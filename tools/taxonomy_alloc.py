#!/usr/bin/env python3
"""
taxonomy_alloc.py — SurveyMind Taxonomy-Based Paper Analysis Allocator

Reads gate3_taxonomy/taxonomy.md and gate2_paper_analysis/*.md files,
then updates each paper analysis with taxonomy-derived fields based on
the paper's position in the taxonomy hierarchy.

This uses a taxonomy-aware allocation that:
1. Looks up each paper in the taxonomy's method-challenge matrix
2. Derives Quantization Bit Scope from "Papers by Bit-width Focus"
3. Derives Core Challenge Addressed from Method-Challenge Matrix
4. Derives Survey Contribution Mapping from training paradigm
5. Auto-generates routing rules from Level-1 taxonomy structure

Usage
-----
    # Allocate all papers based on taxonomy
    python3 tools/taxonomy_alloc.py

    # Dry run — show what would change without writing
    python3 tools/taxonomy_alloc.py --dry-run

    # Custom directories
    python3 tools/taxonomy_alloc.py --taxonomy-dir surveys/survey_ultra_low_bit/gate3_taxonomy --analysis-dir surveys/survey_ultra_low_bit/gate2_paper_analysis

Exit codes
    0  success
    1  taxonomy not found / parse error
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ─── Taxonomy Parsing ─────────────────────────────────────────────────────────

def parse_taxonomy_md(taxonomy_path: Path) -> Dict:
    """Parse taxonomy.md and extract all relevant tables and mappings."""

    content = taxonomy_path.read_text()

    # Parse method tables to get paper_id → method mapping
    paper_methods = _parse_hierarchical_tables(content)

    # Parse bit-width table
    bit_width_map = _parse_bitwidth_table(content)

    # Parse paradigm table
    paradigm_map = _parse_paradigm_table(content)

    # Parse method-challenge matrix
    challenge_map = _parse_challenge_matrix(content)

    # Parse level-1 structure for routing rules
    routing_rules = _parse_level1_for_routing(content)

    return {
        "paper_methods": paper_methods,
        "bit_width_map": bit_width_map,
        "paradigm_map": paradigm_map,
        "challenge_map": challenge_map,
        "routing_rules": routing_rules,
    }


def _parse_hierarchical_tables(content: str) -> Dict[str, Dict]:
    """Extract paper IDs and their positions from hierarchical taxonomy tables."""
    result = {}

    # Pattern to match tables in the hierarchical structure
    # Tables have format: | Paper ID | Method | Core Innovation | Evidence |
    table_pat = re.compile(
        r'\| Paper ID \| Method \|.*?\n\|[-| ]+\|\n((?:\|[^\n]+\n)+)',
        re.MULTILINE
    )

    # Also match tables with different headers
    table_pat2 = re.compile(
        r'\| Paper ID \|.*?\|\n\|[-| ]+\|\n((?:\|[^\n]+\n)+)',
        re.MULTILINE
    )

    for match in table_pat.finditer(content):
        rows = match.group(1)
        for row in rows.strip().split('\n'):
            cells = [c.strip() for c in row.split('|')[1:-1]]
            if len(cells) >= 2 and cells[0]:
                paper_id = cells[0].strip()
                method = cells[1].strip()
                result[paper_id] = {"method": method}

    return result


def _parse_bitwidth_table(content: str) -> Dict[str, str]:
    """Parse 'Papers by Bit-width Focus' table."""
    result = {}

    # Find the section
    section_match = re.search(
        r'### Papers by Bit-width Focus\s*\n\s*\|.*?\n\|[-| ]+\|\n((?:\|[^\n]+\n)+)',
        content,
        re.MULTILINE
    )
    if not section_match:
        return result

    rows = section_match.group(1)
    for row in rows.strip().split('\n'):
        cells = [c.strip() for c in row.split('|')[1:-1]]
        if len(cells) >= 3 and cells[0]:
            bit_width = cells[0].strip()
            # Methods are in the third column, comma or newline separated
            methods_str = cells[2].strip()
            # Parse method names from method column (not the summary column)
            # Actually we need to look at the row format: | Bit-width | Count | Methods |
            methods = [m.strip() for m in methods_str.replace('\n', ', ').split(',') if m.strip()]
            for method in methods:
                # Map method names to their bit-width
                result[method.lower()] = bit_width

    return result


def _parse_paradigm_table(content: str) -> Dict[str, str]:
    """Parse 'Papers by Training Paradigm' table."""
    result = {}

    section_match = re.search(
        r'### Papers by Training Paradigm\s*\n\s*\|.*?\n\|[-| ]+\|\n((?:\|[^\n]+\n)+)',
        content,
        re.MULTILINE
    )
    if not section_match:
        return result

    rows = section_match.group(1)
    for row in rows.strip().split('\n'):
        cells = [c.strip() for c in row.split('|')[1:-1]]
        if len(cells) >= 3 and cells[0]:
            paradigm = cells[0].strip()
            # Paper IDs are in the third column
            ids_str = cells[2].strip()
            paper_ids = [pid.strip() for pid in re.split(r'[,;]', ids_str) if pid.strip()]
            for pid in paper_ids:
                result[pid] = paradigm

    return result


def _parse_challenge_matrix(content: str) -> Dict[str, List[str]]:
    """Parse Method-Challenge Matrix."""
    result = {}

    # Find the section - it starts with ## Method-Challenge Matrix
    # Then there may be a blank line, then the table
    section_start = content.find('## Method-Challenge Matrix')
    if section_start == -1:
        return result

    # Find the next section or end of file
    next_section = content.find('\n## ', section_start + 1)
    if next_section == -1:
        section_content = content[section_start:]
    else:
        section_content = content[section_start:next_section]

    # Find table rows - they start with | followed by Method name
    # Skip the header row (first row with | Method |)
    row_pattern = re.compile(r'^\| ([^|]+) \|', re.MULTILINE)
    challenge_names = ["C1: Rep. Capacity", "C2: Outlier", "C3: Gradient Flow",
                       "C4: Layer Heterogeneity", "C5: HW Mismatch"]

    in_table = False
    for line in section_content.split('\n'):
        if '|--------|' in line or '| :-----' in line:
            in_table = True  # Found separator, next rows are data
            continue
        if not in_table:
            continue
        if line.startswith('|'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) >= 6 and cells[0]:
                method = cells[0].strip()
                challenges = []
                for i, cell in enumerate(cells[1:6]):
                    if '✓' in cell:
                        challenges.append(challenge_names[i] if i < len(challenge_names) else f"C{i+1}")
                result[method.lower()] = challenges

    return result


def _parse_level1_for_routing(content: str) -> List[Dict]:
    """Parse Level-1 taxonomy structure to generate routing rules."""

    # Level-1 categories and their section mappings
    # Based on the survey_trace structure:
    # 05: Quantization-Aware Training (QAT)
    # 06: Post-Training Quantization Methods
    # 07: Outlier Handling Strategies
    # 08: Hardware Implementation
    # 09: Comprehensive Benchmark Comparison
    # 10: Research Gaps and Limitations
    # 11: Beyond Text / Multimodal

    rules = [
        {
            "name": "QAT Binary",
            "paradigm": ["QAT", "From-Scratch"],
            "method_keywords": ["binary", "1-bit", "binarization"],
            "subsection": "05/01_binary_networks_1_bit"
        },
        {
            "name": "QAT Ternary",
            "paradigm": ["QAT"],
            "method_keywords": ["ternary", "1.58", "ternarization"],
            "subsection": "05/02_ternary_networks_1_58_bit"
        },
        {
            "name": "QAT Recent",
            "paradigm": ["QAT", "Hybrid QAT+PTQ"],
            "method_keywords": ["curvature", "hessian", "low-rank", "sparse", "progressive"],
            "subsection": "05/03_recent_qat_advances_curvature_and_sparse_co_training"
        },
        {
            "name": "PTQ Ultra-low",
            "paradigm": ["PTQ"],
            "method_keywords": ["ultra-low", "sub-2-bit", "sub 2", "1.61", "trit-plane", "dual-scale", "tessera", "butterfly", "lieq", "d2quant"],
            "subsection": "06/01_ultra_low_bit_ptq_sub_2_bit"
        },
        {
            "name": "PTQ 2-bit",
            "paradigm": ["PTQ"],
            "method_keywords": ["2-bit", "int2", "fast-2bit", "upq"],
            "subsection": "06/2_2_bit_quantization_methods"
        },
        {
            "name": "PTQ Standard",
            "paradigm": ["PTQ"],
            "method_keywords": ["gptq", "awq", "spqr", "quip", "smoothquant", "quarot", "prefixquant"],
            "subsection": "06/04_transform_based_and_mixed_precision_methods"
        },
        {
            "name": "Outlier Handling",
            "paradigm": ["PTQ"],
            "method_keywords": ["outlier", "smoothquant", "quarot", "quip", "rotation", "prefixquant", "afpq"],
            "subsection": "07/02_categorization_of_outlier_handling_methods"
        },
        {
            "name": "Hardware",
            "paradigm": ["Hardware"],
            "method_keywords": ["cpu", "gpu", "asic", "kernel", "simd", "bitnet.cpp", "fast-2bit", "async"],
            "subsection": "08/01_cpu_implementations"
        },
        {
            "name": "Multimodal",
            "paradigm": ["Multimodal"],
            "method_keywords": ["multimodal", "mlm", "vlm", "luq"],
            "subsection": "11/1_1_bit_vision_language_action_models"
        },
        {
            "name": "Benchmark",
            "paradigm": [],
            "method_keywords": ["benchmark", "perplexity", "latency"],
            "subsection": "09/02_performance_comparison"
        },
    ]

    return rules


# ─── Paper Analysis Update ─────────────────────────────────────────────────────

def get_field_value(content: str, field_name: str) -> Optional[str]:
    """Extract classification value for a given field from paper analysis."""
    patterns = [
        rf"### \d+\. {re.escape(field_name)}.*?\*\*Classification\*\*:\s*([^\n]+)",
        rf"\*\*{re.escape(field_name)}:\*\*\s*([^\n]+)",
    ]
    for pat in patterns:
        m = re.search(pat, content, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip().rstrip('*').strip()
    return None


def update_paper_analysis(
    paper_md_path: Path,
    taxonomy_data: Dict,
    dry_run: bool = False
) -> Tuple[bool, str]:
    """
    Update a single paper analysis with taxonomy-derived fields.

    Returns (changed, message).
    """

    content = paper_md_path.read_text()

    # Extract paper ID from filename or content
    paper_id_match = re.search(r'(\d{4}\.\d{5})', paper_md_path.stem)
    if not paper_id_match:
        return False, f"Cannot extract paper ID from {paper_md_path.name}"

    paper_id = paper_id_match.group(1)

    # Look up in taxonomy
    bit_width_map = taxonomy_data["bit_width_map"]
    paradigm_map = taxonomy_data["paradigm_map"]
    challenge_map = taxonomy_data["challenge_map"]
    paper_methods = taxonomy_data["paper_methods"]

    # Get existing method name
    method_name = get_field_value(content, "Specific Method") or ""
    method_lower = method_name.lower()

    # Derive Quantization Bit Scope from taxonomy
    derived_bit_scope = None
    for keyword, bit_scope in bit_width_map.items():
        if keyword in method_lower or keyword.replace('-', ' ') in method_lower:
            derived_bit_scope = bit_scope
            break

    # If not found by method, try by paper_id in paradigm map
    if not derived_bit_scope:
        for kw, scope in bit_width_map.items():
            if kw in paper_methods.get(paper_id, {}).get("method", "").lower():
                derived_bit_scope = scope
                break

    # Look up challenges from matrix
    derived_challenges = challenge_map.get(method_lower, [])

    # Look up paradigm
    paradigm = paradigm_map.get(paper_id, "")

    # Build taxonomy-derived field values
    new_fields = {}

    if derived_bit_scope:
        new_fields["Quantization Bit Scope"] = derived_bit_scope

    if derived_challenges:
        new_fields["Core Challenge Addressed"] = "; ".join(derived_challenges)
    else:
        # Fallback to existing value or mark as unknown
        existing = get_field_value(content, "Core Challenge Addressed")
        if existing and "[TODO" not in existing:
            new_fields["Core Challenge Addressed"] = existing

    # Derive Survey Contribution Mapping based on paradigm
    if paradigm:
        if "QAT" in paradigm:
            new_fields["Survey Contribution Mapping"] = "Establishes ultra-low-bit training capability for LLMs; addresses gradient flow and representation capacity trade-offs."
        elif "PTQ" in paradigm:
            new_fields["Survey Contribution Mapping"] = "Enables accurate post-training quantization at ≤4-bit; focuses on calibration and reconstruction methods."
        elif paradigm == "Hardware":
            new_fields["Survey Contribution Mapping"] = "Provides hardware-friendly inference for ultra-low-bit LLMs; addresses deployment mismatch."
        elif paradigm == "Multimodal":
            new_fields["Survey Contribution Mapping"] = "Extends ultra-low-bit quantization to multimodal LLMs; addresses cross-modal challenges."
        else:
            new_fields["Survey Contribution Mapping"] = f"Addresses {paradigm.lower()} challenges in ultra-low-bit quantization."

    # Derive Ultra-low-bit Relevance Summary
    if derived_bit_scope:
        new_fields["Ultra-low-bit Relevance Summary"] = f"Method achieves {derived_bit_scope} quantization with focus on: {', '.join(derived_challenges[:2]) if derived_challenges else 'representation capacity'}."
    else:
        new_fields["Ultra-low-bit Relevance Summary"] = f"Contributes to ultra-low-bit quantization landscape; addresses: {', '.join(derived_challenges[:2]) if derived_challenges else 'quantization challenges'}."

    # Now update the content
    updated_content = content
    changed = False

    for field_name, field_value in new_fields.items():
        # Check if field already exists with content
        existing_value = get_field_value(content, field_name)

        if existing_value and "[TODO" not in existing_value and not dry_run:
            # Don't overwrite existing good values
            continue

        # Find the section for this field and update it
        field_pattern = rf'(### \d+\. {re.escape(field_name)}\s*\n\*\*Classification\*\*:)\s*[^\n]+'

        if re.search(field_pattern, updated_content):
            if dry_run:
                updated_content = re.sub(
                    field_pattern,
                    rf'\1 {field_value} [FROM TAXONOMY]',
                    updated_content
                )
            else:
                updated_content = re.sub(
                    field_pattern,
                    rf'\1 {field_value}',
                    updated_content
                )
            changed = True
        else:
            # Field doesn't exist in standard format, check for TODO placeholder
            todo_pattern = rf'({re.escape(field_name)}.*?\[)TODO[^\]]*(\])'
            if re.search(todo_pattern, updated_content, re.DOTALL):
                if dry_run:
                    updated_content = re.sub(
                        todo_pattern,
                        rf'\1FROM TAXONOMY: {field_value}\2',
                        updated_content,
                        flags=re.DOTALL
                    )
                else:
                    updated_content = re.sub(
                        todo_pattern,
                        rf'\1{field_value}\2',
                        updated_content,
                        flags=re.DOTALL
                    )
                changed = True

    if dry_run:
        return True, f"DRY RUN: Would update {paper_id} with fields: {list(new_fields.keys())}"

    if changed:
        paper_md_path.write_text(updated_content)
        return True, f"Updated {paper_id} with fields: {list(new_fields.keys())}"
    else:
        return False, f"No changes needed for {paper_id}"


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Taxonomy-based paper analysis allocator"
    )
    parser.add_argument(
        "--taxonomy-dir",
        default="surveys/survey_ultra_low_bit/gate3_taxonomy",
        help="Directory containing taxonomy.md"
    )
    parser.add_argument(
        "--analysis-dir",
        default="surveys/survey_ultra_low_bit/gate2_paper_analysis",
        help="Directory containing paper analysis .md files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed output"
    )
    args = parser.parse_args()

    taxonomy_path = Path(args.taxonomy_dir) / "taxonomy.md"
    analysis_dir = Path(args.analysis_dir)

    if not taxonomy_path.exists():
        print(f"ERROR: Taxonomy not found at {taxonomy_path}", file=sys.stderr)
        sys.exit(1)

    if not analysis_dir.exists():
        print(f"ERROR: Analysis directory not found at {analysis_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'='*60}")
    print("SurveyMind taxonomy-alloc — Taxonomy-Based Field Allocation")
    print(f"{'='*60}")
    print(f"Taxonomy: {taxonomy_path}")
    print(f"Analysis dir: {analysis_dir}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Parse taxonomy
    print("Parsing taxonomy...")
    taxonomy_data = parse_taxonomy_md(taxonomy_path)
    print(f"  - Paper methods: {len(taxonomy_data['paper_methods'])}")
    print(f"  - Bit-width mappings: {len(taxonomy_data['bit_width_map'])}")
    print(f"  - Paradigm mappings: {len(taxonomy_data['paradigm_map'])}")
    print(f"  - Challenge mappings: {len(taxonomy_data['challenge_map'])}")
    print(f"  - Routing rules: {len(taxonomy_data['routing_rules'])}")

    # Find all paper analysis files
    paper_files = list(analysis_dir.glob("*_analysis.md"))
    print(f"\nFound {len(paper_files)} paper analysis files")

    # Process each file
    updated_count = 0
    for paper_path in sorted(paper_files):
        changed, msg = update_paper_analysis(paper_path, taxonomy_data, args.dry_run)
        if args.verbose or changed:
            print(f"  {msg}")
        if changed:
            updated_count += 1

    print()
    if args.dry_run:
        print(f"DRY RUN: {updated_count} files would be updated")
    else:
        print(f"Updated {updated_count} files")

    # Print routing rules summary
    print("\n--- Auto-generated Routing Rules ---")
    for rule in taxonomy_data["routing_rules"]:
        keywords = rule.get("method_keywords", [])
        print(f"  {rule['name']}: {rule['subsection']}")
        if args.verbose and keywords:
            print(f"    Keywords: {', '.join(keywords[:5])}")

    print()
    print(f"*Converted: {datetime.now().date()} by SurveyMind taxonomy_alloc.py*")

    return 0


if __name__ == "__main__":
    sys.exit(main())
