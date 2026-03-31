"""Survey synthesis stages for CLI full-closure flow.

These stages provide scriptable equivalents for:
- taxonomy-build
- gap-identify
- survey-write
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


_FIELD_LABEL_TO_KEY = {
    "Model Type": "model_type",
    "Method Category": "method_category",
    "Specific Method": "specific_method",
    "Training Paradigm": "training",
    "Core Challenge": "core_challenge",
    "Evaluation Focus": "evaluation",
    "Hardware Co-design": "hardware",
    "Quantization Bit Scope": "bit_scope",
    "General Method Type": "general_method",
}


def _parse_analysis_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    out: dict[str, str] = {"paper_id": path.name.replace("_analysis.md", "")}

    # Match lines like: "2. **Method Category**: Binarization"
    for m in re.finditer(r"\n\s*\d+\.\s+\*\*(.+?)\*\*:\s*(.+)", "\n" + text):
        label = m.group(1).strip()
        value = m.group(2).strip()
        key = _FIELD_LABEL_TO_KEY.get(label)
        if key and value:
            out[key] = value
    return out


def _load_analysis_records(analysis_dir: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for p in sorted(analysis_dir.glob("*_analysis.md")):
        try:
            records.append(_parse_analysis_file(p))
        except Exception:
            continue
    return records


def run_taxonomy_build(args) -> int:
    """Build taxonomy from gate2 analysis files."""
    print("\n" + "=" * 60)
    print("STAGE: taxonomy-build — Build taxonomy from analyses")
    print("=" * 60)

    analysis_dir = Path(args.analysis_dir)
    gate3_dir = Path(args.gate3_dir)
    gate3_dir.mkdir(parents=True, exist_ok=True)

    records = _load_analysis_records(analysis_dir)
    if not records:
        print(f"ERROR: no analysis files found in {analysis_dir}", file=sys.stderr)
        return 1

    method_counts = Counter(r.get("method_category", "Unknown") for r in records)
    training_counts = Counter(r.get("training", "Unknown") for r in records)
    bit_counts = Counter(r.get("bit_scope", "Unknown") for r in records)
    model_counts = Counter(r.get("model_type", "Unknown") for r in records)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "analysis_dir": str(analysis_dir),
        "paper_count": len(records),
        "method_category": dict(method_counts),
        "training_paradigm": dict(training_counts),
        "bit_scope": dict(bit_counts),
        "model_type": dict(model_counts),
    }

    taxonomy_json = gate3_dir / "taxonomy_summary.json"
    taxonomy_md = gate3_dir / "taxonomy.md"
    taxonomy_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Taxonomy",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Paper count: {payload['paper_count']}",
        "",
        "## Method Category",
        "",
    ]
    for k, v in method_counts.most_common():
        lines.append(f"- {k}: {v}")

    lines += ["", "## Training Paradigm", ""]
    for k, v in training_counts.most_common():
        lines.append(f"- {k}: {v}")

    lines += ["", "## Quantization Bit Scope", ""]
    for k, v in bit_counts.most_common():
        lines.append(f"- {k}: {v}")

    lines += ["", "## Model Type", ""]
    for k, v in model_counts.most_common():
        lines.append(f"- {k}: {v}")

    taxonomy_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"taxonomy markdown: {taxonomy_md}")
    print(f"taxonomy summary: {taxonomy_json}")
    return 0


def run_gap_identify(args) -> int:
    """Identify research gaps from taxonomy summary."""
    print("\n" + "=" * 60)
    print("STAGE: gap-identify — Identify research gaps")
    print("=" * 60)

    gate3_dir = Path(args.gate3_dir)
    gate4_dir = Path(args.gate4_dir)
    gate4_dir.mkdir(parents=True, exist_ok=True)

    taxonomy_json = gate3_dir / "taxonomy_summary.json"
    if not taxonomy_json.exists():
        print(f"ERROR: taxonomy summary missing: {taxonomy_json} (run taxonomy-build first)", file=sys.stderr)
        return 1

    data = json.loads(taxonomy_json.read_text(encoding="utf-8"))
    method_counts = data.get("method_category", {})
    training_counts = data.get("training_paradigm", {})
    bit_counts = data.get("bit_scope", {})

    sparse_methods = [k for k, v in method_counts.items() if isinstance(v, int) and v <= 1 and k != "Unknown"]
    expected_training = [
        "PTQ (Post-Training Quantization)",
        "QAT (Quantization-Aware Training)",
        "From-Scratch Training",
    ]
    missing_training = [t for t in expected_training if training_counts.get(t, 0) == 0]
    expected_bits = ["1-bit", "1.58-bit (ternary)", "2-bit", "3-bit", "4-bit"]
    missing_bits = [b for b in expected_bits if bit_counts.get(b, 0) == 0]

    gaps = []
    if sparse_methods:
        gaps.append({
            "type": "Method under-coverage",
            "severity": "medium",
            "detail": f"Low-evidence method categories: {', '.join(sparse_methods[:8])}",
        })
    if missing_training:
        gaps.append({
            "type": "Training paradigm gap",
            "severity": "high",
            "detail": f"Missing paradigms: {', '.join(missing_training)}",
        })
    if missing_bits:
        gaps.append({
            "type": "Bit-width coverage gap",
            "severity": "high",
            "detail": f"Missing bit scopes: {', '.join(missing_bits)}",
        })
    if not gaps:
        gaps.append({
            "type": "No obvious structural gaps",
            "severity": "low",
            "detail": "Current taxonomy covers major method/training/bit axes from available analyses.",
        })

    payload = {
        "generated_at": datetime.now().isoformat(),
        "source_taxonomy": str(taxonomy_json),
        "gap_count": len(gaps),
        "gaps": gaps,
    }

    out_json = gate4_dir / "gap_analysis.json"
    out_md = gate4_dir / "gap_analysis.md"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Gap Analysis",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Gap count: {payload['gap_count']}",
        "",
    ]
    for i, g in enumerate(gaps, start=1):
        lines += [
            f"## Gap {i}: {g['type']}",
            "",
            f"- Severity: {g['severity']}",
            f"- Detail: {g['detail']}",
            "",
        ]

    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"gap analysis markdown: {out_md}")
    print(f"gap analysis json: {out_json}")
    return 0


def run_survey_write(args) -> int:
    """Synthesize survey draft from scope/taxonomy/gap artifacts."""
    print("\n" + "=" * 60)
    print("STAGE: survey-write — Synthesize survey draft")
    print("=" * 60)

    gate3_dir = Path(args.gate3_dir)
    gate4_dir = Path(args.gate4_dir)
    gate5_dir = Path(args.gate5_dir)
    gate5_dir.mkdir(parents=True, exist_ok=True)

    taxonomy_md = gate3_dir / "taxonomy.md"
    gap_md = gate4_dir / "gap_analysis.md"
    if not taxonomy_md.exists() or not gap_md.exists():
        print("ERROR: taxonomy/gap artifacts missing (run taxonomy-build and gap-identify first)", file=sys.stderr)
        return 1

    scope_title = "Survey"
    scope_path = Path(args.scope_file)
    if scope_path.exists():
        for line in scope_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("# "):
                scope_title = line[2:].strip()
                break

    draft_path = gate5_dir / "SURVEY_DRAFT.md"
    lines = [
        f"# {scope_title}",
        "",
        "## 1. Introduction",
        "- Motivation and scope generated from gate0 scope definition.",
        "",
        "## 2. Taxonomy",
        "",
        taxonomy_md.read_text(encoding="utf-8", errors="ignore").strip(),
        "",
        "## 3. Gap Analysis",
        "",
        gap_md.read_text(encoding="utf-8", errors="ignore").strip(),
        "",
        "## 4. Discussion",
        "- Summarize trade-offs across method categories and training paradigms.",
        "- Highlight benchmark and reproducibility limitations.",
        "",
        "## 5. Conclusion",
        "- Key takeaways and actionable future directions.",
        "",
        "## References",
        "- TODO: populate from gate1 paper list and citations.",
        "",
    ]
    draft_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"survey draft: {draft_path}")
    return 0
