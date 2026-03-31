#!/usr/bin/env python3
"""
arxiv_json_extractor.py — SurveyMind arXiv JSON Paper Processor

Parses an arXiv search results JSON file and produces an actionable
paper corpus report: classification by relevance tier, PDF availability,
and gap detection vs. an existing papers/ directory.

Designed to be reusable for ANY survey topic — all topic-specific
logic is parameterized via CLI flags.

Usage
-----
    # Basic: extract from arxiv_results.json
    python3 tools/arxiv_json_extractor.py \\
        --input tpami_tem/arxiv_results.json \\
        --papers-dir papers \\
        --topic-keywords "quantization,LLM,binary,ternary,low-bit" \\
        --output corpus_report.json

    # Dry run: just show tier distribution without downloading metadata
    python3 tools/arxiv_json_extractor.py \\
        --input tpami_tem/arxiv_results.json \\
        --papers-dir papers \\
        --topic-keywords "quantization,LLM" \\
        --dry-run

    # With arxiv API enrichment (fetches abstract/categories)
    python3 tools/arxiv_json_extractor.py \\
        --input tpami_tem/arxiv_results.json \\
        --papers-dir papers \\
        --topic-keywords "quantization,LLM" \\
        --enrich-from-arxiv

Output
------
    corpus_report.json   — structured machine-readable report
    corpus_report.md     — human-readable markdown summary

Exit codes
    0  success
    1  file not found / JSON parse error
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from domain_profile import (
    DomainProfileError,
    load_domain_profile,
    profile_context_keywords,
    profile_core_keywords,
    profile_keywords,
)
from triage_core import compute_relevance_score

# ─── arXiv API ────────────────────────────────────────────────────────────────

ARXIV_API = "http://export.arxiv.org/api/query"
USER_AGENT = "SurveyMind-arxiv-extractor/1.0"

_ATOM_NS = "http://www.w3.org/2005/Atom"


def fetch_arxiv_metadata(arxiv_id: str, retries: int = 2) -> dict | None:
    """Fetch abstract + categories from arXiv API for one paper."""
    query = f"id:{arxiv_id}"
    url = f"{ARXIV_API}?search_query={urllib.parse.quote(query)}&max_results=1"
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml_text = resp.read().decode("utf-8")
            root = ET.fromstring(xml_text)
            entry = root.find(f"{{{_ATOM_NS}}}entry")
            if entry is None:
                return None
            authors = [
                a.findtext(f"{{{_ATOM_NS}}}name", "")
                for a in entry.findall(f"{{{_ATOM_NS}}}author")
            ]
            categories = [
                c.get("term", "")
                for c in entry.findall(f"{{{_ATOM_NS}}}category")
            ]
            summary_el = entry.find(f"{{{_ATOM_NS}}}summary")
            abstract = summary_el.text.strip() if summary_el is not None else ""
            published_el = entry.find(f"{{{_ATOM_NS}}}published")
            published = published_el.text[:7] if published_el is not None else ""  # YYYY-MM
            pdf_link_el = entry.find(f"{{{_ATOM_NS}}}link[@title='pdf']")
            pdf_url = pdf_link_el.get("href", "") if pdf_link_el is not None else ""
            return {
                "abstract": abstract,
                "authors": authors,
                "categories": categories,
                "published": published,
                "pdf_url": pdf_url,
            }
        except Exception as exc:
            if attempt < retries:
                time.sleep(2 ** attempt)
            else:
                return {"_error": str(exc)}
    return None


# ─── Relevance helpers (file-specific) ─────────────────────────────────────────

DEFAULT_KEYWORDS = ["survey", "review", "benchmark", "evaluation", "method", "model"]


def relevance_tier(score: int) -> str:
    if score >= 3:
        return "Tier 1 – Core"
    if score == 2:
        return "Tier 2 – High Relevance"
    if score == 1:
        return "Tier 3 – Related"
    return "Tier 4 – Peripheral"


# ─── arXiv JSON parsing ────────────────────────────────────────────────────

def load_arxiv_json(path: str) -> list[dict]:
    """Load arxiv_results.json, tolerating several common formats."""
    with open(path) as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        # Some exports wrap results under a key like "results" or "papers"
        for key in ("results", "papers", "data", "items"):
            if key in raw:
                raw = raw[key]
                break
    if not isinstance(raw, list):
        raise ValueError(
            f"Expected list of papers in {path}, got {type(raw).__name__}. "
            "Wrapped JSON may need --top-level-key"
        )
    return raw


# ─── Core report builder ────────────────────────────────────────────────────

def build_corpus_report(
    arxiv_json_path: str,
    papers_dir: str = "papers",
    topic_keywords: list[str] | None = None,
    core_keywords: list[str] | None = None,
    context_keywords: list[str] | None = None,
    enrich: bool = False,
    enrich_batch_size: int = 5,
    enrich_delay: float = 3.0,
) -> dict:
    """
    Main report builder.

    For every paper in arxiv_json_path:
      1. Check if PDF exists locally (papers_dir)
      2. Optionally enrich via arXiv API (abstract / categories)
      3. Score relevance
      4. Assign tier
    """
    papers_dir = Path(papers_dir)
    keyword_list = topic_keywords or DEFAULT_KEYWORDS

    papers = load_arxiv_json(arxiv_json_path)
    report = {
        "generated_at": datetime.now().isoformat(),
        "arxiv_json": arxiv_json_path,
        "papers_dir": str(papers_dir),
        "keywords_used": keyword_list,
        "total_papers": len(papers),
        "tiers": {
            "Tier 1 – Core": [],
            "Tier 2 – High Relevance": [],
            "Tier 3 – Related": [],
            "Tier 4 – Peripheral": [],
        },
        "pdf_status": {"available": [], "missing": []},
        "all_papers": [],
    }

    unavailable_ids = []

    for idx, entry in enumerate(papers):
        arxiv_id = entry.get("id") or entry.get("arxiv_id", "")
        title = entry.get("title", "Untitled")
        published = entry.get("published", "")[:7]  # YYYY-MM
        authors = entry.get("authors", [])

        # Check PDF
        pdf_name = f"{arxiv_id}.pdf"
        pdf_path = papers_dir / pdf_name
        has_pdf = pdf_path.exists()

        # Build enriched record
        record = {
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors if isinstance(authors, list) else [authors],
            "published": published,
            "has_pdf": has_pdf,
            "pdf_path": str(pdf_path) if has_pdf else None,
            "score": 0,
            "tier": "Tier 4 – Peripheral",
            "matched_keywords": [],
            "abstract": entry.get("abstract", ""),
            "categories": entry.get("categories", []),
        }

        if not has_pdf:
            unavailable_ids.append(arxiv_id)

        # Score relevance
        score, matched = compute_relevance_score(
            title=title,
            abstract=record["abstract"],
            categories=record["categories"],
            keywords=keyword_list,
            core_keywords=core_keywords,
            context_keywords=context_keywords,
        )
        record["score"] = score
        record["tier"] = relevance_tier(score)
        record["matched_keywords"] = matched[:8]  # cap for readability

        report["tiers"][record["tier"]].append(arxiv_id)
        if has_pdf:
            report["pdf_status"]["available"].append(arxiv_id)
        else:
            report["pdf_status"]["missing"].append(arxiv_id)
        report["all_papers"].append(record)

    # ── arXiv API enrichment (optional, batched) ──────────────────────────
    if enrich:
        missing_abstract = [
            p for p in report["all_papers"]
            if not p["abstract"] and p["arxiv_id"] in unavailable_ids
        ]
        if not missing_abstract:
            print("  No papers need enrichment (all have abstracts or PDFs).")
        else:
            print(f"  Enriching {len(missing_abstract)} papers via arXiv API...")
            for i in range(0, len(missing_abstract), enrich_batch_size):
                batch = missing_abstract[i:i + enrich_batch_size]
                for rec in batch:
                    meta = fetch_arxiv_metadata(rec["arxiv_id"])
                    if meta and "_error" not in meta:
                        rec["abstract"] = meta.get("abstract", "")
                        rec["categories"] = meta.get("categories", [])
                        rec["published"] = meta.get("published", rec["published"])
                        rec["pdf_url"] = meta.get("pdf_url", "")
                        # Re-score with new abstract
                        score, matched = compute_relevance_score(
                            title=rec["title"],
                            abstract=rec["abstract"],
                            categories=rec["categories"],
                            keywords=keyword_list,
                            core_keywords=core_keywords,
                            context_keywords=context_keywords,
                        )
                        old_tier = rec["tier"]
                        rec["score"] = score
                        rec["tier"] = relevance_tier(score)
                        rec["matched_keywords"] = matched[:8]
                        if old_tier != rec["tier"]:
                            # Move between tier lists
                            report["tiers"][old_tier].remove(rec["arxiv_id"])
                            report["tiers"][rec["tier"]].append(rec["arxiv_id"])
                        print(f"    Enriched {rec['arxiv_id']}: tier={rec['tier']}")
                    else:
                        print(f"    Failed to enrich {rec['arxiv_id']}: {meta.get('_error','?')}")
                if i + enrich_batch_size < len(missing_abstract):
                    time.sleep(enrich_delay)

    # Summary stats
    report["summary"] = {
        "total": len(papers),
        "with_pdf": len(report["pdf_status"]["available"]),
        "missing_pdf": len(report["pdf_status"]["missing"]),
        "tier_counts": {tier: len(ids) for tier, ids in report["tiers"].items()},
    }

    return report


# ─── Markdown report generator ───────────────────────────────────────────────

TIER_ORDER = ["Tier 1 – Core", "Tier 2 – High Relevance",
               "Tier 3 – Related", "Tier 4 – Peripheral"]


def make_markdown_report(report: dict) -> str:
    lines = [
        "# SurveyMind Paper Corpus Report",
        "",
        f"**Generated**: {report['generated_at']}",
        f"**Source**: `{report['arxiv_json']}`",
        f"**Papers Dir**: `{report['papers_dir']}`",
        f"**Keywords**: `{'`, `'.join(report['keywords_used'])}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total papers | {report['summary']['total']} |",
        f"| PDFs available | {report['summary']['with_pdf']} |",
        f"| PDFs missing | {report['summary']['missing_pdf']} |",
        "",
    ]
    for tier in TIER_ORDER:
        count = len(report["tiers"].get(tier, []))
        pct = count / max(report["summary"]["total"], 1) * 100
        lines.append(f"| {tier} | {count} ({pct:.0f}%) |")
    lines += ["", "## Tier Details", ""]

    for tier in TIER_ORDER:
        ids = report["tiers"].get(tier, [])
        if not ids:
            lines.append(f"### {tier}\n*None*\n")
            continue
        lines.append(f"### {tier} ({len(ids)} papers)\n")
        # Build lookup
        lookup = {p["arxiv_id"]: p for p in report["all_papers"]}
        for arid in ids:
            p = lookup.get(arid, {})
            title = p.get("title", "Unknown")
            authors = p.get("authors", [])
            author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
            year = p.get("published", "")[:4]
            has_pdf = "📄" if p.get("has_pdf") else "❌"
            matched = ", ".join(f"`{m}`" for m in p.get("matched_keywords", [])[:6])
            lines.append(
                f"- {has_pdf} `{arid}` **{title}** ({year}) — {author_str}\n"
                f"  Keywords: {matched}"
            )
        lines.append("")

    lines += [
        "## PDFs Missing",
        "",
        f"These {len(report['pdf_status']['missing'])} papers have no local PDF:",
        "",
    ]
    lookup = {p["arxiv_id"]: p for p in report["all_papers"]}
    for arid in report["pdf_status"]["missing"]:
        p = lookup.get(arid, {})
        lines.append(f"- `{arid}` — {p.get('title', '?')[:80]}")
    lines.append("")

    return "\n".join(lines)


# ─── CLI ───────────────────────────────────────────────────────────────────

def parse_keywords(s: str) -> list[str]:
    return [k.strip() for k in s.split(",") if k.strip()]


def main():
    ap = argparse.ArgumentParser(
        description="SurveyMind arXiv JSON Paper Processor"
    )
    ap.add_argument(
        "--input", "-i", required=True,
        help="Path to arxiv_results.json (or similar wrap paper list)"
    )
    ap.add_argument(
        "--papers-dir", "-p", default="papers",
        help="Directory containing downloaded PDFs (default: papers/)"
    )
    ap.add_argument(
        "--topic-keywords", "-k",
        default="",
        help="Comma-separated topic keywords for relevance scoring (overrides profile keywords)"
    )
    ap.add_argument(
        "--domain-profile",
        default="templates/domain_profiles/general_profile.json",
        help="Domain profile JSON path"
    )
    ap.add_argument(
        "--output", "-o", default="corpus_report",
        help="Base name for output files (default: corpus_report)"
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Parse and score only; do not fetch from arXiv API"
    )
    ap.add_argument(
        "--enrich-from-arxiv", "-e", action="store_true",
        help="Fetch abstract/categories from arXiv API for papers missing PDFs"
    )
    ap.add_argument(
        "--enrich-batch-size", type=int, default=5,
        help="Batch size for arXiv API enrichment (default: 5)"
    )
    ap.add_argument(
        "--enrich-delay", type=float, default=3.0,
        help="Seconds between API batches to respect rate limits (default: 3.0)"
    )
    ap.add_argument(
        "--top-level-key",
        help="If JSON wraps list under a key, specify it (e.g. 'results')"
    )

    args = ap.parse_args()

    # Resolve papers dir relative to this file's location
    tools_dir = Path(__file__).parent
    root_dir = tools_dir.parent
    papers_dir = (root_dir / args.papers_dir).resolve()
    input_path = (root_dir / args.input).resolve()

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        profile, profile_path = load_domain_profile(args.domain_profile, root_dir)
    except DomainProfileError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    keywords = parse_keywords(args.topic_keywords) or profile_keywords(profile)
    core_keywords = profile_core_keywords(profile)
    context_keywords = profile_context_keywords(profile)

    print("SurveyMind arxiv_json_extractor")
    print(f"  Input:   {input_path}")
    print(f"  Papers:  {papers_dir}")
    print(f"  Profile: {profile_path}")
    print(f"  Keywords: {','.join(keywords[:8])}")
    print(f"  Dry run: {args.dry_run}")
    if args.enrich_from_arxiv and not args.dry_run:
        print(f"  Enrich:  yes (batch={args.enrich_batch_size}, delay={args.enrich_delay}s)")

    try:
        report = build_corpus_report(
            arxiv_json_path=str(input_path),
            papers_dir=str(papers_dir),
            topic_keywords=keywords,
            core_keywords=core_keywords,
            context_keywords=context_keywords,
            enrich=args.enrich_from_arxiv and not args.dry_run,
            enrich_batch_size=args.enrich_batch_size,
            enrich_delay=args.enrich_delay,
        )
    except Exception as exc:
        print(f"ERROR building report: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Write JSON report ────────────────────────────────────────────────
    out_json = Path(args.output + ".json")
    with open(out_json, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nJSON report → {out_json}")

    # ── Write Markdown report ─────────────────────────────────────────────
    md_text = make_markdown_report(report)
    out_md = Path(args.output + ".md")
    with open(out_md, "w") as f:
        f.write(md_text)
    print(f"Markdown report → {out_md}")

    # ── Summary ───────────────────────────────────────────────────────────
    s = report["summary"]
    print(f"\n{'='*50}")
    print(f"Total:    {s['total']}")
    print(f"PDFs:     {s['with_pdf']} available, {s['missing_pdf']} missing")
    for tier in TIER_ORDER:
        print(f"  {tier}: {s['tier_counts'].get(tier, 0)}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
