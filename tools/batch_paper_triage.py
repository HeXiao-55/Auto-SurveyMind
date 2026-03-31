#!/usr/bin/env python3
"""
batch_paper_triage.py — SurveyMind Batch Paper Triage

Reads an arxiv JSON file, runs multi-field classification on every paper,
and produces a complete coverage report mapping all papers to survey_trace
subsections.

Designed to be reusable for ANY survey — routing rules are parameterised
via --routing-config or built-in defaults.

Usage
-----
    # Triage all papers in arxiv JSON
    python3 tools/batch_paper_triage.py \\
        --input tpami_tem/arxiv_results.json \\
        --output all_papers_triage.json

    # Tier 1 only (Priority)
    python3 tools/batch_paper_triage.py \\
        --input tpami_tem/arxiv_results.json \\
        --tier-filter 1 \\
        --output tier1_triage.json

    # With API delay control
    python3 tools/batch_paper_triage.py \\
        --input tpami_tem/arxiv_results.json \\
        --delay 2.0

Exit codes
    0  success
    1  input not found / parse error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from arxiv_client import fetch_metadata
from domain_profile import (
    DomainProfileError,
    load_domain_profile,
    profile_context_keywords,
    profile_core_keywords,
    profile_framework_anchor_terms,
    profile_keywords,
    profile_routing_fallback,
    profile_routing_rules,
)
from triage_core import (
    DEFAULT_ROUTING_RULES,
    classify_12field,
    route_paper,
)

# ─── arXiv API — delegated to tools/arxiv_client.py ────────────────────────────



# ─── Batch helpers ───────────────────────────────────────────────────────────────

def build_framework_vocabulary(rules: list[dict], anchor_terms: list[str] | None = None) -> set[str]:
    """Build a loose keyword pool from routing rules for framework-aware pruning."""
    vocab: set[str] = set()
    for rule in rules:
        for key in ("training", "method", "bits"):
            for item in rule.get(key, []) or []:
                text = str(item).lower()
                vocab.add(text)
                for tok in re.findall(r"[a-z0-9\.\-\+]+", text):
                    if len(tok) >= 3:
                        vocab.add(tok)
    for term in anchor_terms or []:
        term = str(term).strip().lower()
        if term:
            vocab.add(term)
    return vocab


def framework_match_keywords(text: str, framework_vocab: set[str]) -> list[str]:
    hits = [kw for kw in framework_vocab if kw and kw in text]
    # Deterministic order for stable outputs.
    return sorted(hits)[:12]


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


# ─── Main ─────────────────────────────────────────────────────────────────

def load_arxiv_json(path: str) -> list[dict]:
    with open(path) as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        for key in ("results", "papers", "data", "items"):
            if key in raw:
                raw = raw[key]
                break
    if not isinstance(raw, list):
        raise ValueError(f"Expected list of papers in {path}")
    return raw


def build_triage_report(
    arxiv_json_path: str,
    output_path: str,
    keywords: list[str],
    core_keywords: list[str] | None = None,
    context_keywords: list[str] | None = None,
    routing_config_path: str | None = None,
    profile_routing_rules_data: list[dict] | None = None,
    fallback_subsection: str = "02/01_general_related_work",
    framework_anchor_terms: list[str] | None = None,
    tier_filter: int | None = None,
    min_score: int = 0,
    coarse_prune: bool = True,
    delay: float = 1.0,
    verbose: bool = False,
) -> dict:
    papers = load_arxiv_json(arxiv_json_path)
    rules = load_routing_config(routing_config_path) if routing_config_path else (profile_routing_rules_data or DEFAULT_ROUTING_RULES)
    framework_vocab = build_framework_vocabulary(rules, framework_anchor_terms)

    results = []
    tier_counts = {"Tier 1 – Core": 0, "Tier 2 – High Relevance": 0,
                   "Tier 3 – Related": 0, "Tier 4 – Peripheral": 0}
    subsection_counts = {}
    kept_count = 0
    pruned_count = 0

    for i, entry in enumerate(papers):
        arid = entry.get("id") or entry.get("arxiv_id", "")
        if not arid:
            continue

        # Progress indicator every 10 papers
        if verbose and (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(papers)}] processed...")

        paper = fetch_metadata(arid)
        if paper is None:
            results.append({
                "arxiv_id": arid,
                "title": entry.get("title", "Unknown"),
                "status": "error",
                "error": "not found on arXiv",
                "classification": None,
                "subsection": None,
            })
            if delay > 0:
                time.sleep(delay)
            continue

        # Convert ArxivPaper to dict for backward compatibility with classify_12field
        meta = {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "abstract": paper.abstract,
            "authors": paper.authors,
            "categories": paper.categories,
            "published": paper.published,
            "pdf_url": paper.pdf_url,
        }

        classification = classify_12field(
            meta,
            keywords,
            core_keywords=core_keywords,
            context_keywords=context_keywords,
        )
        subsection = route_paper(classification, rules, fallback_subsection)
        text = (meta.get("title", "") + " " + meta.get("abstract", "")).lower()
        fw_hits = framework_match_keywords(text, framework_vocab)
        classification["framework_match_count"] = len(fw_hits)
        classification["framework_matched_keywords"] = fw_hits

        # Coarse prune policy: keep high recall, only remove clearly irrelevant.
        # Clearly irrelevant = below min_score and no framework evidence.
        keep = True
        if coarse_prune:
            keep = (classification["relevance_score"] >= min_score) or bool(fw_hits)
        else:
            keep = classification["relevance_score"] >= min_score

        if tier_filter is not None:
            if classification["relevance_score"] < 3 and tier_filter == 1:
                if delay > 0:
                    time.sleep(0.5)
                continue

        if keep:
            kept_count += 1
        else:
            pruned_count += 1

        if not keep:
            results.append({
                "arxiv_id": arid,
                "title": meta.get("title", ""),
                "authors": meta.get("authors", []),
                "published": meta.get("published", ""),
                "categories": meta.get("categories", []),
                "pdf_url": meta.get("pdf_url", ""),
                "status": "pruned_irrelevant",
                "classification": classification,
                "subsection": subsection,
            })
            if delay > 0:
                time.sleep(delay)
            continue

        tier = classification["relevance_tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        subsection_counts[subsection] = subsection_counts.get(subsection, 0) + 1

        results.append({
            "arxiv_id": arid,
            "title": meta.get("title", ""),
            "authors": meta.get("authors", []),
            "published": meta.get("published", ""),
            "categories": meta.get("categories", []),
            "pdf_url": meta.get("pdf_url", ""),
            "status": "ok",
            "classification": classification,
            "subsection": subsection,
        })

        if delay > 0:
            time.sleep(delay)

    report = {
        "generated_at": datetime.now().isoformat(),
        "source": arxiv_json_path,
        "total": len(papers),
        "kept": kept_count,
        "pruned": pruned_count,
        "coarse_prune": coarse_prune,
        "min_score": min_score,
        "tier_counts": tier_counts,
        "subsection_counts": subsection_counts,
        "papers": results,
    }

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


# ─── CLI ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="SurveyMind Batch Paper Triage")
    ap.add_argument("--input", "-i", required=True, help="Input arxiv JSON file")
    ap.add_argument("--output", "-o", default="batch_triage.json",
                   help="Output JSON path (default: batch_triage.json)")
    ap.add_argument("--tier-filter", type=int, choices=[1, 2, 3, 4],
                   help="Only process papers of this tier (1-4)")
    ap.add_argument("--topic-keywords", "-k",
                   default="",
                   help="Comma-separated topic keywords (overrides profile keywords)")
    ap.add_argument("--domain-profile",
                   default="templates/domain_profiles/general_profile.json",
                   help="Domain profile JSON path")
    ap.add_argument("--routing-config", "-r",
                   help="JSON routing config (default: built-in ultra-low bit rules)")
    ap.add_argument("--min-score", type=int, choices=[0, 1, 2, 3], default=0,
                   help="Keep papers with relevance_score >= min-score (default: 0)")
    ap.add_argument("--coarse-prune", action=argparse.BooleanOptionalAction, default=True,
                   help="Enable framework-aware coarse pruning (default: on)")
    ap.add_argument("--delay", type=float, default=1.0,
                   help="Seconds between API calls (default: 1.0, use 0 to disable)")
    ap.add_argument("--verbose", "-v", action="store_true")

    args = ap.parse_args()

    tools_dir = Path(__file__).parent
    root_dir = tools_dir.parent
    input_path = (root_dir / args.input).resolve()

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = (root_dir / args.output).resolve()

    try:
        profile, profile_path = load_domain_profile(args.domain_profile, root_dir)
    except DomainProfileError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    keywords = [k.strip() for k in args.topic_keywords.split(",") if k.strip()] or profile_keywords(profile)
    core_keywords = profile_core_keywords(profile)
    context_keywords = profile_context_keywords(profile)
    fallback_subsection = profile_routing_fallback(profile, "02/01_general_related_work")
    profile_rules = profile_routing_rules(profile)
    anchor_terms = profile_framework_anchor_terms(profile)

    print("SurveyMind batch_paper_triage")
    print(f"  Input:   {input_path}")
    print(f"  Output:  {output_path}")
    print(f"  Profile: {profile_path}")
    print(f"  Keywords:{','.join(keywords[:8])}")
    print(f"  Delay:   {args.delay}s between API calls")
    if args.tier_filter:
        print(f"  Filter:  Tier {args.tier_filter} only")
    print(f"  Coarse:  {'on' if args.coarse_prune else 'off'} (min-score={args.min_score})")

    report = build_triage_report(
        arxiv_json_path=str(input_path),
        output_path=str(output_path),
        keywords=keywords,
        core_keywords=core_keywords,
        context_keywords=context_keywords,
        routing_config_path=args.routing_config,
        profile_routing_rules_data=profile_rules,
        fallback_subsection=fallback_subsection,
        framework_anchor_terms=anchor_terms,
        tier_filter=args.tier_filter,
        min_score=args.min_score,
        coarse_prune=args.coarse_prune,
        delay=args.delay,
        verbose=args.verbose,
    )

    print(f"\n{'='*50}")
    print(f"Total:    {report['total']}")
    print(f"Kept:     {report['kept']}")
    print(f"Pruned:   {report['pruned']}")
    for tier, count in report['tier_counts'].items():
        print(f"  {tier}: {count}")
    print("\nSubsection distribution:")
    for sub, count in sorted(report['subsection_counts'].items(), key=lambda x: -x[1]):
        print(f"  {sub}: {count}")
    print(f"{'='*50}")
    print(f"Output → {output_path}")


if __name__ == "__main__":
    main()
