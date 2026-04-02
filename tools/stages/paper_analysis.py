"""Stage: paper-analysis — priority-driven deep analysis + coverage reporting."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from stages._helpers import (
    _existing_analysis_ids,
    _generate_missing_analysis_drafts,
    _load_paper_index,
    _load_priority_targets,
    _resolve_pdf_path,
    _resolve_priority_path,
    _write_coverage_report,
)

import json


# Known quantization benchmark methods (representative papers)
BENCHMARK_METHODS = {
    "GPTQ", "AWQ", "OPTQ", "QuIP", "QuIP#", "QuaRot", "SmoothQuant",
    "BitNet", "BitNet b1.58", "SpQR", "OmniQuant", "TesseraQ", "LieQ",
    "KIVI", "QAQ", "LLaMA", "OPT", "Qwen", "Mistral",
}

# Standard model sizes for comparison
MODEL_SIZES = ["7B", "13B", "30B", "65B", "175B"]


def _parse_benchmark_value(text: str) -> float | None:
    """Parse a numerical value from text."""
    text = text.strip().replace(",", "")
    # Handle scientific notation and decimals
    match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            pass
    return None


def _normalize_model_name(text: str) -> str:
    """Normalize model name for comparison."""
    text = text.upper()
    text = re.sub(r"[-_]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Common normalizations
    replacements = {
        "LLAMA": "LLaMA",
        "LLM": "LLM",
        "OPT-": "OPT-",
        "QWEN": "Qwen",
    }
    for old, new in replacements.items():
        if old in text:
            text = text.replace(old, new)

    return text


def _extract_structured_benchmarks(raw_benchmarks: dict) -> dict:
    """Convert raw benchmark data to structured {model: {metric: value}} format."""
    structured = {}

    # Process WikiText PPL
    for model, value in raw_benchmarks.get("WikiText-2 PPL", []):
        if not model or model == "Unknown":
            continue
        model_norm = _normalize_model_name(model)
        val = _parse_benchmark_value(value)
        if val and val > 0:
            if model_norm not in structured:
                structured[model_norm] = {}
            structured[model_norm]["WikiText2_PPL"] = val

    # Process other PPL metrics
    for metric in ["C4 PPL"]:
        for model, value in raw_benchmarks.get(metric, []):
            if not model or model == "Unknown":
                continue
            model_norm = _normalize_model_name(model)
            val = _parse_benchmark_value(value)
            if val and val > 0:
                if model_norm not in structured:
                    structured[model_norm] = {}
                key = metric.replace(" ", "_").replace("-", "_")
                structured[model_norm][key] = val

    # Process accuracy metrics
    acc_metrics = ["ARC-C", "ARC-E", "BoolQ", "HellaSwag", "PIQA", "MMLU", "GSM8K"]
    for metric in acc_metrics:
        for model, value in raw_benchmarks.get(metric, []):
            if not model or model == "Unknown":
                continue
            model_norm = _normalize_model_name(model)
            val = _parse_benchmark_value(value)
            if val is not None and 0 <= val <= 100:
                if model_norm not in structured:
                    structured[model_norm] = {}
                structured[model_norm][metric] = val

    return structured


def run_paper_analysis(args) -> int:
    """Run priority-driven paper analysis + coverage check.

    Modes:
    - coverage-only: only report existing coverage for target tiers
    - deep+coverage: generate missing analysis drafts from triage metadata, then report coverage
    """
    print("\n" + "=" * 60)
    print("STAGE: paper-analysis — Priority-driven deep analysis + coverage")
    print("=" * 60)

    priority_path = _resolve_priority_path(args)
    analysis_dir = Path(args.analysis_dir)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    if not priority_path.exists():
        print(
            f"ERROR: priority triage file not found: {priority_path} (run batch-triage first)",
            file=sys.stderr,
        )
        return 1

    targets, tier_counts = _load_priority_targets(priority_path, args.analysis_tier_scope)
    if not targets:
        print(
            f"No target papers found for scope={args.analysis_tier_scope}. Nothing to analyze.",
            file=sys.stderr,
        )
        _write_coverage_report(
            analysis_dir=analysis_dir,
            scope=args.analysis_tier_scope,
            mode=args.analysis_mode,
            policy=args.analysis_report_policy,
            target_ids=[],
            existing_ids=set(),
            generated_ids=[],
            metadata_fallback_ids=[],
            tier_counts=tier_counts,
        )
        return 0

    target_ids = sorted(targets)
    paper_index = _load_paper_index(Path(args.paper_list), Path(args.survey_root))

    if args.analysis_mode == "deep+coverage" and args.analysis_download_first:
        from stages._helpers import _ensure_local_pdf_for_targets
        dl = _ensure_local_pdf_for_targets(
            target_ids=target_ids,
            paper_index=paper_index,
            pdf_dir=Path(args.pdf_dir),
            verbose=args.verbose,
        )
        print(
            "pdf pre-download: "
            f"ready={dl['ready']} downloaded={dl['downloaded']} failed={dl['failed']}"
        )

    existing = _existing_analysis_ids(analysis_dir)
    missing = sorted([pid for pid in target_ids if pid not in existing])

    print(f"priority source: {priority_path}")
    print(f"target scope: {args.analysis_tier_scope}")
    print(f"analysis mode: {args.analysis_mode}")
    print(f"report policy: {args.analysis_report_policy}")
    print(f"target papers: {len(target_ids)}")
    print(f"analysis files found: {len(existing)}")
    print(f"missing before run: {len(missing)}")

    generated_ids: list[str] = []
    metadata_fallback_ids: list[str] = []
    if args.analysis_mode == "deep+coverage" and missing:
        generated_ids, metadata_fallback_ids = _generate_missing_analysis_drafts(
            missing_ids=missing,
            analysis_dir=analysis_dir,
            paper_index=paper_index,
            pdf_dir=Path(args.pdf_dir),
            retry_missing_pdf_download=True,
            verbose=args.verbose,
        )

    # Consolidate benchmarks: only extract for top 10 papers and save to single JSON
    if args.analysis_mode == "deep+coverage":
        # Get top 10 Tier 1 papers (or all if less than 10)
        tier1_papers = [
            pid for pid in target_ids
            if (analysis_dir / f"{pid}_analysis.md").exists()
        ][:10]

        if tier1_papers and args.verbose:
            print(f"  consolidating benchmarks for top {len(tier1_papers)} papers...")

        consolidated_benchmarks = {"models": {}}

        for pid in tier1_papers:
            pdf_path = _resolve_pdf_path(paper_index.get(pid, {}), pid, Path(args.pdf_dir))
            if not (pdf_path and pdf_path.exists()):
                continue

            try:
                from benchmark_extractor import extract_benchmarks_from_pdf
                raw_data = extract_benchmarks_from_pdf(str(pdf_path), pages_to_scan=15)
                structured = _extract_structured_benchmarks(raw_data.get("benchmarks", {}))

                # Add to consolidated benchmarks
                for model_name, metrics in structured.items():
                    if model_name not in consolidated_benchmarks["models"]:
                        consolidated_benchmarks["models"][model_name] = {}
                    consolidated_benchmarks["models"][model_name].update(metrics)

                if args.verbose:
                    print(f"  processed {pid}: {len(structured)} models")
            except Exception as exc:
                if args.verbose:
                    print(f"  benchmark extraction failed for {pid}: {exc}")

        # Write consolidated benchmark file
        if consolidated_benchmarks["models"]:
            # Save to survey root's validation dir
            survey_root = Path(args.survey_root)
            benchmark_file = survey_root / "validation" / "benchmark_survey.json"
            benchmark_file.parent.mkdir(parents=True, exist_ok=True)
            benchmark_file.write_text(json.dumps(consolidated_benchmarks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"  consolidated benchmarks: {len(consolidated_benchmarks['models'])} models saved to {benchmark_file}")

            # Also copy to tools/ for validator compatibility
            tools_benchmark = Path("tools") / "benchmark_survey.json"
            tools_benchmark.write_text(json.dumps(consolidated_benchmarks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    existing = _existing_analysis_ids(analysis_dir)
    missing = sorted([pid for pid in target_ids if pid not in existing])

    report_json, report_md = _write_coverage_report(
        analysis_dir=analysis_dir,
        scope=args.analysis_tier_scope,
        mode=args.analysis_mode,
        policy=args.analysis_report_policy,
        target_ids=target_ids,
        existing_ids=existing,
        generated_ids=generated_ids,
        metadata_fallback_ids=metadata_fallback_ids,
        tier_counts=tier_counts,
    )

    print(f"missing after run: {len(missing)}")
    if missing:
        print(f"missing sample: {', '.join(missing[:8])}")
    print(f"coverage report: {report_json}")
    print(f"coverage markdown: {report_md}")

    if args.analysis_report_policy == "strict" and missing:
        print("paper-analysis strict policy failed: missing target analyses", file=sys.stderr)
        return 1
    return 0
