#!/usr/bin/env python3
"""
surveymind_run.py — SurveyMind Pipeline Orchestrator

One-command execution of the full SurveyMind pipeline, or selective
execution of individual stages.

This is the reusable core of SurveyMind. All paths and routing rules
are parameterised so the same script works for ANY survey topic.

Usage
-----
    # Full pipeline (all stages)
    python3 tools/surveymind_run.py --stage all

    # Individual stages
    python3 tools/surveymind_run.py --stage corpus-extract
    python3 tools/surveymind_run.py --stage trace-init
    python3 tools/surveymind_run.py --stage trace-sync
    python3 tools/surveymind_run.py --stage convert-12field

    # With custom parameters
    python3 tools/surveymind_run.py \\
        --stage all \\
        --arxiv-json tpami_tem/arxiv_results.json \\
        --papers-dir my_papers \\
        --trace-dir "my idea/survey_trace" \\
        --topic-keywords "quantization,LLM,binary,ternary,1-bit,1.58-bit" \\
        --routing-config my_routing.json

Exit codes
    0  success
    1  stage not found / required file missing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime

# ─── Available stages ───────────────────────────────────────────────────────

STAGES = [
    "corpus-extract",    # Parse arxiv JSON → corpus report + tier classification
    "batch-triage",     # Full 12-field triage of all arxiv papers (API enrichment)
    "trace-init",        # Parse survey LaTeX → create survey_trace/ directory tree
    "trace-sync",        # Sync paper analyses → survey_trace subsection records
    "convert-12field",   # Convert 8-field analyses → 12-field with POST_TASK_QC
    "all",               # Run all stages in order
]


def run_corpus_extract(args) -> int:
    """Run arxiv_json_extractor to build corpus report."""
    print("\n" + "=" * 60)
    print("STAGE: corpus-extract — arXiv corpus extraction & triage")
    print("=" * 60)

    cmd = [
        sys.executable, "tools/arxiv_json_extractor.py",
        "--input", args.arxiv_json,
        "--papers-dir", args.pdf_dir,
        "--topic-keywords", args.topic_keywords,
        "--output", args.output_base or "corpus_report",
    ]
    if args.dry_run:
        cmd.append("--dry-run")

    print(f"Running: {' '.join(cmd)}")
    import subprocess
    result = subprocess.run(cmd)
    return result.returncode


def run_trace_init(args) -> int:
    """Run survey_trace_init to create directory tree from survey LaTeX."""
    print("\n" + "=" * 60)
    print("STAGE: trace-init — Survey Trace directory initialisation")
    print("=" * 60)

    if not Path(args.survey_tex).exists():
        print(f"ERROR: survey LaTeX not found: {args.survey_tex}", file=sys.stderr)
        return 1

    cmd = [
        sys.executable, "tools/survey_trace_init.py",
        "--from-tex", args.survey_tex,
        "--output-dir", args.trace_dir,
    ]
    if args.force:
        cmd.append("--force")
    if args.dry_run:
        cmd.append("--dry-run")
    if args.verbose:
        cmd.append("--verbose")

    print(f"Running: {' '.join(cmd)}")
    import subprocess
    result = subprocess.run(cmd)
    return result.returncode


def run_trace_sync(args) -> int:
    """Run survey_trace_sync to populate subsection records."""
    print("\n" + "=" * 60)
    print("STAGE: trace-sync — Paper analyses → Survey Trace sync")
    print("=" * 60)

    cmd = [
        sys.executable, "tools/survey_trace_sync.py",
        "--papers-dir", args.analysis_dir,
        "--trace-dir", args.trace_dir,
    ]
    if args.routing_config:
        cmd.extend(["--routing-config", args.routing_config])
    if args.dry_run:
        cmd.append("--dry-run")
    if args.verbose:
        cmd.append("--verbose")

    print(f"Running: {' '.join(cmd)}")
    import subprocess
    result = subprocess.run(cmd)
    return result.returncode


def run_convert_12field(args) -> int:
    """Run convert_to_12field to upgrade analyses to 12-field format."""
    print("\n" + "=" * 60)
    print("STAGE: convert-12field — 8-field → 12-field conversion")
    print("=" * 60)

    cmd = [
        sys.executable, "tools/convert_to_12field.py",
        "--papers-dir", args.analysis_dir,
    ]
    if args.output_dir:
        cmd.extend(["--output-dir", args.output_dir])
    if args.dry_run:
        cmd.append("--dry-run")
    if args.verbose:
        cmd.append("--verbose")

    print(f"Running: {' '.join(cmd)}")
    import subprocess
    result = subprocess.run(cmd)
    return result.returncode


def run_batch_triage(args) -> int:
    """Run batch_paper_triage to classify all arxiv papers with API enrichment."""
    print("\n" + "=" * 60)
    print("STAGE: batch-triage — Full 12-field classification via arXiv API")
    print("=" * 60)

    cmd = [
        sys.executable, "tools/batch_paper_triage.py",
        "--input", args.arxiv_json,
        "--output", args.output_base or "all_papers_triage",
        "--topic-keywords", args.topic_keywords,
        "--delay", "0.5",   # 500ms between API calls
    ]
    if args.routing_config:
        cmd.extend(["--routing-config", args.routing_config])
    if args.verbose:
        cmd.append("--verbose")

    print(f"Running: {' '.join(cmd)}")
    import subprocess
    result = subprocess.run(cmd)
    return result.returncode


# ─── Main ─────────────────────────────────────────────────────────────────

STAGE_HANDLERS = {
    "corpus-extract": run_corpus_extract,
    "batch-triage": run_batch_triage,
    "trace-init": run_trace_init,
    "trace-sync": run_trace_sync,
    "convert-12field": run_convert_12field,
}


def main():
    ap = argparse.ArgumentParser(
        description="SurveyMind Pipeline Orchestrator — reusable survey tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--stage", "-s", default="all",
        choices=STAGES,
        help="Pipeline stage to run (default: all)"
    )
    ap.add_argument(
        "--arxiv-json",
        default="tpami_tem/arxiv_results.json",
        help="Path to arXiv search results JSON (default: tpami_tem/arxiv_results.json)"
    )
    ap.add_argument(
        "--analysis-dir",
        default="paper_analysis_results",
        help="Directory containing paper analysis .md files (default: paper_analysis_results)"
    )
    ap.add_argument(
        "--pdf-dir",
        default="papers",
        help="Directory containing downloaded PDFs (default: papers)"
    )
    ap.add_argument(
        "--trace-dir",
        default="my idea/survey_trace",
        help="Root of survey_trace directory (default: my idea/survey_trace)"
    )
    ap.add_argument(
        "--survey-tex",
        default="tpami_tem/literature_review_survey.tex",
        help="Survey LaTeX file for trace-init (default: tpami_tem/literature_review_survey.tex)"
    )
    ap.add_argument(
        "--topic-keywords", "-k",
        default="quantization,LLM,binary,ternary,low-bit,post-training,1-bit,1.58-bit",
        help="Comma-separated topic keywords for relevance scoring"
    )
    ap.add_argument(
        "--routing-config",
        help="JSON routing config for trace-sync (default: built-in ultra-low bit rules)"
    )
    ap.add_argument(
        "--output-base",
        help="Base name for output files (e.g. corpus_report)"
    )
    ap.add_argument(
        "--output-dir",
        help="Output directory for 12-field conversion (default: in-place)"
    )
    ap.add_argument(
        "--force", action="store_true",
        help="Force recreate trace dir (for trace-init)"
    )
    ap.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Run stages in dry-run mode where supported"
    )
    ap.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output"
    )

    args = ap.parse_args()

    root = Path(__file__).parent.parent

    # Resolve paths relative to project root
    args.arxiv_json = str(root / args.arxiv_json)
    args.analysis_dir = str(root / args.analysis_dir)
    args.pdf_dir = str(root / args.pdf_dir)
    args.trace_dir = str(root / args.trace_dir)
    args.survey_tex = str(root / args.survey_tex)
    if args.output_base:
        args.output_base = str(root / args.output_base)

    print(f"SurveyMind Pipeline — {datetime.now().date()}")
    print(f"Stage: {args.stage}")
    print(f"Project root: {root}")

    if args.stage == "all":
        # Run in dependency order; skip batch-triage in dry-run mode
        stages_to_run = ["corpus-extract", "trace-init", "convert-12field", "trace-sync"]
        if not args.dry_run:
            stages_to_run.insert(1, "batch-triage")  # add API stage only for real runs
    else:
        stages_to_run = [args.stage]

    failed = []
    for stage in stages_to_run:
        handler = STAGE_HANDLERS.get(stage)
        if not handler:
            print(f"ERROR: unknown stage '{stage}'", file=sys.stderr)
            sys.exit(1)
        rc = handler(args)
        if rc != 0:
            print(f"\nSTAGE FAILED: {stage} (exit {rc})", file=sys.stderr)
            failed.append(stage)

    print("\n" + "=" * 60)
    if failed:
        print(f"FAILED stages: {', '.join(failed)}")
        sys.exit(1)
    else:
        print(f"All stages completed successfully: {', '.join(stages_to_run)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
