from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ARXIV_API = "http://export.arxiv.org/api/query"
ATOM_NS = "http://www.w3.org/2005/Atom"
USER_AGENT = "SurveyMind-validation/1.0"

ARXIV_ID_RE = re.compile(r"\b\d{4}\.\d{4,5}\b")
CITE_KEY_RE = re.compile(r"\\cite\{([^}]+)\}")


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


def _normalize_arxiv_id(value: str) -> str:
    value = value.strip()
    value = value.replace("https://arxiv.org/abs/", "").replace("http://arxiv.org/abs/", "")
    value = value.replace("https://arxiv.org/pdf/", "").replace("http://arxiv.org/pdf/", "")
    value = value.replace(".pdf", "")
    if "v" in value and ARXIV_ID_RE.search(value):
        value = value.split("v")[0]
    return value


def _fetch_arxiv_metadata(arxiv_id: str) -> Optional[Dict]:
    query = f"id:{arxiv_id}"
    url = f"{ARXIV_API}?search_query={urllib.parse.quote(query)}&max_results=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_text = resp.read().decode("utf-8")
        root = ET.fromstring(xml_text)
        entry = root.find(f"{{{ATOM_NS}}}entry")
        if entry is None:
            return None
        title = (entry.findtext(f"{{{ATOM_NS}}}title", "") or "").strip()
        authors = [
            (a.findtext(f"{{{ATOM_NS}}}name", "") or "").strip()
            for a in entry.findall(f"{{{ATOM_NS}}}author")
        ]
        published = (entry.findtext(f"{{{ATOM_NS}}}published", "") or "")[:4]
        return {
            "arxiv_id": arxiv_id,
            "title": re.sub(r"\s+", " ", title),
            "first_author": authors[0] if authors else "",
            "year": int(published) if published.isdigit() else None,
        }
    except Exception:
        return None


def _title_similarity(a: str, b: str) -> float:
    sa = set(re.findall(r"[a-z0-9]+", a.lower()))
    sb = set(re.findall(r"[a-z0-9]+", b.lower()))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))


def _pick_path(project_root: Path, survey_root: Optional[Path], gate_rel: str, legacy_rel: str) -> Path:
    if survey_root:
        gate_path = survey_root / gate_rel
        if gate_path.exists():
            return gate_path
    return project_root / legacy_rel


def _load_registry(project_root: Path, survey_root: Optional[Path]) -> Tuple[Dict[str, Dict], List[Issue]]:
    issues: List[Issue] = []
    paper_list = _pick_path(project_root, survey_root, "gate1_research_lit/paper_list.json", "paper_list.json")
    if not paper_list.exists():
        issues.append(Issue("critical", "MISSING_PAPER_LIST", "paper_list.json not found", "paper_list.json"))
        return {}, issues

    data = json.loads(paper_list.read_text(encoding="utf-8"))
    papers = data.get("papers", [])
    registry: Dict[str, Dict] = {}
    seen: Set[str] = set()

    for p in papers:
        paper_id = _normalize_arxiv_id(str(p.get("paper_id", "")))
        arxiv_id = _normalize_arxiv_id(str(p.get("arXiv_id", p.get("arxiv_id", ""))))
        canonical = arxiv_id or paper_id

        if not canonical:
            issues.append(Issue("critical", "MISSING_ID", "Missing paper_id/arXiv_id", str(p.get("title", "<unknown>"))))
            continue
        if canonical in seen:
            issues.append(Issue("critical", "DUPLICATE_ID", "Duplicate paper id", canonical))
            continue
        seen.add(canonical)

        title = str(p.get("title", "")).strip()
        authors = p.get("authors", []) if isinstance(p.get("authors", []), list) else []
        year = p.get("year", None)

        if not ARXIV_ID_RE.search(canonical):
            issues.append(Issue("warning", "NON_STANDARD_ID", "ID does not match arXiv pattern", canonical))

        if not title:
            issues.append(Issue("critical", "MISSING_TITLE", "Missing title", canonical, retryable=True))
        if not authors:
            issues.append(Issue("warning", "MISSING_AUTHORS", "Missing authors", canonical, retryable=True))
        if not isinstance(year, int):
            issues.append(Issue("warning", "MISSING_YEAR", "Missing year", canonical, retryable=True))

        registry[canonical] = {
            "paper_id": canonical,
            "title": title,
            "first_author": str(authors[0]) if authors else "",
            "year": year,
        }

    return registry, issues


def _extract_citations_from_text(path: Path) -> Tuple[Set[str], Set[str]]:
    if not path.exists():
        return set(), set()
    text = path.read_text(encoding="utf-8", errors="ignore")
    arxiv_ids = set(_normalize_arxiv_id(m.group(0)) for m in ARXIV_ID_RE.finditer(text))

    cite_keys: Set[str] = set()
    for m in CITE_KEY_RE.finditer(text):
        keys = [x.strip() for x in m.group(1).split(",") if x.strip()]
        cite_keys.update(keys)
    return arxiv_ids, cite_keys


def _collect_source_ids_from_analysis(project_root: Path, survey_root: Optional[Path]) -> Set[str]:
    out: Set[str] = set()
    analysis_dir = _pick_path(project_root, survey_root, "gate2_paper_analysis", "paper_analysis_results")
    if not analysis_dir.exists():
        return out
    for p in analysis_dir.glob("*_analysis.md"):
        stem = p.name.replace("_analysis.md", "")
        out.add(_normalize_arxiv_id(stem))
    return out


def _load_discovery_ids(project_root: Path, survey_root: Optional[Path]) -> Set[str]:
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
    out: Set[str] = set()
    for rec in data:
        if not isinstance(rec, dict):
            continue
        rid = _normalize_arxiv_id(str(rec.get("id", rec.get("arxiv_id", ""))))
        if rid:
            out.add(rid)
    return out


def _validate_once(project_root: Path, survey_root: Optional[Path], fetched_cache: Dict[str, Dict]) -> List[Issue]:
    issues: List[Issue] = []
    registry, reg_issues = _load_registry(project_root, survey_root)
    discovery_ids = _load_discovery_ids(project_root, survey_root)
    issues.extend(reg_issues)

    if not registry and discovery_ids:
        issues.append(
            Issue(
                "warning",
                "MISSING_PAPER_LIST_USING_DISCOVERY",
                "paper_list.json missing or empty, falling back to arxiv_results.json id checks",
                "paper_list.json",
            )
        )

    analysis_ids = _collect_source_ids_from_analysis(project_root, survey_root)
    for aid in sorted(analysis_ids):
        if aid not in registry:
            if aid in discovery_ids:
                issues.append(
                    Issue(
                        "warning",
                        "ANALYSIS_ID_NOT_IN_SELECTED_LIST",
                        "Analysis id not in paper_list.json but present in arxiv_results.json (subset workflow)",
                        aid,
                    )
                )
            else:
                issues.append(Issue("critical", "ANALYSIS_ID_NOT_IN_REGISTRY", "Analysis file id not found in paper_list/arxiv_results", aid))

    draft_path = _pick_path(project_root, survey_root, "gate5_survey_write/SURVEY_DRAFT.md", "SURVEY_DRAFT.md")
    draft_ids, draft_keys = _extract_citations_from_text(draft_path)

    tex_path = _pick_path(
        project_root,
        survey_root,
        "gate5_survey_write/literature_review_survey.tex",
        "tpami_tem/literature_review_survey.tex",
    )
    tex_ids, tex_keys = _extract_citations_from_text(tex_path)

    cited_ids = draft_ids | tex_ids
    for cid in sorted(cited_ids):
        if cid not in registry:
            if cid in discovery_ids:
                issues.append(
                    Issue(
                        "warning",
                        "CITED_ID_NOT_IN_SELECTED_LIST",
                        "Cited arXiv id is outside paper_list.json but present in arxiv_results.json",
                        cid,
                        retryable=False,
                    )
                )
            else:
                issues.append(Issue("critical", "CITED_ID_NOT_IN_REGISTRY", "Cited arXiv id not found in paper_list/arxiv_results", cid, retryable=True))

    if draft_keys or tex_keys:
        bib_path = _pick_path(project_root, survey_root, "gate5_survey_write/references.bib", "tpami_tem/references.bib")
        if bib_path.exists():
            bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
            bib_keys = set(re.findall(r"@\w+\{\s*([^,\s]+)", bib_text))
            missing_keys = (draft_keys | tex_keys) - bib_keys
            for key in sorted(missing_keys):
                issues.append(Issue("critical", "CITE_KEY_NOT_IN_BIB", "Citation key missing from references.bib", key))

    # Metadata consistency against arXiv fetch cache
    for rid, entry in registry.items():
        if not ARXIV_ID_RE.search(rid):
            continue
        remote = fetched_cache.get(rid)
        if remote is None:
            continue
        if remote.get("title") and entry.get("title"):
            sim = _title_similarity(entry["title"], remote["title"])
            if sim < 0.55:
                issues.append(
                    Issue(
                        "critical",
                        "TITLE_MISMATCH",
                        f"Title similarity too low ({sim:.2f})",
                        rid,
                        retryable=True,
                    )
                )
        ry = remote.get("year")
        ly = entry.get("year")
        if isinstance(ly, int) and isinstance(ry, int) and ly != ry:
            issues.append(Issue("warning", "YEAR_MISMATCH", f"Local year {ly} != arXiv year {ry}", rid, retryable=True))

    return issues


def _retry_refetch(issues: List[Issue], fetched_cache: Dict[str, Dict]) -> int:
    retry_ids = sorted({i.item for i in issues if i.retryable and ARXIV_ID_RE.search(i.item)})
    retried = 0
    for rid in retry_ids:
        meta = _fetch_arxiv_metadata(rid)
        if meta is not None:
            fetched_cache[rid] = meta
        retried += 1
    return retried


def run_citation_validation(
    project_root: Path,
    report_dir: Path,
    policy: Dict,
    strict: bool,
    retry: int,
    survey_root: Optional[Path] = None,
) -> Dict:
    fetched_cache: Dict[str, Dict] = {}
    retried = 0
    last_issues: List[Issue] = []

    attempts = max(1, retry + 1)
    for attempt in range(attempts):
        issues = _validate_once(project_root, survey_root, fetched_cache)
        last_issues = issues
        retryable_left = any(i.retryable for i in issues)
        if attempt < attempts - 1 and retryable_left:
            retried += _retry_refetch(issues, fetched_cache)
            continue
        break

    critical = [i for i in last_issues if i.level == "critical"]
    warning = [i for i in last_issues if i.level == "warning"]
    passed = len(critical) == 0

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "citations",
        "passed": passed,
        "strict": strict,
        "retry_config": retry,
        "retried": retried,
        "critical_count": len(critical),
        "warning_count": len(warning),
        "issues": [i.as_dict() for i in last_issues],
    }

    out_json = report_dir / "citation_validation_report.json"
    out_md = report_dir / "citation_validation_report.md"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Citation Validation Report",
        "",
        f"- Passed: {passed}",
        f"- Critical: {len(critical)}",
        f"- Warning: {len(warning)}",
        f"- Retry attempts configured: {retry}",
        f"- Re-fetch operations executed: {retried}",
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
