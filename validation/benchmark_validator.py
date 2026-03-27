from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


@dataclass
class Issue:
    level: str
    code: str
    message: str
    item: str
    retryable: bool = False

    def as_dict(self) -> Dict:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "item": self.item,
            "retryable": self.retryable,
        }


def _parse_number(raw: object) -> Optional[float]:
    if isinstance(raw, (int, float)):
        return float(raw)
    if not isinstance(raw, str):
        return None
    text = raw.strip().replace(",", "")
    m = NUM_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _metric_kind(metric: str) -> str:
    m = metric.lower()
    if "ppl" in m or "perplexity" in m or "wikitext" in m or "ptb" in m or "c4" in m:
        return "ppl"
    if any(x in m for x in ["acc", "accuracy", "avg", "arc", "boolq", "piqa", "mmlu", "lambada", "hellaswag", "winogrande"]):
        return "acc"
    return "other"


def _validate_benchmark_file(path: Path, registry_ids: set[str], discovery_ids: set[str]) -> List[Issue]:
    issues: List[Issue] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(Issue("critical", "JSON_PARSE_ERROR", f"Cannot parse JSON: {exc}", path.name, retryable=True))
        return issues

    paper_id = str(data.get("paper_id", "")).strip()
    if not paper_id:
        issues.append(Issue("critical", "MISSING_PAPER_ID", "paper_id missing", path.name, retryable=True))
        return issues

    expected = path.name.replace("_benchmark.json", "")
    if paper_id != expected:
        issues.append(Issue("warning", "PAPER_ID_FILENAME_MISMATCH", f"paper_id={paper_id}, filename={expected}", path.name, retryable=True))

    if paper_id not in registry_ids:
        if paper_id in discovery_ids:
            issues.append(
                Issue(
                    "warning",
                    "BENCHMARK_ID_NOT_IN_SELECTED_LIST",
                    "benchmark paper_id not in paper_list.json but present in arxiv_results.json",
                    paper_id,
                    retryable=False,
                )
            )
        else:
            issues.append(Issue("critical", "BENCHMARK_ID_NOT_IN_REGISTRY", "benchmark paper_id not found in paper_list/arxiv_results", paper_id, retryable=True))

    models = data.get("models")
    if not isinstance(models, dict) or not models:
        issues.append(Issue("critical", "MISSING_MODELS", "models object missing or empty", path.name, retryable=True))
        return issues

    for model_name, metrics in models.items():
        if not isinstance(metrics, dict) or not metrics:
            issues.append(Issue("critical", "INVALID_MODEL_METRICS", "model metrics missing", f"{path.name}:{model_name}", retryable=True))
            continue
        for key, raw in metrics.items():
            if key.lower().endswith("method") or key.lower().endswith("bits"):
                continue
            value = _parse_number(raw)
            if value is None:
                issues.append(Issue("warning", "NON_NUMERIC_METRIC", f"Cannot parse metric value: {raw}", f"{path.name}:{model_name}:{key}", retryable=True))
                continue
            kind = _metric_kind(key)
            if kind == "ppl":
                if value <= 0:
                    issues.append(Issue("critical", "INVALID_PPL", f"PPL must be > 0, got {value}", f"{path.name}:{model_name}:{key}", retryable=True))
                if value > 1e5:
                    issues.append(Issue("warning", "EXTREME_PPL", f"Very large PPL {value}", f"{path.name}:{model_name}:{key}"))
            elif kind == "acc":
                if value < 0 or value > 100:
                    issues.append(Issue("critical", "INVALID_ACCURACY_RANGE", f"Accuracy-like metric out of [0,100]: {value}", f"{path.name}:{model_name}:{key}", retryable=True))

    return issues


def _pick_path(project_root: Path, survey_root: Optional[Path], gate_rel: str, legacy_rel: str) -> Path:
    if survey_root:
        gate_path = survey_root / gate_rel
        if gate_path.exists():
            return gate_path
    return project_root / legacy_rel


def _load_registry_ids(project_root: Path, survey_root: Optional[Path]) -> set[str]:
    paper_list = _pick_path(project_root, survey_root, "gate1_research_lit/paper_list.json", "paper_list.json")
    if not paper_list.exists():
        return set()
    data = json.loads(paper_list.read_text(encoding="utf-8"))
    ids = set()
    for p in data.get("papers", []):
        pid = str(p.get("paper_id", "")).strip()
        if pid:
            ids.add(pid)
        aid = str(p.get("arXiv_id", p.get("arxiv_id", ""))).strip()
        if aid:
            ids.add(aid)
    return ids


def _load_discovery_ids(project_root: Path, survey_root: Optional[Path]) -> set[str]:
    arxiv_json = _pick_path(project_root, survey_root, "gate1_research_lit/arxiv_results.json", "arxiv_results.json")
    if not arxiv_json.exists():
        return set()
    try:
        data = json.loads(arxiv_json.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if isinstance(data, dict):
        for key in ("results", "papers", "data", "items"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
    if not isinstance(data, list):
        return set()
    ids = set()
    for rec in data:
        if isinstance(rec, dict):
            rid = str(rec.get("id", rec.get("arxiv_id", ""))).strip()
            if rid:
                ids.add(rid)
    return ids


def _attempt_reextract(project_root: Path, survey_root: Optional[Path], paper_id: str, out_dir: Path) -> bool:
    pdf = _pick_path(project_root, survey_root, f"gate1_research_lit/papers/{paper_id}.pdf", f"papers/{paper_id}.pdf")
    if not pdf.exists():
        return False
    out_file = out_dir / f"{paper_id}_reextract.json"
    cmd = [
        sys.executable,
        str(project_root / "tools" / "benchmark_extractor.py"),
        "extract",
        str(pdf),
        "-o",
        str(out_file),
        "-p",
        "12",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except Exception:
        return False
    return res.returncode == 0 and out_file.exists()


def _validate_once(project_root: Path, survey_root: Optional[Path]) -> List[Issue]:
    issues: List[Issue] = []
    registry_ids = _load_registry_ids(project_root, survey_root)
    discovery_ids = _load_discovery_ids(project_root, survey_root)
    if not registry_ids and not discovery_ids:
        issues.append(Issue("critical", "MISSING_REGISTRY", "paper_list.json and arxiv_results.json both missing or empty", "paper_list.json"))
    elif not registry_ids and discovery_ids:
        issues.append(Issue("warning", "MISSING_PAPER_LIST_USING_DISCOVERY", "paper_list.json missing or empty, using arxiv_results.json fallback", "paper_list.json"))

    benchmark_dir = _pick_path(project_root, survey_root, "gate2_paper_analysis", "paper_analysis_results")
    files = sorted(benchmark_dir.glob("*_benchmark.json")) if benchmark_dir.exists() else []
    if not files:
        issues.append(Issue("warning", "NO_BENCHMARK_FILES", "No *_benchmark.json files found", "paper_analysis_results"))

    for f in files:
        issues.extend(_validate_benchmark_file(f, registry_ids, discovery_ids))

    survey_file = project_root / "tools" / "benchmark_survey.json"
    if survey_file.exists():
        try:
            survey = json.loads(survey_file.read_text(encoding="utf-8"))
            models = survey.get("models", {})
            if not isinstance(models, dict) or not models:
                issues.append(Issue("critical", "INVALID_SURVEY_BENCHMARK", "tools/benchmark_survey.json models missing", "tools/benchmark_survey.json", retryable=True))
        except Exception as exc:
            issues.append(Issue("critical", "SURVEY_BENCHMARK_PARSE_ERROR", f"Cannot parse benchmark_survey.json: {exc}", "tools/benchmark_survey.json", retryable=True))
    else:
        issues.append(Issue("warning", "SURVEY_BENCHMARK_MISSING", "tools/benchmark_survey.json not found", "tools/benchmark_survey.json"))

    return issues


def run_benchmark_validation(
    project_root: Path,
    report_dir: Path,
    policy: Dict,
    strict: bool,
    retry: int,
    survey_root: Optional[Path] = None,
) -> Dict:
    retried = 0
    last_issues: List[Issue] = []

    attempts = max(1, retry + 1)
    for attempt in range(attempts):
        issues = _validate_once(project_root, survey_root)
        last_issues = issues

        retry_items = sorted({i.item for i in issues if i.retryable})
        if attempt < attempts - 1 and retry_items:
            out_dir = project_root / "validation" / "tmp" / "reextract"
            out_dir.mkdir(parents=True, exist_ok=True)
            for item in retry_items:
                pid = item.split(":")[0].replace("_benchmark.json", "")
                if re.match(r"\d{4}\.\d{4,5}$", pid):
                    if _attempt_reextract(project_root, survey_root, pid, out_dir):
                        retried += 1
            continue
        break

    critical = [i for i in last_issues if i.level == "critical"]
    warning = [i for i in last_issues if i.level == "warning"]
    passed = len(critical) == 0

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "benchmarks",
        "passed": passed,
        "strict": strict,
        "retry_config": retry,
        "retried": retried,
        "critical_count": len(critical),
        "warning_count": len(warning),
        "issues": [i.as_dict() for i in last_issues],
    }

    out_json = report_dir / "benchmark_validation_report.json"
    out_md = report_dir / "benchmark_validation_report.md"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Benchmark Validation Report",
        "",
        f"- Passed: {passed}",
        f"- Critical: {len(critical)}",
        f"- Warning: {len(warning)}",
        f"- Retry attempts configured: {retry}",
        f"- Re-extract operations executed: {retried}",
        "",
    ]
    if last_issues:
        lines.append("## Issues")
        lines.append("")
        for i in last_issues:
            lines.append(f"- [{i.level.upper()}] {i.code} | {i.item} | {i.message}")
    else:
        lines.append("No issues found.")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "passed": passed,
        "critical_count": len(critical),
        "warning_count": len(warning),
        "retried": retried,
        "report_json": str(out_json),
        "report_md": str(out_md),
    }
