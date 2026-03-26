#!/usr/bin/env python3
"""
survey_trace_init.py — SurveyMind Survey Trace Directory Initialiser

Given a survey outline (section / subsection hierarchy), auto-creates the
``survey_trace/`` directory tree with all required documentation files.
Designed to be reusable for ANY survey topic — all content is
parameterised via CLI flags or a config file.

Usage
-----
    # Use existing survey .tex to auto-detect sections
    python3 tools/survey_trace_init.py \\
        --from-tex tpami_tem/literature_review_survey.tex

    # From explicit YAML outline
    python3 tools/survey_trace_init.py \\
        --outline-yaml my_survey_outline.yaml

    # Verbose — show every file created
    python3 tools/survey_trace_init.py \\
        --from-tex tpami_tem/literature_review_survey.tex --verbose

Outline YAML format
------------------
    sections:
      - number: "01"
        name: "introduction"
        title: "Introduction"
        subsections:
          - "motivation"
          - "scope"
      - number: "02"
        name: "background"
        title: "Background"
        subsections:
          - "quantization_fundamentals"
          - "llm_architectures"

Output structure
---------------
    survey_trace/
    ├── 01_introduction/
    │   ├── 01_motivation/
    │   │   ├── SUBSECTION_RECORD.md
    │   │   └── SUBFOLDER_SUMMARY.md
    │   ├── 02_scope/
    │   │   ├── SUBSECTION_RECORD.md
    │   │   └── SUBFOLDER_SUMMARY.md
    │   └── SECTION_SUMMARY.md
    ├── 02_background/
    │   ├── 01_quantization_fundamentals/
    │   │   ├── SUBSECTION_RECORD.md
    │   │   └── SUBFOLDER_SUMMARY.md
    │   └── SECTION_SUMMARY.md
    └── ...

Exit codes
    0  success
    1  outline file not found / parse error / directory exists
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# ─── Survey outline parsers ────────────────────────────────────────────────

def parse_tex_sections(tex_path: str) -> list[dict]:
    """
    Auto-detect section / subsection structure from a LaTeX survey file.
    Returns a list of section dicts, each with:
      number, name, title, subsections (list of dicts with number, name, title)
    """
    with open(tex_path) as f:
        content = f.read()

    sections = []
    # Match \section{...} and \subsection{...}
    sec_pat = re.compile(r'\\section\{([^}]+)\}')
    subsec_pat = re.compile(r'\\subsection\{([^}]+)\}')
    label_pat = re.compile(r'\\label\{([^}]+)\}')

    current_section = None

    for line in content.splitlines():
        sec_match = sec_pat.search(line)
        if sec_match:
            if current_section:
                sections.append(current_section)
            title = sec_match.group(1).strip()
            # Extract section number from \label if present
            label_match = label_pat.search(line)
            label = label_match.group(1) if label_match else ""
            # Number from title or label
            number = _infer_section_number(title, label, len(sections) + 1)
            name = _title_to_dirname(title)
            current_section = {
                "number": number,
                "name": name,
                "title": title,
                "label": label,
                "subsections": [],
            }
        subsec_match = subsec_pat.search(line)
        if subsec_match and current_section is not None:
            subtitle = subsec_match.group(1).strip()
            label_match = label_pat.search(line)
            sublabel = label_match.group(1) if label_match else ""
            subnumber = _infer_subsection_number(subtitle, sublabel, len(current_section["subsections"]) + 1)
            subname = _title_to_dirname(subtitle)
            current_section["subsections"].append({
                "number": subnumber,
                "name": subname,
                "title": subtitle,
                "label": sublabel,
            })

    if current_section:
        sections.append(current_section)

    # If no sections found, fall back to default
    if not sections:
        sections = _default_ultra_low_bit_outline()

    return sections


def _infer_section_number(title: str, label: str, fallback: int) -> str:
    """Extract '01', '02', … from label or title."""
    # Try label: sec:taxonomy → taxonomy → not numbered
    # Try to find digits in label
    m = re.search(r'\d+', label)
    if m:
        n = int(m.group())
        return f"{n:02d}"
    # Try title: "Section 4: ..." or "4. " prefix
    m = re.search(r'^(?:Section\s+)?(\d+)', title)
    if m:
        return f"{int(m.group()):02d}"
    return f"{fallback:02d}"


def _infer_subsection_number(title: str, label: str, fallback: int) -> str:
    m = re.search(r'\d+', label)
    if m:
        return f"{int(m.group()):02d}"
    m = re.search(r'^(?:Section\s+)?(\d+(?:\.\d+)?)', title)
    if m:
        return m.group(1).replace('.', '')
    return f"{fallback:02d}"


def _title_to_dirname(title: str) -> str:
    """'Background & Foundations' → 'background_foundations'"""
    # Strip latex: \ref{}, \cite{}, math
    s = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', title)
    s = re.sub(r'[$][^$]*[$]', '', s)   # inline math
    s = re.sub(r'[^a-zA-Z0-9\s]', ' ', s)
    s = re.sub(r'\s+', '_', s.strip())
    return s.lower()[:60]


def _default_ultra_low_bit_outline() -> list[dict]:
    """Fallback outline matching the extreme quantization survey."""
    return [
        {
            "number": "01", "name": "introduction", "title": "Introduction",
            "subsections": [
                {"number": "01", "name": "motivation", "title": "Motivation"},
                {"number": "02", "name": "scope", "title": "Scope & Contributions"},
            ]
        },
        {
            "number": "02", "name": "related_work", "title": "Related Work & Positioning",
            "subsections": []
        },
        {
            "number": "03", "name": "background", "title": "Background & Theory",
            "subsections": [
                {"number": "01", "name": "quantization_fundamentals", "title": "Quantization Fundamentals"},
            ]
        },
        {
            "number": "04", "name": "taxonomy", "title": "Unified Taxonomy",
            "subsections": [
                {"number": "01", "name": "problem_treatment", "title": "Problem-Treatment Framework"},
            ]
        },
        {
            "number": "05", "name": "qat", "title": "Quantization-Aware Training",
            "subsections": [
                {"number": "01", "name": "binary_networks", "title": "Binary Networks (1-bit)"},
                {"number": "02", "name": "ternary_networks", "title": "Ternary Networks (1.58-bit)"},
                {"number": "03", "name": "recent_qat", "title": "Recent Advances"},
            ]
        },
        {
            "number": "06", "name": "ptq", "title": "Post-Training Quantization",
            "subsections": [
                {"number": "01", "name": "ultra_low_ptq", "title": "Ultra-Low Bit PTQ"},
                {"number": "02", "name": "standard_ptq", "title": "Standard PTQ (3-4-bit)"},
            ]
        },
        {
            "number": "07", "name": "outlier", "title": "Outlier Handling",
            "subsections": []
        },
        {
            "number": "08", "name": "hardware", "title": "Hardware Implementation",
            "subsections": []
        },
        {
            "number": "09", "name": "benchmark", "title": "Benchmark Comparison",
            "subsections": []
        },
        {
            "number": "10", "name": "gaps", "title": "Research Gaps",
            "subsections": []
        },
        {
            "number": "11", "name": "multimodal", "title": "Beyond Text: Multimodal & Agents",
            "subsections": []
        },
        {
            "number": "12", "name": "future", "title": "Future Directions",
            "subsections": []
        },
        {
            "number": "13", "name": "conclusion", "title": "Conclusion",
            "subsections": []
        },
    ]


# ─── File templates ─────────────────────────────────────────────────────────

def subsection_record_md(section_num: str, section_name: str,
                         subsection_num: str, subsection_name: str,
                         subsection_title: str) -> str:
    return f"""# Subsection Record

- **Folder**: {section_num}_{section_name}/{subsection_num}_{subsection_name}
- **Paper ID**: [TBD — fill after paper analysis]
- **Survey Section**: {section_num} — {subsection_title}

## Evidence Table

| Claim | Evidence Type | Source Snippet | Confidence |
|---|---|---|---|
| [TBD] | [Abstract/Method/Experiment/Conclusion] | "[snippet]" | [High/Med/Low] |

## Quality Checklist

- [ ] Paper ID and metadata filled
- [ ] All evidence rows populated
- [ ] POST_TASK_QC block appended

---

*Generated: {datetime.now().isoformat()} by SurveyMind survey_trace_init.py*
"""


def subfolder_summary_md(section_num: str, section_name: str,
                          subsection_num: str, subsection_name: str,
                          subsection_title: str) -> str:
    return f"""# Subfolder Summary

- **Path**: `{section_num}_{section_name}/{subsection_num}_{subsection_name}`
- **Survey Section**: {section_num}.{subsection_num} — {subsection_title}
- **Papers Analyzed**: 0 (placeholder)

## Content Summary

[TODO — update after paper analysis is completed]

## Record Paths

- `./SUBSECTION_RECORD.md`

---

*Generated: {datetime.now().isoformat()} by SurveyMind survey_trace_init.py*
"""


def section_summary_md(section_num: str, section_name: str,
                       section_title: str,
                       subsections: list[dict]) -> str:
    subfolder_lines = []
    for sub in subsections:
        subfolder_lines.append(f"- ./{sub['number']}_{sub['name']}/")

    subfolder_str = "\n".join(subfolder_lines) if subfolder_lines else "*No subsections*"

    return f"""# Section Summary: {section_title}

- **Section Number**: {section_num}
- **Folder**: `{section_num}_{section_name}/`
- **Papers Analyzed**: 0

## Subfolder Paths

{subfolder_str}

## Content Summary

[TODO — update after subsection analyses are completed]

## Record Paths (expected)

""" + "\n".join(
    f"- ./{sub['number']}_{sub['name']}/SUBSECTION_RECORD.md"
    for sub in subsections
) + f"""

## Coverage Snapshot

- Populated subfolders: 0/{len(subsections)}
- Papers logged: 0
- High-confidence claims: 0

---

*Generated: {datetime.now().isoformat()} by SurveyMind survey_trace_init.py*
"""


def survey_trace_readme_md(root_dir: str) -> str:
    return f"""# Survey Trace Repository

This folder stores evidence-grounded outputs generated by the SurveyMind
pipeline for paper analysis.

## Auto-generated Structure

All files in this directory tree are automatically created and updated by:

    python3 tools/survey_trace_sync.py   # sync analysis → trace
    python3 tools/survey_trace_init.py   # (re)init from survey outline

## Purpose

- Keep all analysis artifacts traceable to the survey manuscript structure.
- Organize content by section/subsection to support automated drafting and review.
- Preserve source-grounded evidence for every claim.

## Structure Rule

- Level-1 folders map to manuscript sections.
- Level-2 folders map to manuscript subsections.
- Each Level-1 folder has a `SECTION_SUMMARY.md` with relative paths to subsection folders.
- Each Level-2 folder contains evidence records (`SUBSECTION_RECORD.md`) and
  optional paper-level notes.

## Required Traceability Fields (for every record)

- Paper ID / title
- Source evidence type (Abstract/Method/Experiment/Conclusion)
- Source snippet (exact or high-fidelity paraphrase)
- Confidence (High/Med/Low)
- Whether numeric claims are tied to table/figure references

---

*Generated: {datetime.now().isoformat()} by SurveyMind survey_trace_init.py*
"""


# ─── Core directory creator ──────────────────────────────────────────────────

def create_trace_tree(
    sections: list[dict],
    root: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Creates the full survey_trace directory tree.

    Returns a summary dict:
        {created_dirs: [Path, ...], created_files: [Path, ...]}
    """
    created_dirs = []
    created_files = []

    def _create(path: Path, content: str) -> None:
        if dry_run:
            print(f"  [dry-run] would create: {path}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with open(path, "w") as f:
                f.write(content)
            created_files.append(path)
            if verbose:
                print(f"  + {path}")

    for sec in sections:
        sec_num = sec["number"]
        sec_name = sec["name"]
        sec_title = sec["title"]
        sec_dir = root / f"{sec_num}_{sec_name}"
        created_dirs.append(sec_dir)

        subsections = sec.get("subsections", [])
        if not subsections:
            # Section without subsections — create section-level files only
            _create(
                sec_dir / "SECTION_SUMMARY.md",
                section_summary_md(sec_num, sec_name, sec_title, [])
            )
        else:
            for sub in subsections:
                sub_num = sub["number"]
                sub_name = sub["name"]
                sub_title = sub["title"]
                sub_dir = sec_dir / f"{sub_num}_{sub_name}"
                created_dirs.append(sub_dir)

                _create(
                    sub_dir / "SUBSECTION_RECORD.md",
                    subsection_record_md(sec_num, sec_name, sub_num, sub_name, sub_title)
                )
                _create(
                    sub_dir / "SUBFOLDER_SUMMARY.md",
                    subfolder_summary_md(sec_num, sec_name, sub_num, sub_name, sub_title)
                )

            _create(
                sec_dir / "SECTION_SUMMARY.md",
                section_summary_md(sec_num, sec_name, sec_title, subsections)
            )

    # Root-level README
    _create(root / "README.md", survey_trace_readme_md(str(root)))

    return {
        "created_dirs": [str(d) for d in created_dirs],
        "created_files": [str(f) for f in created_files],
        "total_dirs": len(created_dirs),
        "total_files": len(created_files),
    }


# ─── CLI ─────────────────────────────────────────────────────────────────

def parse_outline_yaml(path: str) -> list[dict]:
    """Parse JSON outline file (YAML requires pyyaml; use JSON instead)."""
    return parse_outline_json(path)


def parse_outline_json(path: str) -> list[dict]:
    import json
    with open(path) as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        if "sections" in raw:
            return raw["sections"]
        if isinstance(raw.get("outline"), list):
            return raw["outline"]
    if isinstance(raw, list):
        return raw
    raise ValueError(f"Could not parse outline from {path}")


def main():
    ap = argparse.ArgumentParser(description="SurveyMind Survey Trace Initialiser")
    ap.add_argument(
        "--from-tex", metavar="PATH",
        help="Auto-detect section structure from LaTeX survey file"
    )
    ap.add_argument(
        "--outline-yaml", metavar="PATH",
        help="[DEPRECATED — use --outline-json] Load section outline from JSON/YAML file"
    )
    ap.add_argument(
        "--outline-json", metavar="PATH",
        help="Load section outline from JSON file"
    )
    ap.add_argument(
        "--output-dir", "-o", default="my idea/survey_trace",
        help="Root of the survey_trace directory (default: my idea/survey_trace)"
    )
    ap.add_argument(
        "--force", action="store_true",
        help="Delete and recreate output dir if it already exists"
    )
    ap.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Show what would be created without writing files"
    )
    ap.add_argument(
        "--verbose", "-v", action="store_true",
        help="List every file created"
    )

    args = ap.parse_args()

    if not (args.from_tex or args.outline_yaml or args.outline_json):
        # Fall back to default ultra-low-bit outline
        sections = _default_ultra_low_bit_outline()
        print("No outline source specified — using built-in default (ultra-low bit LLM quantization).")
    elif args.from_tex:
        sections = parse_tex_sections(args.from_tex)
        print(f"Parsed {len(sections)} sections from {args.from_tex}")
    elif args.outline_yaml:
        sections = parse_outline_json(args.outline_yaml)
        print(f"Loaded {len(sections)} sections from {args.outline_yaml}")
    else:
        sections = parse_outline_json(args.outline_json)
        print(f"Loaded {len(sections)} sections from {args.outline_json}")

    # Resolve output dir
    tools_dir = Path(__file__).parent
    root_dir = (tools_dir.parent / args.output_dir).resolve()

    if root_dir.exists() and not args.force and not args.dry_run:
        # Check if it has the expected structure
        existing = list(root_dir.iterdir())
        if existing:
            print(f"WARNING: {root_dir} already exists with {len(existing)} items.")
            print("Use --force to delete and recreate, or --dry-run to see what would happen.")
            print("Skipping creation.")
            sys.exit(1)

    print(f"\nOutput directory: {root_dir}")

    result = create_trace_tree(sections, root_dir, dry_run=args.dry_run, verbose=args.verbose)

    print(f"\n{'='*55}")
    if args.dry_run:
        print(f"[dry-run] Would create {result['total_dirs']} directories, {result['total_files']} files")
    else:
        print(f"Created {result['total_dirs']} directories, {result['total_files']} files")
    print(f"{'='*55}")

    print("\nSection summary:")
    for sec in sections:
        subs = sec.get("subsections", [])
        sub_info = f" ({len(subs)} subsections)" if subs else ""
        print(f"  {sec['number']}. {sec['title']}{sub_info}")
        for sub in subs:
            print(f"      └── {sub['number']}. {sub['title']}")


if __name__ == "__main__":
    main()
