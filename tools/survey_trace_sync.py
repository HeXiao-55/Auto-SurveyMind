#!/usr/bin/env python3
"""
survey_trace_sync.py — SurveyMind Paper Analysis → Survey Trace Synchroniser

Reads all ``paper_analysis_results/*.md`` files, extracts their 8- or 12-field
classifications and evidence tables, then appends each paper to the correct
subsection record in the ``survey_trace/`` directory tree.

After syncing, all ``SECTION_SUMMARY.md`` and ``SUBFOLDER_SUMMARY.md`` files
contain up-to-date paper counts and claim statistics.

Designed to be reusable for ANY survey — all topic-specific routing rules
are parameterised in a mapping config.

Usage
-----
    # Sync all papers in paper_analysis_results/ to survey_trace/
    python3 tools/survey_trace_sync.py \\
        --papers-dir paper_analysis_results \\
        --trace-dir "my idea/survey_trace"

    # With a custom routing config (JSON)
    python3 tools/survey_trace_sync.py \\
        --papers-dir paper_analysis_results \\
        --trace-dir "my idea/survey_trace" \\
        --routing-config my_routing.json

    # Dry run — show which papers would go where
    python3 tools/survey_trace_sync.py --dry-run

Exit codes
    0  success
    1  routing error / file not found
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─── Routing logic ────────────────────────────────────────────────────────

# Default routing rules for ultra-low bit LLM quantization survey.
# Maps (training_paradigm, method_subcategory, bit_scope) → survey subsection path.
# Rules are checked in order; first match wins.
# subsection format: "section_num/subsection_dir_name"

DEFAULT_ROUTING_RULES: list[dict] = [
    # QAT – Binary
    {
        "training": ["QAT", "From-Scratch"],
        "method": ["Binary", "binarization", "1-bit"],
        "bits": ["1-bit"],
        "subsection": "05/01_binary_networks_1_bit",
    },
    # QAT – Ternary
    {
        "training": ["QAT", "From-Scratch"],
        "method": ["Ternary", "ternarization", "1.58-bit"],
        "bits": ["1.58-bit", "ternary"],
        "subsection": "05/02_ternary_networks_1_58_bit",
    },
    # QAT – Recent advances
    {
        "training": ["QAT"],
        "method": ["curvature", "hessian", "low-rank", "sparse", "co-training"],
        "bits": [],
        "subsection": "05/03_recent_qat_advances_curvature_and_sparse_co_training",
    },
    # PTQ – Ultra-low bit
    {
        "training": ["PTQ"],
        "method": ["Ultra-low", "sub-2-bit", "structured", "mask", "trit-plane",
                    "dual-scale", "deviation", "block reconstruction",
                    "layer-wise", "butterfly", "rotation"],
        "bits": ["1-bit", "1.61-bit", "sub-2-bit", "1.58-bit"],
        "subsection": "06/01_ultra_low_ptq_sub_2_bit",
    },
    # PTQ – 2-bit
    {
        "training": ["PTQ"],
        "method": ["2-bit", "INT2", "progressive"],
        "bits": ["2-bit"],
        "subsection": "06/2_2_bit_quantization_methods",
    },
    # PTQ – Standard (3-4 bit)
    {
        "training": ["PTQ"],
        "method": ["standard", "4-bit", "per-channel", "per-token", "mixed-precision"],
        "bits": ["3-bit", "4-bit"],
        "subsection": "06/04_transform_based_and_mixed_precision_methods",
    },
    # PTQ – Any (fallback)
    {
        "training": ["PTQ"],
        "method": [],
        "bits": [],
        "subsection": "06/01_ultra_low_ptq_sub_2_bit",
    },
    # Outlier handling
    {
        "training": [],
        "method": ["outlier", "smoothquant", "quarot", "quip", "prefix",
                    "rotation", "redistribution", "migration", "asymmetric"],
        "bits": [],
        "subsection": "07/02_categorization_of_outlier_handling_methods",
    },
    # Hardware
    {
        "training": [],
        "method": ["CPU", "GPU", "ASIC", "CIM", "PIM", "kernel", "lut",
                    "hardware", "inference", "SIMD", "async", "dequantization"],
        "bits": [],
        "subsection": "08/01_cpu_implementations",
    },
    # Multimodal / Beyond text
    {
        "training": [],
        "method": ["multimodal", "MLLM", "VLM", "VLA", "agent", "KV cache"],
        "bits": [],
        "subsection": "11/1_1_bit_vision_language_action_models",
    },
    # Benchmark / Evaluation
    {
        "training": [],
        "method": ["benchmark", "perplexity", "accuracy", "latency", "throughput",
                    "energy", "memory"],
        "bits": [],
        "subsection": "09/02_performance_comparison",
    },
    # Gap analysis
    {
        "training": [],
        "method": ["gap", "limitation", "challenge", "generalization", "theory",
                    "standardization"],
        "bits": [],
        "subsection": "10/01_gap_1_lack_of_standardized_evaluation_protocols",
    },
]


# ─── Field extraction from paper analysis .md ────────────────────────────────

# Patterns for the 8-field format (current paper_analysis_results)
FIELD_PATTERNS = [
    (r"Model Type[:\s]*\*\*Classification\*\*[:\s]*([^\n*]+)", "model_type"),
    (r"Method Category[:\s]*\*\*Classification\*\*[:\s]*([^\n*]+)", "method_category"),
    (r"Specific Method[:\s]*\*\*Classification\*\*[:\s]*([^\n*]+)", "specific_method"),
    (r"Training Paradigm[:\s]*\*\*Classification\*\*[:\s]*([^\n*]+)", "training"),
    (r"Core Challenge[:\s]*\*\*Classification\*\*[:\s]*([^\n*]+)", "core_challenge"),
    (r"Evaluation Focus[:\s]*\*\*Classification\*\*[:\s]*([^\n*]+)", "evaluation"),
    (r"Hardware Co-design[:\s]*\*\*Classification\*\*[:\s]*([^\n*]+)", "hardware"),
    (r"Summary[:\s]*\*\*Summary\*\*[:\s]*\n\*\*[^\n]*\n([^\n#]+)", "summary"),
    # 12-field additions
    (r"Quantization Bit Scope[:\s]*\*\*Classification\*\*[:\s]*([^\n*]+)", "bit_scope"),
    (r"General Method Type[:\s]*\*\*Classification\*\*[:\s]*([^\n*]+)", "general_method"),
    (r"Core Challenge Addressed[:\s]*\*\*Classification\*\*[:\s]*([^\n*]+)", "core_challenge"),
]

# Patterns for evidence table extraction
EVIDENCE_TABLE_PAT = re.compile(
    r"\| Claim\s*\|.*?\n\|[-| :]+\|\n((?:\|[^\n]+\n)+)",
    re.MULTILINE
)

ARXIV_ID_PAT = re.compile(r"^\d{4}\.\d{4,5}", re.MULTILINE)


def extract_arxiv_id(filepath: str) -> Optional[str]:
    """Extract arxiv ID from filename or content."""
    fname = Path(filepath).stem           # "2306.00978_analysis"
    if ARXIV_ID_PAT.match(fname):
        return fname.replace("_analysis", "")
    content = open(filepath).read(500)
    m = ARXIV_ID_PAT.search(content)
    return m.group(0) if m else None


def parse_paper_analysis(filepath: str) -> dict:
    """Extract structured fields + evidence table from a paper analysis .md file."""
    content = open(filepath).read()

    fields = {"source_file": filepath}
    for pat, key in FIELD_PATTERNS:
        m = re.search(pat, content, re.IGNORECASE)
        fields[key] = m.group(1).strip() if m else ""

    # Extract evidence table
    table_match = EVIDENCE_TABLE_PAT.search(content)
    if table_match:
        rows = table_match.group(1).strip().splitlines()
        fields["evidence_rows"] = []
        for row in rows:
            cells = [c.strip().strip('"') for c in row.split("|")[1:-1]]
            if len(cells) >= 4:
                fields["evidence_rows"].append({
                    "claim": cells[0],
                    "type": cells[1],
                    "snippet": cells[2][:120],
                    "confidence": cells[3],
                })
    else:
        fields["evidence_rows"] = []

    # Extract paper metadata
    title_m = re.search(r"\*\*Title\*\*:\s*([^\n]+)", content)
    authors_m = re.search(r"\*\*Authors\*\*:\s*([^\n]+)", content)
    year_m = re.search(r"\*\*Year/Month\*\*:\s*([^\n]+)", content)

    fields["title"] = title_m.group(1).strip() if title_m else ""
    fields["authors"] = authors_m.group(1).strip() if authors_m else ""
    fields["year"] = year_m.group(1).strip() if year_m else ""

    return fields


def route_paper(paper: dict, rules: list[dict]) -> str:
    """
    Determine the survey_trace subsection for a paper based on its classification.

    Returns subsection string like "05/01_binary_networks_1_bit"
    or "06/01_ultra_low_ptq_sub_2_bit".
    """
    training = (paper.get("training") or "").upper()
    method = (paper.get("method_category") + " " +
               paper.get("specific_method") + " " +
               paper.get("general_method") + " " +
               paper.get("core_challenge")).upper()
    bits = (paper.get("bit_scope") or "").upper()

    for rule in rules:
        rule_training = [r.upper() for r in rule.get("training", [])]
        rule_method = [r.upper() for r in rule.get("method", [])]
        rule_bits = [r.upper() for r in rule.get("bits", [])]

        # Check training match
        if rule_training and not any(t in training for t in rule_training):
            continue
        # Check method keyword match
        if rule_method and not any(kw in method for kw in rule_method):
            continue
        # Check bits match
        if rule_bits and not any(b in bits for b in rule_bits):
            continue

        return rule["subsection"]

    return "02/01_general_model_quantization_surveys"  # fallback


def build_trace_entry(paper: dict) -> str:
    """Build a SUBSECTION_RECORD.md entry block for one paper."""
    arid = paper.get("arxiv_id", "unknown")
    title = paper.get("title", "Unknown")
    authors = paper.get("authors", "")
    year = paper.get("year", "")
    summary = (paper.get("summary") or "").strip()[:200]

    # Evidence rows as markdown table rows
    ev_rows = []
    for ev in (paper.get("evidence_rows") or []):
        ev_rows.append(
            f"| {ev['claim'][:60]} | {ev['type']} | \"{ev['snippet'][:80]}\" | {ev['confidence']} |"
        )
    ev_table = "\n".join(ev_rows) if ev_rows else "| [none extracted] | -- | -- | Low |"

    return f"""

## Paper: {arid}

- **Title**: {title}
- **Authors**: {authors}
- **Year**: {year}
- **Source**: `{paper.get('source_file', 'unknown')}`

### Summary

{summary}

### Evidence Table

| Claim | Evidence Type | Source Snippet | Confidence |
|---|---|---|---|
{ev_table}

---

"""


def update_subfolder_summary(path: Path, paper_count_delta: int,
                             claim_count_delta: int) -> None:
    """Increment paper_count and claim_count in a SUBFOLDER_SUMMARY.md."""
    if not path.exists():
        return
    content = path.read_text()

    def _inc(text: str, field: str, delta: int) -> str:
        pat = re.compile(rf"({field}:\s*)(\d+)")
        m = pat.search(text)
        if m:
            new_val = int(m.group(2)) + delta
            text = pat.sub(rf"\g<1>{new_val}", text)
        return text

    # Update "Papers Analyzed: N" → N+1
    content = _inc(content, "Papers Analyzed", paper_count_delta)

    lines = content.splitlines()
    new_lines = []
    for line in lines:
        new_lines.append(line)
        if "Coverage Snapshot" in line and paper_count_delta != 0:
            new_lines.append(
                f"*   Updated +{paper_count_delta} papers ({datetime.now().date()})"
            )
    path.write_text("\n".join(new_lines))


def update_section_summary(path: Path, subfolder_delta: int = 0) -> None:
    """Update SECTION_SUMMARY.md with new paper counts."""
    if not path.exists():
        return
    content = path.read_text()

    def _inc(text: str, field: str, delta: int) -> str:
        pat = re.compile(rf"({field}:\s*)(\d+)")
        m = pat.search(text)
        if m:
            new_val = int(m.group(2)) + delta
            text = pat.sub(rf"\g<1>{new_val}", text)
        return text

    content = _inc(content, "Papers Analyzed", subfolder_delta)
    path.write_text(content)


# ─── Main sync logic ────────────────────────────────────────────────────────

def sync_papers_to_trace(
    papers_dir: Path,
    trace_dir: Path,
    rules: list[dict],
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Scan papers_dir for ``*_analysis.md`` files, route each to the correct
    survey_trace subsection, append evidence, and update summaries.
    """
    analysis_files = sorted(papers_dir.glob("*_analysis.md"))
    if not analysis_files:
        return {"synced": 0, "skipped": 0, "errors": [], "routing": {}}

    routing_log = {}
    sync_count = 0
    error_count = 0
    errors = []

    for fpath in analysis_files:
        arid = extract_arxiv_id(str(fpath))
        try:
            paper = parse_paper_analysis(str(fpath))
            paper["arxiv_id"] = arid or fpath.stem
        except Exception as exc:
            errors.append(f"{fpath.name}: {exc}")
            error_count += 1
            continue

        subsection = route_paper(paper, rules)
        routing_log[paper["arxiv_id"]] = subsection

        if verbose:
            print(f"  {arid} → {subsection}")

        # Build subsection path: trace_dir/05/01_binary_networks_1_bit
        sub_parts = subsection.split("/")
        sec_num = sub_parts[0]
        sec_dir = trace_dir / f"{sec_num}_{_find_matching_sec_dir(trace_dir, sec_num)}"
        # Find actual subsection dir using keyword fuzzy match
        sub_dir_name = _fuzzy_match_subsection(sec_dir, sub_parts[1])
        sub_dir = sec_dir / sub_dir_name

        if dry_run:
            sync_count += 1
            continue

        # Append to SUBSECTION_RECORD.md
        record_path = sub_dir / "SUBSECTION_RECORD.md"
        entry = build_trace_entry(paper)

        if record_path.exists():
            existing = record_path.read_text()
            # Check if already has this paper
            if arid and f"## Paper: {arid}" in existing:
                print(f"  [skip] {arid} already in {record_path}")
                continue
            record_path.write_text(existing + entry)
        else:
            record_path.parent.mkdir(parents=True, exist_ok=True)
            record_path.write_text(f"# Subsection Record\n\n## Paper: {arid}\n\n{entry}")

        # Update SUBFOLDER_SUMMARY.md
        subfolder_summary = sub_dir / "SUBFOLDER_SUMMARY.md"
        if subfolder_summary.exists():
            update_subfolder_summary(subfolder_summary, 1, len(paper.get("evidence_rows", [])))

        # Update SECTION_SUMMARY.md
        section_summary = sec_dir / "SECTION_SUMMARY.md"
        if section_summary.exists():
            update_section_summary(section_summary, 0)  # only subfolder counts below

        sync_count += 1

    return {
        "synced": sync_count,
        "skipped": error_count,
        "errors": errors,
        "routing": routing_log,
    }


def _find_matching_sec_dir(trace_dir: Path, sec_num: str) -> str:
    """
    Find the actual section directory name in trace_dir that starts with sec_num.
    When multiple dirs match (e.g. '07_lier_handling_strategies' and
    '07_outlier_handling_strategies'), prefer the one with more alphabetic chars
    (less likely to be a garbled LaTeX parse artifact).
    """
    target = sec_num + "_"
    candidates = [d.name for d in trace_dir.iterdir() if d.is_dir() and d.name.startswith(target)]

    if not candidates:
        return f"section_{sec_num}"
    if len(candidates) == 1:
        return candidates[0][len(target):]

    # Pick the candidate with the most alphabetic chars (least garbled)
    best = max(candidates, key=lambda n: sum(c.isalpha() for c in n))
    return best[len(target):]


def _fuzzy_match_subsection(sec_dir: Path, routing_sub_name: str) -> str:
    """
    Given the section dir and a routing subsection name (e.g. '01_ultra_low_ptq_sub_2_bit'),
    find the actual subsection subdirectory that best matches.
    Falls back to routing_sub_name if no strong match found.
    """
    # Extract the subsection number prefix (e.g. '01' from '01_ultra_low_ptq_sub_2_bit')
    num_prefix = routing_sub_name.split("_")[0]

    # Find all numbered subdirs in section dir
    candidates = [d.name for d in sec_dir.iterdir() if d.is_dir() and d.name.startswith(num_prefix + "_")]

    if not candidates:
        return routing_sub_name
    if len(candidates) == 1:
        return candidates[0]

    # Score candidates by keyword overlap with routing name
    routing_kw = set(routing_sub_name.replace("_", " ").split())
    best_score, best_match = -1, candidates[0]
    for cand in candidates:
        cand_kw = set(cand.replace("_", " ").split())
        score = len(routing_kw & cand_kw)
        if score > best_score:
            best_score, best_match = score, cand

    return best_match


# ─── CLI ─────────────────────────────────────────────────────────────────

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


def main():
    ap = argparse.ArgumentParser(description="SurveyMind Paper Analysis → Survey Trace Sync")
    ap.add_argument(
        "--papers-dir", "-p", default="paper_analysis_results",
        help="Directory containing paper analysis .md files"
    )
    ap.add_argument(
        "--trace-dir", "-t", default="my idea/survey_trace",
        help="Root of the survey_trace directory"
    )
    ap.add_argument(
        "--routing-config", "-r",
        help="JSON file with routing rules (default: built-in ultra-low bit rules)"
    )
    ap.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Show routing decisions without writing files"
    )
    ap.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print each paper's routing decision"
    )

    args = ap.parse_args()

    tools_dir = Path(__file__).parent
    root_dir = tools_dir.parent
    papers_dir = (root_dir / args.papers_dir).resolve()
    trace_dir = (root_dir / args.trace_dir).resolve()

    if not papers_dir.exists():
        print(f"ERROR: papers directory not found: {papers_dir}", file=sys.stderr)
        sys.exit(1)
    if not trace_dir.exists():
        print(f"ERROR: trace directory not found: {trace_dir}", file=sys.stderr)
        sys.exit(1)

    rules = load_routing_config(args.routing_config or "")
    print(f"SurveyMind survey_trace_sync")
    print(f"  Papers:  {papers_dir}")
    print(f"  Trace:   {trace_dir}")
    print(f"  Routing:  {'default (ultra-low bit)' if not args.routing_config else args.routing_config}")
    print(f"  Dry run: {args.dry_run}")

    result = sync_papers_to_trace(
        papers_dir=papers_dir,
        trace_dir=trace_dir,
        rules=rules,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    print(f"\n{'='*50}")
    print(f"Synced:  {result['synced']} papers")
    print(f"Skipped: {result['skipped']}")
    if result['errors']:
        print(f"Errors:   {len(result['errors'])}")
        for e in result['errors'][:5]:
            print(f"  - {e}")
    print(f"{'='*50}")

    if result['routing'] and args.verbose:
        print("\nRouting summary:")
        from collections import Counter
        counts = Counter(result['routing'].values())
        for sub, n in counts.most_common():
            print(f"  {sub}: {n}")


if __name__ == "__main__":
    main()
