"""Shared helper functions used by paper_analysis and paper_download stages."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TIER_SCOPE_MAP = {
    "all": {"Tier 1 – Core", "Tier 2 – High Relevance", "Tier 3 – Related", "Tier 4 – Peripheral"},
    "tier12": {"Tier 1 – Core", "Tier 2 – High Relevance"},
    "tier1": {"Tier 1 – Core"},
}


def _resolve_priority_path(args) -> Path:
    p = Path(args.analysis_priority_json)
    if p.is_absolute():
        return p
    return (Path(args.survey_root) / p).resolve() if not str(p).startswith(str(Path(args.survey_root))) else p


def _load_priority_targets(priority_path: Path, tier_scope: str) -> tuple[set[str], dict[str, int]]:
    data = json.loads(priority_path.read_text(encoding="utf-8"))
    papers = data.get("papers", []) if isinstance(data, dict) else []
    allowed = TIER_SCOPE_MAP.get(tier_scope, TIER_SCOPE_MAP["all"])

    targets: set[str] = set()
    tier_counts = {k: 0 for k in sorted(list(allowed))}

    for rec in papers:
        if not isinstance(rec, dict):
            continue
        if rec.get("status") != "ok":
            continue
        arxiv_id = str(rec.get("arxiv_id", "")).strip()
        classification = rec.get("classification", {}) if isinstance(rec.get("classification", {}), dict) else {}
        tier = str(classification.get("relevance_tier", "")).strip()
        if not arxiv_id:
            continue
        if tier not in allowed:
            continue
        targets.add(arxiv_id)
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    return targets, tier_counts


def _existing_analysis_ids(analysis_dir: Path) -> set[str]:
    return {p.name.replace("_analysis.md", "") for p in analysis_dir.glob("*_analysis.md")}


def _load_paper_index(paper_list_path: Path, survey_root: Path) -> dict[str, dict]:
    if not paper_list_path.exists():
        return {}
    try:
        data = json.loads(paper_list_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, dict] = {}
    for p in data.get("papers", []):
        if not isinstance(p, dict):
            continue
        pid = str(p.get("paper_id", "")).strip()
        aid = str(p.get("arXiv_id", p.get("arxiv_id", ""))).strip()
        key = pid or aid
        if not key:
            continue
        rec = dict(p)
        pdf_path = rec.get("pdf_path")
        if pdf_path:
            pdf_path_obj = Path(str(pdf_path))
            if not pdf_path_obj.is_absolute():
                rec["pdf_path"] = str((survey_root / pdf_path_obj).resolve())
        out[key] = rec
    return out


def _resolve_pdf_path(rec: dict, paper_id: str, pdf_dir: Path | None = None) -> Path | None:
    val = rec.get("pdf_path")
    if val:
        p = Path(str(val))
        if p.exists():
            return p
    guess_str = rec.get("source_pdf_guess", "")
    if guess_str:
        guess = Path(guess_str)
        if guess.exists():
            return guess
    if pdf_dir:
        by_safe_id = pdf_dir / f"{paper_id.replace('/', '_')}.pdf"
        if by_safe_id.exists():
            return by_safe_id
        by_raw_id = pdf_dir / f"{paper_id}.pdf"
        if by_raw_id.exists():
            return by_raw_id
    return None


def _download_pdf_for_id(arxiv_id: str, pdf_dir: Path, verbose: bool = False) -> Path | None:
    pdf_dir.mkdir(parents=True, exist_ok=True)
    try:
        from arxiv_fetch import download as arxiv_download
        result = arxiv_download(arxiv_id, output_dir=str(pdf_dir))
        out = Path(result.get("path", "")) if isinstance(result, dict) else None
        if out and out.exists():
            return out
    except Exception as exc:
        if verbose:
            print(f"  download import-path failed for {arxiv_id}: {exc}")

    try:
        cmd = [sys.executable, "tools/arxiv_fetch.py", "download", arxiv_id, "--dir", str(pdf_dir)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode != 0 and verbose:
            print(f"  download cmd failed for {arxiv_id}: {res.stderr.strip()}")
    except Exception as exc:
        if verbose:
            print(f"  download subprocess failed for {arxiv_id}: {exc}")

    candidate = pdf_dir / f"{arxiv_id.replace('/', '_')}.pdf"
    if candidate.exists():
        return candidate
    raw_candidate = pdf_dir / f"{arxiv_id}.pdf"
    if raw_candidate.exists():
        return raw_candidate
    return None


def _ensure_local_pdf_for_targets(
    target_ids: list[str],
    paper_index: dict[str, dict],
    pdf_dir: Path,
    verbose: bool = False,
) -> dict[str, object]:
    ready = 0
    downloaded = 0
    failed = 0
    failed_ids: list[str] = []

    for idx, pid in enumerate(target_ids, start=1):
        if verbose and idx % 20 == 0:
            print(f"  checking pdfs: {idx}/{len(target_ids)}")

        rec = paper_index.get(pid, {})
        existing = _resolve_pdf_path(rec, pid, pdf_dir)
        if existing:
            ready += 1
            continue

        out = _download_pdf_for_id(pid, pdf_dir, verbose=verbose)
        if out and out.exists():
            downloaded += 1
            continue

        failed += 1
        failed_ids.append(pid)

    return {
        "ready": ready,
        "downloaded": downloaded,
        "failed": failed,
        "failed_ids": failed_ids,
    }


def _extract_pdf_text(pdf_path: Path) -> str:
    if not pdf_path or not pdf_path.exists():
        return ""

    try:
        cmd = ["pdftotext", "-f", "1", "-l", "20", "-layout", str(pdf_path), "-"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode == 0 and len(res.stdout.strip()) > 200:
            return res.stdout
    except Exception:
        pass

    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(str(pdf_path))
        parts: list[str] = []
        for page in reader.pages[:20]:
            txt = page.extract_text() or ""
            if txt:
                parts.append(txt)
        text = "\n".join(parts)
        if len(text.strip()) > 200:
            return text
    except Exception:
        pass

    return ""


def _pick_sentences(text: str, keywords: list[str], limit: int = 2) -> list[str]:
    sentences = re.split(r"(?<=[\.!?])\s+", re.sub(r"\s+", " ", text))
    out: list[str] = []
    for s in sentences:
        ls = s.lower()
        if any(k in ls for k in keywords) and len(s) >= 40:
            out.append(s.strip())
            if len(out) >= limit:
                break
    return out


def _collect_evidence(pdf_text: str, abstract_text: str) -> dict[str, list[str]]:
    text = pdf_text or ""
    return {
        "method": _pick_sentences(text, ["method", "propose", "framework", "algorithm", "quantization"], limit=2)
        or _pick_sentences(abstract_text, ["propose", "quantization"], limit=1),
        "evaluation": _pick_sentences(text, ["experiment", "benchmark", "perplexity", "accuracy", "latency", "throughput"], limit=2)
        or _pick_sentences(abstract_text, ["benchmark", "evaluate"], limit=1),
        "hardware": _pick_sentences(text, ["gpu", "cpu", "edge", "hardware", "kernel", "accelerator"], limit=2),
        "training": _pick_sentences(text, ["post-training", "ptq", "qat", "fine-tuning", "training"], limit=2),
    }


def _build_analysis_from_pdf(paper_id: str, meta: dict, cls: dict, pdf_text: str, pdf_path: Path) -> str:
    title = meta.get("title", "")
    authors = meta.get("authors", [])
    published = meta.get("published", "")
    year = published[:4] if published else "Unknown"
    month = published[5:7] if len(published) >= 7 else "Unknown"
    abstract = meta.get("abstract", "")
    ev = _collect_evidence(pdf_text, abstract)

    def _render_block(name: str, rows: list[str]) -> str:
        if not rows:
            return f"- {name}: evidence not confidently extracted from first pages"
        return "\n".join([f"- {name}: {r}" for r in rows])

    return f"""# Paper Analysis: {paper_id}

## Paper Metadata

- **Paper ID**: {paper_id}
- **Title**: {title}
- **Authors**: {', '.join(authors) if authors else 'Unknown'}
- **Year/Month**: {year}/{month}
- **Venue**: arXiv
- **Source**: Local PDF + arXiv metadata
- **arXiv ID**: {paper_id}
- **PDF Path**: {pdf_path}
- **Analysis Date**: {datetime.now().date()}

---

## multi-field Classification (PDF-First Draft)

1. **Model Type**: {cls.get('model_type', 'Unknown')}
2. **Method Category**: {cls.get('method_category', 'Unknown')}
3. **Specific Method**: {cls.get('specific_method', 'Unknown')}
4. **Training Paradigm**: {cls.get('training', 'Unknown')}
5. **Core Challenge**: {cls.get('core_challenge', 'Unknown')}
6. **Evaluation Focus**: {cls.get('evaluation', 'Unknown')}
7. **Hardware Co-design**: {cls.get('hardware', 'Unknown')}
8. **Summary**: {cls.get('summary', 'Unknown')}
9. **Quantization Bit Scope**: {cls.get('bit_scope', 'Unknown')}
10. **General Method Type**: {cls.get('general_method', 'Unknown')}
11. **Core Challenge Addressed**: {cls.get('core_challenge_addressed', 'Unknown')}
12. **Survey Contribution Mapping**: {cls.get('survey_contribution', 'Unknown')}

---

## Evidence Snippets (From PDF First Pages)

{_render_block('Method', ev.get('method', []))}
{_render_block('Evaluation', ev.get('evaluation', []))}
{_render_block('Hardware', ev.get('hardware', []))}
{_render_block('Training', ev.get('training', []))}

---

## Abstract Snapshot

{abstract}

---

## Notes

- This file is auto-generated in PDF-first mode from locally available PDF text.
- TODO-DEEP-READ: Upgrade to full section-level evidence extraction when needed.

"""


def _build_analysis_draft(paper_id: str, meta: dict, cls: dict) -> str:
    title = meta.get("title", "")
    authors = meta.get("authors", [])
    published = meta.get("published", "")
    year = published[:4] if published else "Unknown"
    month = published[5:7] if len(published) >= 7 else "Unknown"
    abstract = meta.get("abstract", "")

    return f"""# Paper Analysis: {paper_id}

## Paper Metadata

- **Paper ID**: {paper_id}
- **Title**: {title}
- **Authors**: {', '.join(authors) if authors else 'Unknown'}
- **Year/Month**: {year}/{month}
- **Venue**: arXiv
- **Source**: arXiv API (triage fallback)
- **arXiv ID**: {paper_id}
- **Analysis Date**: {datetime.now().date()}

---

## multi-field Classification (Triage-Derived Draft)

1. **Model Type**: {cls.get('model_type', 'Unknown')}
2. **Method Category**: {cls.get('method_category', 'Unknown')}
3. **Specific Method**: {cls.get('specific_method', 'Unknown')}
4. **Training Paradigm**: {cls.get('training', 'Unknown')}
5. **Core Challenge**: {cls.get('core_challenge', 'Unknown')}
6. **Evaluation Focus**: {cls.get('evaluation', 'Unknown')}
7. **Hardware Co-design**: {cls.get('hardware', 'Unknown')}
8. **Summary**: {cls.get('summary', 'Unknown')}
9. **Quantization Bit Scope**: {cls.get('bit_scope', 'Unknown')}
10. **General Method Type**: {cls.get('general_method', 'Unknown')}
11. **Core Challenge Addressed**: {cls.get('core_challenge_addressed', 'Unknown')}
12. **Survey Contribution Mapping**: {cls.get('survey_contribution', 'Unknown')}

---

## Abstract Snapshot

{abstract}

---

## Evidence Notes

- This file is an auto-generated draft from arXiv metadata triage.
- TODO-DEEP-READ: Replace this draft with full PDF-based evidence extraction.

"""


def _write_coverage_report(
    analysis_dir: Path,
    scope: str,
    mode: str,
    policy: str,
    target_ids: list[str],
    existing_ids: set[str],
    generated_ids: list[str],
    metadata_fallback_ids: list[str] | None,
    tier_counts: dict[str, int],
) -> tuple[str, str]:
    done = sorted([pid for pid in target_ids if pid in existing_ids])
    missing = sorted([pid for pid in target_ids if pid not in existing_ids])
    coverage_rate = round((len(done) / len(target_ids) * 100.0), 2) if target_ids else 100.0

    payload = {
        "generated_at": datetime.now().isoformat(),
        "scope": scope,
        "mode": mode,
        "policy": policy,
        "target_count": len(target_ids),
        "done_count": len(done),
        "missing_count": len(missing),
        "coverage_rate": coverage_rate,
        "generated_count": len(generated_ids),
        "generated_ids": generated_ids,
        "metadata_fallback_count": len(metadata_fallback_ids or []),
        "metadata_fallback_ids": metadata_fallback_ids or [],
        "tier_breakdown": tier_counts,
        "missing_ids": missing,
    }

    out_json = analysis_dir / "paper_analysis_coverage.json"
    out_md = analysis_dir / "paper_analysis_coverage.md"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Paper Analysis Coverage",
        "",
        f"- Scope: {scope}",
        f"- Mode: {mode}",
        f"- Policy: {policy}",
        f"- Target count: {len(target_ids)}",
        f"- Done count: {len(done)}",
        f"- Missing count: {len(missing)}",
        f"- Coverage rate: {coverage_rate}%",
        f"- Auto-generated draft count: {len(generated_ids)}",
        f"- Metadata fallback count: {len(metadata_fallback_ids or [])}",
        "",
        "## Tier Breakdown",
        "",
    ]
    for tier, count in sorted(tier_counts.items()):
        lines.append(f"- {tier}: {count}")
    lines.append("")
    if missing:
        lines.append("## Missing IDs")
        lines.append("")
        for pid in missing:
            lines.append(f"- {pid}")
    else:
        lines.append("No missing IDs.")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return str(out_json), str(out_md)


def _generate_missing_analysis_drafts(
    missing_ids: list[str],
    analysis_dir: Path,
    paper_index: dict[str, dict],
    pdf_dir: Path,
    retry_missing_pdf_download: bool,
    verbose: bool = False,
) -> tuple[list[str], list[str]]:
    try:
        from arxiv_client import fetch_metadata
        from triage_core import DEFAULT_KEYWORDS, classify_12field
    except Exception as exc:
        print(f"WARNING: cannot import triage dependencies for draft generation: {exc}", file=sys.stderr)
        return [], []

    generated: list[str] = []
    metadata_fallback_ids: list[str] = []
    for idx, pid in enumerate(missing_ids, start=1):
        if verbose and idx % 20 == 0:
            print(f"  processing drafts: {idx}/{len(missing_ids)}")

        analysis_file = analysis_dir / f"{pid}_analysis.md"
        benchmark_file = analysis_dir / f"{pid}_benchmark.json"

        # Skip only if both analysis AND benchmark files already exist
        if analysis_file.exists() and benchmark_file.exists():
            if verbose:
                print(f"  skipping {pid}: analysis and benchmark both exist")
            continue

        # If benchmark file missing but analysis exists, just extract benchmark
        if analysis_file.exists() and not benchmark_file.exists():
            pdf_path = _resolve_pdf_path(paper_index.get(pid, {}), pid, pdf_dir)
            if pdf_path and pdf_path.exists():
                try:
                    from benchmark_extractor import extract_benchmarks_from_pdf
                    benchmark_data = extract_benchmarks_from_pdf(str(pdf_path), pages_to_scan=15)
                    benchmark_file.write_text(json.dumps(benchmark_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    if verbose:
                        print(f"  extracted benchmarks: {pid} ({benchmark_data.get('num_benchmark_sections', 0)} sections)")
                except Exception as exc:
                    if verbose:
                        print(f"  benchmark extraction failed for {pid}: {exc}")
            continue

        base_rec = paper_index.get(pid, {})
        paper = fetch_metadata(pid)
        if paper is None:
            continue

        meta = {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "abstract": paper.abstract,
            "authors": paper.authors,
            "categories": paper.categories,
            "published": paper.published,
            "pdf_url": paper.pdf_url,
        }

        pdf_path = _resolve_pdf_path(base_rec, pid, pdf_dir)
        if not pdf_path and retry_missing_pdf_download:
            _download_pdf_for_id(pid, pdf_dir, verbose=verbose)
            pdf_path = _resolve_pdf_path(base_rec, pid, pdf_dir)
        pdf_text = _extract_pdf_text(pdf_path) if pdf_path else ""

        # Extract benchmark data if PDF is available
        if pdf_path and pdf_path.exists():
            try:
                from benchmark_extractor import extract_benchmarks_from_pdf
                benchmark_data = extract_benchmarks_from_pdf(str(pdf_path), pages_to_scan=15)
                benchmark_out = analysis_dir / f"{pid}_benchmark.json"
                benchmark_out.write_text(json.dumps(benchmark_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                if verbose:
                    print(f"  extracted benchmarks: {pid} ({benchmark_data.get('num_benchmark_sections', 0)} sections)")
            except Exception as exc:
                if verbose:
                    print(f"  benchmark extraction failed for {pid}: {exc}")

        enriched_meta = dict(meta)
        if pdf_text:
            enriched_meta["abstract"] = (meta.get("abstract", "") + "\n" + pdf_text[:12000]).strip()
        cls = classify_12field(enriched_meta, DEFAULT_KEYWORDS)

        out = analysis_dir / f"{pid}_analysis.md"

        if pdf_text and pdf_path is not None:
            content = _build_analysis_from_pdf(pid, meta, cls, pdf_text, pdf_path)
        else:
            content = _build_analysis_draft(pid, meta, cls)
            metadata_fallback_ids.append(pid)

        out.write_text(content, encoding="utf-8")
        generated.append(pid)
    return generated, metadata_fallback_ids


def _generate_paper_list_from_corpus(corpus_path: Path, paper_list_path: Path) -> None:
    if not corpus_path.exists():
        print(f"Warning: corpus report not found ({corpus_path}), skipping paper_list.json generation")
        return

    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    all_papers = corpus.get("all_papers", [])

    topic = corpus.get("keywords_used", ["unknown"])[0] if corpus.get("keywords_used") else "unknown"

    paper_list = {
        "topic": topic,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "description": f"Survey paper collection from arxiv_results.json ({len(all_papers)} papers)",
        "papers": [],
    }

    for p in all_papers:
        arxiv_id = p.get("arxiv_id", "")
        published = p.get("published", "")
        year = int(published[:4]) if published and len(published) >= 4 else 2024
        authors_raw = p.get("authors", [])
        authors = [a.strip() for a in authors_raw]

        paper_entry = {
            "paper_id": arxiv_id,
            "title": p.get("title", "Unknown"),
            "authors": authors,
            "year": year,
            "venue": "arXiv",
            "arXiv_id": arxiv_id,
            "category": p.get("tier", "Tier 3").split("–")[0].strip() if "–" in p.get("tier", "") else p.get("tier", "Tier 3"),
            "subcategory": "",
            "priority": "HIGH" if "Tier 1" in p.get("tier", "") else ("MED" if "Tier 2" in p.get("tier", "") else "LOW"),
            "contribution": "",
            "pdf_path": p.get("pdf_path"),
            "source": "arxiv_results.json",
            "abstract": p.get("abstract", ""),
            "tier": p.get("tier", ""),
            "score": p.get("score", 0),
            "matched_keywords": p.get("matched_keywords", []),
        }
        paper_list["papers"].append(paper_entry)

    paper_list_path.parent.mkdir(parents=True, exist_ok=True)
    paper_list_path.write_text(json.dumps(paper_list, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Generated paper_list.json: {len(paper_list['papers'])} papers")
    print("Tier breakdown:")
    tier_counts = {}
    for p in paper_list["papers"]:
        tier = p.get("tier", "Unknown")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    for tier, count in sorted(tier_counts.items()):
        print(f"  {tier}: {count}")
