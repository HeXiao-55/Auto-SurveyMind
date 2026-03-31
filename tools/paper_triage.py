#!/usr/bin/env python3
"""
paper_triage.py — SurveyMind Single-Paper 12-Field Triage + Routing

Given an arXiv ID, fetches metadata (title, abstract, categories) via the
arXiv API, performs 12-field classification, and outputs the recommended
survey_trace subsection path — all without requiring a local PDF.

Designed to be reusable for ANY survey topic — routing rules are
parameterised via --routing-config or built-in defaults.

Usage
-----
    # Triage a single paper
    python3 tools/paper_triage.py 2210.17323

    # With custom routing rules
    python3 tools/paper_triage.py 2210.17323 --routing-config my_routing.json

    # With verbose output
    python3 tools/paper_triage.py 2210.17323 --verbose

    # JSON output (machine-readable)
    python3 tools/paper_triage.py 2210.17323 --format json

    # Batch mode: multiple IDs
    python3 tools/paper_triage.py 2210.17323 2211.10438 2306.00978

Exit codes
    0  success
    1  arXiv ID not found / API error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from arxiv_client import fetch_metadata
from domain_profile import (
    DomainProfileError,
    load_domain_profile,
    profile_context_keywords,
    profile_core_keywords,
    profile_keywords,
    profile_routing_fallback,
    profile_routing_rules,
)
from triage_core import (
    DEFAULT_ROUTING_RULES,
    classify_12field,
    route_paper,
)

# ─── Routing config ───────────────────────────────────────────────────────────

def load_routing_config(path: str) -> list[dict]:
    if not path:
        return DEFAULT_ROUTING_RULES
    with open(path) as f:
        cfg = json.load(f)
    if isinstance(cfg, list):
        return cfg
    if "rules" in cfg:
        return cfg["rules"]
    return DEFAULT_ROUTING_RULES


# ─── Output formatters ────────────────────────────────────────────────────────

FIELD_LABELS = [
    ("model_type", "Model Type"),
    ("method_category", "Method Category"),
    ("specific_method", "Specific Method"),
    ("training", "Training Paradigm"),
    ("core_challenge", "Core Challenge"),
    ("evaluation", "Evaluation Focus"),
    ("hardware", "Hardware Co-design"),
    ("summary", "Summary"),
    ("bit_scope", "Quantization Bit Scope"),
    ("general_method", "General Method Type"),
    ("core_challenge_addressed", "Core Challenge Addressed"),
    ("survey_contribution", "Survey Contribution Mapping"),
]


def format_text(arxiv_id: str, meta: dict, fields: dict, subsection: str) -> str:
    """Human-readable text output."""
    lines = [
        f"arXiv ID:   {arxiv_id}",
        f"Title:      {meta.get('title', '?')}",
        f"Authors:    {', '.join(meta.get('authors', [])[:3])}{' et al.' if len(meta.get('authors', [])) > 3 else ''}",
        f"Published:  {meta.get('published', '?')}",
        f"Categories: {', '.join(meta.get('categories', [])[:5])}",
        f"PDF:        {meta.get('pdf_url', 'N/A')}",
        "",
        "── 12-Field Classification ──────────────────────────────",
        f"  [Tier {fields['relevance_score']}] {fields['relevance_tier']}",
        f"  Matched keywords: {', '.join(fields['matched_keywords'][:6])}",
        "",
    ]
    for key, label in FIELD_LABELS:
        val = fields.get(key, "")
        if val:
            lines.append(f"  {label}: {val}")

    lines.extend([
        "",
        "── Routing ──────────────────────────────────────────────",
        f"  → survey_trace: {subsection}",
    ])
    return "\n".join(lines)


def format_json(arxiv_id: str, meta: dict, fields: dict, subsection: str) -> str:
    """Machine-readable JSON output."""
    output = {
        "arxiv_id": arxiv_id,
        "title": meta.get("title", ""),
        "authors": meta.get("authors", []),
        "published": meta.get("published", ""),
        "categories": meta.get("categories", []),
        "pdf_url": meta.get("pdf_url", ""),
        "classification": fields,
        "survey_trace_subsection": subsection,
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


# ─── CLI ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="SurveyMind Single-Paper 12-Field Triage")
    ap.add_argument("arxiv_ids", nargs="+", help="One or more arXiv IDs (e.g. 2210.17323)")
    ap.add_argument("--routing-config", "-r", help="JSON routing config")
    ap.add_argument("--domain-profile",
                   default="templates/domain_profiles/general_profile.json",
                   help="Domain profile JSON path")
    ap.add_argument("--topic-keywords", "-k",
                   default="",
                   help="Comma-separated topic keywords (overrides profile keywords)")
    ap.add_argument("--format", "-f", choices=["text", "json"], default="text",
                   help="Output format (default: text)")
    ap.add_argument("--verbose", "-v", action="store_true")

    args = ap.parse_args()

    tools_dir = Path(__file__).parent
    root_dir = tools_dir.parent
    try:
        profile, profile_path = load_domain_profile(args.domain_profile, root_dir)
    except DomainProfileError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    keywords = [k.strip() for k in args.topic_keywords.split(",") if k.strip()] or profile_keywords(profile)
    core_keywords = profile_core_keywords(profile)
    context_keywords = profile_context_keywords(profile)
    rules = load_routing_config(args.routing_config or "") if args.routing_config else profile_routing_rules(profile)
    fallback_subsection = profile_routing_fallback(profile, "02/01_general_related_work")

    shown_keywords = ",".join(keywords[:6])
    print(f"SurveyMind paper_triage — {len(args.arxiv_ids)} paper(s), keywords: {shown_keywords}")
    print(f"Domain profile: {profile_path}")
    print()

    for arid in args.arxiv_ids:
        if args.verbose:
            print(f"Fetching {arid}...")

        paper = fetch_metadata(arid)
        if paper is None:
            print(f"ERROR: arXiv ID not found: {arid}", file=sys.stderr)
            continue

        # Convert ArxivPaper to plain dict for backward compatibility with classify_12field
        meta = {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "abstract": paper.abstract,
            "authors": paper.authors,
            "categories": paper.categories,
            "published": paper.published,
            "pdf_url": paper.pdf_url,
        }

        fields = classify_12field(
            meta,
            keywords,
            core_keywords=core_keywords,
            context_keywords=context_keywords,
        )
        subsection = route_paper(fields, rules, fallback_subsection)

        if args.format == "json":
            print(format_json(arid, meta, fields, subsection))
        else:
            print(format_text(arid, meta, fields, subsection))

        if not args.verbose:
            print()


if __name__ == "__main__":
    main()
