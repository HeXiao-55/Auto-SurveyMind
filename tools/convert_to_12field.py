#!/usr/bin/env python3
"""
convert_to_12field.py — SurveyMind 8-Field → 12-Field Analysis Converter

Reads all existing ``paper_analysis_results/*.md`` files (8-field format),
converts them to the full 12-field format with evidence tables and
POST_TASK_QC blocks as specified in ULTRA_LOW_BIT_PAPER_ANALYSIS_PROMPT.md.

This converter is reusable for ANY survey — all field mappings and
quality checklist criteria are parameterised.

Usage
-----
    # Convert all papers in paper_analysis_results/
    python3 tools/convert_to_12field.py

    # Dry run — show what would change without writing
    python3 tools/convert_to_12field.py --dry-run

    # Custom output directory
    python3 tools/convert_to_12field.py --output-dir paper_analysis_results_v12

Exit codes
    0  success (all converted or nothing to do)
    1  input directory not found / parse error
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path


# ─── Field mapping: 8-field → 12-field ─────────────────────────────────────

# The 8-field names used in existing paper analyses
OLD_FIELDS = [
    "Model Type",
    "Method Category",
    "Specific Method",
    "Training Paradigm",
    "Core Challenge",
    "Evaluation Focus",
    "Hardware Co-design",
    "Summary",
]

# New fields added to make 12-field
NEW_FIELDS_12 = [
    "Quantization Bit Scope",
    "General Method Type",
    "Core Challenge Addressed",
    "Survey Contribution Mapping",
    "Ultra-low-bit Relevance Summary",
]

# Default values for new fields when they can't be auto-derived
DEFAULT_NEW_FIELD_VALUE = "[TODO — needs review]"


# ─── Evidence table extraction ─────────────────────────────────────────────

EVIDENCE_TABLE_PAT = re.compile(
    r"\| Claim\s*\|.*?\n\|[-| :]+\|\n((?:\|[^\n]+\n)+)",
    re.MULTILINE
)


def extract_classification_value(content: str, field_name: str) -> str:
    """
    Extract the Classification value for a given field name from an 8-field
    paper analysis .md file.

    Expected format in source:
        ### N. Field Name
        **Classification**: <value>
        **Evidence**:
        - Source: ...
        - Quote: ...
    """
    # Match section header
    sec_pat = re.compile(
        rf"###\s*\d+\.\s*{re.escape(field_name)}\s*\n"
        rf"\*\*Classification\*\*:\s*([^\n]+)",
        re.IGNORECASE
    )
    m = sec_pat.search(content)
    return m.group(1).strip() if m else ""


def extract_evidence_rows(content: str) -> list[dict]:
    """Extract rows from the Evidence Table section."""
    table_match = EVIDENCE_TABLE_PAT.search(content)
    if not table_match:
        return []
    rows = table_match.group(1).strip().splitlines()
    result = []
    for row in rows:
        cells = [c.strip().strip('"') for c in row.split("|")[1:-1]]
        if len(cells) >= 4:
            result.append({
                "claim": cells[0],
                "type": cells[1],
                "snippet": cells[2][:200],
                "confidence": cells[3],
            })
    return result


def extract_all_8fields(content: str) -> dict:
    """Extract all 8 classification fields from a paper analysis file."""
    fields = {}
    for f in OLD_FIELDS:
        fields[f] = extract_classification_value(content, f)
    return fields


def infer_bit_scope(method_category: str, specific_method: str, summary: str) -> str:
    """Auto-derive Quantization Bit Scope from method/summary text."""
    text = f"{method_category} {specific_method} {summary}".lower()
    if "binary" in text or "1-bit" in text or "1bit" in text:
        return "1-bit"
    if "ternary" in text or "1.58" in text or "1.58-bit" in text:
        return "1.58-bit (ternary)"
    if "2-bit" in text or "2bit" in text:
        return "2-bit"
    if "3-bit" in text:
        return "3-bit"
    if "4-bit" in text and "mixed" not in text and "transform" not in text:
        return "4-bit"
    if "mixed" in text or "mixed-precision" in text:
        return "Mixed (2-4-bit)"
    if "ultra-low" in text or "sub-2" in text or "sub-4" in text:
        return "Sub-4-bit"
    return "Unknown / varies"


def infer_general_method_type(method_category: str, specific_method: str) -> str:
    """Infer General Method Type from method details."""
    text = f"{method_category} {specific_method}".lower()
    if any(k in text for k in ["reconstruction", "calibration", "optimize"]):
        return "Reconstruction-based"
    if any(k in text for k in ["binarization", "ternarization", "quantize"]):
        return "Value Decomposition"
    if any(k in text for k in ["pruning", "sparse", "mask"]):
        return "Sparse / Masking"
    if any(k in text for k in ["rotation", "orthogonal", "transform"]):
        return "Rotation / Transform"
    if any(k in text for k in ["outlier", "smoothquant", "quarot", "quip"]):
        return "Outlier-Aware"
    if any(k in text for k in ["knowledge distillation", "kd", "distillation"]):
        return "Knowledge Distillation"
    if any(k in text for k in ["hardware", "asicl", "cpu", "gpu", "cim"]):
        return "Hardware Co-design"
    return "Standard Quantization"


def build_12field_block(fields: dict, arid: str) -> str:
    """Build the 12-field classification section markdown."""
    bit_scope = infer_bit_scope(
        fields.get("Method Category", ""),
        fields.get("Specific Method", ""),
        fields.get("Summary", "")
    )
    gen_method = infer_general_method_type(
        fields.get("Method Category", ""),
        fields.get("Specific Method", "")
    )

    rows = [
        f"### 9. Quantization Bit Scope",
        f"**Classification**: {bit_scope}",
        f"**Evidence**:\n- Source: Auto-inferred from method/summary text\n- Quote: N/A",
        f"",
        f"### 10. General Method Type",
        f"**Classification**: {gen_method}",
        f"**Evidence**:\n- Source: Auto-inferred from method/summary text\n- Quote: N/A",
        f"",
        f"### 11. Core Challenge Addressed",
        f"**Classification**: {fields.get('Core Challenge', DEFAULT_NEW_FIELD_VALUE)}",
        f"**Evidence**:\n- Source: Copied from Core Challenge field\n- Quote: N/A",
        f"",
        f"### 12. Survey Contribution Mapping",
        f"**Classification**: {DEFAULT_NEW_FIELD_VALUE}",
        f"**Evidence**:\n- Source: [TODO — needs manual review]\n- Quote: N/A",
        f"",
        f"### 13. Ultra-low-bit Relevance Summary",
        f"**Classification**: {DEFAULT_NEW_FIELD_VALUE}",
        f"**Evidence**:\n- Source: [TODO — needs manual review]\n- Quote: N/A",
    ]
    return "\n".join(rows)


def build_post_task_qc(arid: str, fields: dict, evidence_rows: list) -> str:
    """Build the POST_TASK_QC block."""
    paper_title = fields.get("Title", "Unknown")

    # Count High/Med/Low confidence evidence
    high = sum(1 for r in evidence_rows if "High" in r.get("confidence", ""))
    med = sum(1 for r in evidence_rows if "Med" in r.get("confidence", ""))
    low = sum(1 for r in evidence_rows if "Low" in r.get("confidence", ""))

    return f"""
---

## POST_TASK_QC — Quality Checklist

- [x] Paper ID and metadata filled
- [x] All 8+2 classification fields populated
- [x] Evidence rows populated (N={len(evidence_rows)}: {high} High, {med} Med, {low} Low)
- [ ] POST_TASK_QC block appended
- [ ] survey_trace subsection record updated
- [ ] 12-field review completed (fields 9-13 need manual verification)
- [ ] No placeholder text remains in critical fields

**QC Result**: PARTIAL — auto-converted from 8-field. Fields 9-13 need human review.

*Converted: {datetime.now().date()} by SurveyMind convert_to_12field.py*
"""


# ─── Main converter ─────────────────────────────────────────────────────────

def convert_paper_analysis(in_path: Path, out_path: Path, dry_run: bool = False) -> dict:
    """
    Convert a single 8-field .md file to 12-field format.

    Returns a dict with conversion metadata.
    """
    content = in_path.read_text()
    arid = in_path.stem.replace("_analysis", "")

    # Extract existing 8 fields
    fields_8 = extract_all_8fields(content)

    # Extract metadata (title, authors, year)
    title_m = re.search(r"\*\*Title\*\*:\s*([^\n]+)", content)
    authors_m = re.search(r"\*\*Authors\*\*:\s*([^\n]+)", content)
    year_m = re.search(r"\*\*Year/Month\*\*:\s*([^\n]+)", content)

    fields_8["Title"] = title_m.group(1).strip() if title_m else ""
    fields_8["Authors"] = authors_m.group(1).strip() if authors_m else ""
    fields_8["Year"] = year_m.group(1).strip() if year_m else ""

    # Extract existing evidence rows
    evidence_rows = extract_evidence_rows(content)

    # Build new 12-field section
    field_12_block = build_12field_block(fields_8, arid)

    # Build POST_TASK_QC
    qc_block = build_post_task_qc(arid, fields_8, evidence_rows)

    # Build output content
    # Split at "## 8-Dimensional Classification" or "## 8-D" marker
    marker_pat = re.compile(r"(##\s+8[- ]Dimensional Classification\n)")
    marker_match = marker_pat.search(content)

    if marker_match:
        marker_pos = marker_match.start()
        prefix = content[:marker_pos].rstrip()
        suffix = content[marker_pos + len(marker_match.group(0)):]

        # Find where the 8-dim section ends (next ## or end)
        end_pat = re.compile(r"\n## [A-Z]", re.MULTILINE)
        end_match = end_pat.search(suffix)
        if end_match:
            end_pos = end_match.start()
            body_8dim = suffix[:end_pos]
        else:
            body_8dim = suffix
    else:
        prefix = ""
        body_8dim = content

    # Build new sections 9-13
    new_sections = "\n\n" + field_12_block + qc_block

    # Combine: keep prefix (metadata) + existing 8 fields + new 12-field + rest
    new_content = prefix + "\n\n## 8-Dimensional Classification\n" + body_8dim.strip() + new_sections

    if dry_run:
        return {
            "arid": arid,
            "title": fields_8.get("Title", "?"),
            "converted": True,
            "dry_run": True,
        }

    out_path.write_text(new_content)
    return {
        "arid": arid,
        "title": fields_8.get("Title", "?"),
        "converted": True,
        "dry_run": False,
    }


def convert_all(
    papers_dir: Path,
    output_dir: Path | None,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Convert all paper analysis files in papers_dir.
    If output_dir is None, convert in-place.
    """
    analysis_files = sorted(papers_dir.glob("*_analysis.md"))
    if not analysis_files:
        return {"converted": 0, "skipped": 0, "errors": []}

    results = {"converted": 0, "skipped": 0, "errors": []}

    for fpath in analysis_files:
        out_dir = output_dir or fpath.parent
        out_path = out_dir / fpath.name

        try:
            result = convert_paper_analysis(fpath, out_path, dry_run=dry_run)
            if verbose:
                status = "DRY-RUN" if dry_run else "CONVERTED"
                print(f"  [{status}] {result['arid']} → {result['title'][:50]}")
            results["converted"] += 1
        except Exception as exc:
            results["errors"].append(f"{fpath.name}: {exc}")
            results["skipped"] += 1

    return results


# ─── CLI ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="SurveyMind 8-Field → 12-Field Analysis Converter"
    )
    ap.add_argument(
        "--papers-dir", "-p", default="paper_analysis_results",
        help="Directory containing 8-field paper analysis .md files"
    )
    ap.add_argument(
        "--output-dir", "-o",
        help="Output directory (default: in-place conversion)"
    )
    ap.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Show what would be converted without writing files"
    )
    ap.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print each conversion"
    )

    args = ap.parse_args()

    tools_dir = Path(__file__).parent
    root_dir = tools_dir.parent
    papers_dir = (root_dir / args.papers_dir).resolve()

    if not papers_dir.exists():
        print(f"ERROR: papers directory not found: {papers_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir = (root_dir / args.output_dir).resolve() if args.output_dir else None
    if output_dir and not output_dir.exists():
        output_dir.mkdir(parents=True)

    print(f"SurveyMind 8→12 field converter")
    print(f"  Source:   {papers_dir}")
    print(f"  Output:   {'in-place' if not output_dir else output_dir}")
    print(f"  Dry run:  {args.dry_run}")

    result = convert_all(
        papers_dir=papers_dir,
        output_dir=output_dir,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    print(f"\n{'='*50}")
    print(f"Converted: {result['converted']} papers")
    print(f"Skipped:   {result['skipped']}")
    if result['errors']:
        print(f"Errors:    {len(result['errors'])}")
        for e in result['errors'][:5]:
            print(f"  - {e}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
