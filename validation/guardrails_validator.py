from __future__ import annotations

import fnmatch
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set


def _git_changed_files(project_root: Path) -> Set[str]:
    changed: Set[str] = set()

    cmds = [
        ["git", "-C", str(project_root), "diff", "--name-only", "HEAD"],
        ["git", "-C", str(project_root), "ls-files", "--others", "--exclude-standard"],
    ]
    for cmd in cmds:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except Exception:
            continue
        if res.returncode != 0:
            continue
        for line in res.stdout.splitlines():
            line = line.strip()
            if line:
                changed.add(line)

    return changed


def _matches_any(path: str, patterns: List[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def _load_baseline(project_root: Path, baseline_path: str) -> Set[str]:
    path = project_root / baseline_path
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("files", []))
    except Exception:
        return set()


def _save_baseline(project_root: Path, baseline_path: str, files: Set[str]) -> None:
    path = project_root / baseline_path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": sorted(files),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_guardrails_validation(
    project_root: Path,
    report_dir: Path,
    policy: Dict,
    strict: bool,
    record_baseline: bool,
    survey_root: Path | None = None,
) -> Dict:
    allow_patterns = list(policy.get("allow_write_patterns", [])) + ["validation/**"]
    protected_patterns = list(policy.get("protected_patterns", []))
    baseline_path = str(policy.get("baseline_file", "validation/guardrails_baseline.json"))

    changed = _git_changed_files(project_root)

    if record_baseline:
        _save_baseline(project_root, baseline_path, changed)

    baseline = _load_baseline(project_root, baseline_path)
    new_changed = changed - baseline

    violations = []
    warnings = []

    for f in sorted(new_changed):
        if _matches_any(f, allow_patterns):
            continue
        if _matches_any(f, protected_patterns):
            violations.append(
                {
                    "level": "critical",
                    "code": "PROTECTED_PATH_MODIFIED",
                    "item": f,
                    "message": "Path is protected and cannot be modified in strict autorun",
                }
            )
        else:
            warnings.append(
                {
                    "level": "warning",
                    "code": "OUTSIDE_ALLOWLIST",
                    "item": f,
                    "message": "Changed path is outside allow_write_patterns",
                }
            )

    critical_count = len(violations)
    warning_count = len(warnings)
    passed = critical_count == 0

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "guardrails",
        "strict": strict,
        "passed": passed,
        "record_baseline": record_baseline,
        "baseline_file": baseline_path,
        "changed_files_total": len(changed),
        "changed_files_considered": len(new_changed),
        "critical_count": critical_count,
        "warning_count": warning_count,
        "issues": violations + warnings,
    }

    out_json = report_dir / "guardrails_validation_report.json"
    out_md = report_dir / "guardrails_validation_report.md"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Guardrails Validation Report",
        "",
        f"- Passed: {passed}",
        f"- Critical: {critical_count}",
        f"- Warning: {warning_count}",
        f"- Changed files total: {len(changed)}",
        f"- Changed files considered (after baseline): {len(new_changed)}",
        f"- Baseline file: {baseline_path}",
        "",
    ]
    if payload["issues"]:
        lines.append("## Issues")
        lines.append("")
        for i in payload["issues"]:
            lines.append(f"- [{i['level'].upper()}] {i['code']} | {i['item']} | {i['message']}")
    else:
        lines.append("No issues found.")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "passed": passed,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "retried": 0,
        "report_json": str(out_json),
        "report_md": str(out_md),
    }
