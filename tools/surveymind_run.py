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
    python3 tools/surveymind_run.py --stage taxonomy-alloc

    # With custom parameters
    python3 tools/surveymind_run.py \\
        --stage all \\
        --arxiv-json tpami_tem/arxiv_results.json \\
        --papers-dir my_papers \\
        --trace-dir "my idea/survey_trace" \\
        --topic-keywords "{keyword1},{keyword2},{keyword3}" \\
        --routing-config my_routing.json

Exit codes
    0  success
    1  stage not found / required file missing
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from domain_profile import DomainProfileError, load_domain_profile
from stages import (
    run_arxiv_discover,
    run_batch_triage,
    run_brainstorm,
    run_corpus_extract,
    run_gap_identify,
    run_paper_analysis,
    run_paper_download,
    run_survey_write,
    run_taxonomy_build,
    run_taxonomy_alloc,
    run_trace_init,
    run_trace_sync,
    run_validate,
    run_validate_and_improve,
)

STAGES = [
    "brainstorm",        # Stage 0: Refine fuzzy idea → SURVEY_SCOPE.md
    "arxiv-discover",    # Stage 1: Broad arXiv retrieval → arxiv_results.json
    "corpus-extract",    # Parse arxiv JSON → corpus report + tier classification
    "paper-download",    # Download PDFs for target tiers before deep analysis
    "paper-analysis",    # Validate/prepare per-paper analysis artifacts
    "batch-triage",     # Full multi-field triage of all arxiv papers (API enrichment)
    "taxonomy-build",    # Build taxonomy from analysis artifacts
    "gap-identify",      # Identify structured research gaps from taxonomy
    "survey-write",      # Synthesize survey draft from taxonomy + gaps
    "trace-init",        # Parse survey LaTeX → create survey_trace/ directory tree
    "trace-sync",        # Sync paper analyses → survey_trace subsection records
    "taxonomy-alloc",   # Taxonomy-based allocation of papers to subsections
    "validate",          # Run citation/data/guardrails validation gate
    "validate-and-improve",  # Run validation and auto-improve based on results
    "all",               # Run all stages in order
]

TIER_SCOPE_MAP = {
    "tier1": {"Tier 1 – Core"},
    "tier1_tier2": {"Tier 1 – Core", "Tier 2 – High Relevance"},
    "tier3_tier4": {"Tier 3 – Related", "Tier 4 – Peripheral"},
    "all": {
        "Tier 1 – Core",
        "Tier 2 – High Relevance",
        "Tier 3 – Related",
        "Tier 4 – Peripheral",
    },
}

def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "default"


def _default_survey_name(args) -> str:
    if args.survey_name:
        return args.survey_name
    if args.scope_topic:
        return args.scope_topic
    return args.topic_keywords.split(",")[0].strip() or "default"


def _resolve_survey_paths(args, project_root: Path) -> None:
    survey_name = _slugify(_default_survey_name(args))
    if args.survey_root:
        survey_root = Path(args.survey_root)
        if not survey_root.is_absolute():
            survey_root = (project_root / survey_root).resolve()
    else:
        survey_root = (project_root / "surveys" / f"survey_{survey_name}").resolve()

    args.survey_root = str(survey_root)
    args.gate0_dir = str(survey_root / "gate0_scope")
    args.gate1_dir = str(survey_root / "gate1_research_lit")
    args.gate2_dir = str(survey_root / "gate2_paper_analysis")
    args.gate3_dir = str(survey_root / "gate3_taxonomy")
    args.gate4_dir = str(survey_root / "gate4_gap_analysis")
    args.gate5_dir = str(survey_root / "gate5_survey_write")
    args.validation_dir = str(survey_root / "validation" / "reports")

    args.scope_file = str(Path(args.gate0_dir) / "SURVEY_SCOPE.md")
    args.paper_list = str(Path(args.gate1_dir) / "paper_list.json")
    args.corpus_report_base = str(Path(args.gate1_dir) / "corpus_report")
    args.batch_triage_base = str(Path(args.gate2_dir) / "all_papers_triage")
    args.discover_output = str(Path(args.gate1_dir) / "arxiv_results.json")

    if not args.analysis_dir:
        args.analysis_dir = args.gate2_dir
    if not args.pdf_dir:
        args.pdf_dir = str(Path(args.gate1_dir) / "papers")
    if not args.trace_dir:
        args.trace_dir = str(Path(survey_root) / "survey_trace")

    # Ensure destination directories exist for deterministic writes.
    for p in [
        args.gate0_dir,
        args.gate1_dir,
        args.gate2_dir,
        args.gate3_dir,
        args.gate4_dir,
        args.gate5_dir,
        str(Path(survey_root) / "survey_trace"),
        args.validation_dir,
    ]:
        Path(p).mkdir(parents=True, exist_ok=True)


STAGE_HANDLERS = {
    "brainstorm": run_brainstorm,
    "arxiv-discover": run_arxiv_discover,
    "corpus-extract": run_corpus_extract,
    "paper-download": run_paper_download,
    "paper-analysis": run_paper_analysis,
    "batch-triage": run_batch_triage,
    "taxonomy-build": run_taxonomy_build,
    "gap-identify": run_gap_identify,
    "survey-write": run_survey_write,
    "trace-init": run_trace_init,
    "trace-sync": run_trace_sync,
    "taxonomy-alloc": run_taxonomy_alloc,
    "validate": run_validate,
    "validate-and-improve": run_validate_and_improve,
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
        "--survey-root",
        default=None,
        help="Survey output root directory. Default: surveys/survey_<slug>/"
    )
    ap.add_argument(
        "--survey-name",
        default=None,
        help="Survey name used to build default survey root when --survey-root is omitted"
    )
    ap.add_argument(
        "--arxiv-json",
        default=None,
        help="Path to arXiv search results JSON. If omitted, uses discovered gate1 arxiv_results.json"
    )
    ap.add_argument(
        "--analysis-dir",
        default=None,
        help="Directory containing paper analysis .md files (default: <survey>/gate2_paper_analysis)"
    )
    ap.add_argument(
        "--pdf-dir",
        default=None,
        help="Directory containing downloaded PDFs (default: <survey>/gate1_research_lit/papers)"
    )
    ap.add_argument(
        "--trace-dir",
        default=None,
        help="Root of survey_trace directory (default: <survey>/survey_trace)"
    )
    ap.add_argument(
        "--survey-tex",
        default="tpami_tem/literature_review_survey.tex",
        help="Survey LaTeX file for trace-init (default: tpami_tem/literature_review_survey.tex)"
    )
    ap.add_argument(
        "--topic-keywords", "-k",
        default="machine learning,survey,benchmark",
        help="Comma-separated topic keywords for relevance scoring"
    )
    ap.add_argument(
        "--discover-queries",
        help="Optional semicolon-separated arXiv broad-search queries overriding keyword expansion"
    )
    ap.add_argument(
        "--discover-max-per-query",
        type=int,
        default=80,
        help="Max papers to retrieve per broad-search query (default: 80)"
    )
    ap.add_argument(
        "--discover-page-size",
        type=int,
        default=40,
        help="arXiv API page size per request during discovery (default: 40)"
    )
    ap.add_argument(
        "--discover-max-queries",
        type=int,
        default=8,
        help="Max number of expanded discovery queries (default: 8)"
    )
    ap.add_argument(
        "--discover-arxiv",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable broad arXiv discovery stage in --stage all (default: on)"
    )
    ap.add_argument(
        "--discover-require-scope",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require scope-derived terms (or explicit discover queries) for arxiv-discover (default: on)",
    )
    ap.add_argument(
        "--scope-topic",
        help="Survey topic description for auto-mode brainstorm (generates SURVEY_SCOPE.md)"
    )
    ap.add_argument(
        "--literature-scope",
        default="standard",
        choices=["focused", "standard", "comprehensive"],
        help="Literature coverage scope: focused (~20-30), standard (~50-100, default), comprehensive (~100-200)"
    )
    ap.add_argument(
        "--routing-config",
        help="JSON routing config for trace-sync (default: built-in generic rules)"
    )
    ap.add_argument(
        "--domain-profile",
        default="templates/domain_profiles/general_profile.json",
        help="Domain profile JSON path controlling relevance and routing defaults",
    )
    ap.add_argument(
        "--coarse-prune",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable coarse framework-aware pruning in batch-triage (default: on)"
    )
    ap.add_argument(
        "--coarse-filter-min-score",
        type=int,
        choices=[0, 1, 2, 3],
        default=0,
        help="Minimum relevance score for coarse filter (default: 0, high-recall)"
    )
    ap.add_argument(
        "--output-base",
        help="Base name for output files (e.g. corpus_report)"
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
    ap.add_argument(
        "--validation-scope",
        default="all",
        choices=["citations", "benchmarks", "guardrails", "all"],
        help="Validation scope for validate stage (default: all)"
    )
    ap.add_argument(
        "--validation-retry",
        type=int,
        default=2,
        help="Retry times for validation re-fetch/re-extract (default: 2)"
    )
    ap.add_argument(
        "--validation-strict",
        action="store_true",
        help="Enable strict mode in validation gate"
    )
    ap.add_argument(
        "--record-guardrails-baseline",
        action="store_true",
        help="Record current changed files as guardrails baseline"
    )
    ap.add_argument(
        "--fail-on-missing-analysis",
        action="store_true",
        help="Fail paper-analysis stage if any paper in paper_list.json lacks *_analysis.md"
    )
    ap.add_argument(
        "--analysis-tier-scope",
        default="tier1_tier2",
        choices=["tier1", "tier1_tier2", "tier3_tier4", "all"],
        help="Target priority tiers for paper-analysis stage (default: tier1_tier2)",
    )
    ap.add_argument(
        "--analysis-mode",
        default="deep+coverage",
        choices=["coverage-only", "deep+coverage"],
        help="paper-analysis behavior: only check coverage or generate missing drafts then check (default: deep+coverage)",
    )
    ap.add_argument(
        "--analysis-report-policy",
        default="report-only",
        choices=["strict", "report-only"],
        help="Coverage policy for paper-analysis stage (default: report-only)",
    )
    ap.add_argument(
        "--analysis-download-first",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Download missing PDFs for target tiers before deep analysis (default: on)",
    )
    ap.add_argument(
        "--analysis-priority-json",
        default="gate2_paper_analysis/all_papers_triage",
        help="Priority triage file path relative to survey root or absolute path (default: gate2_paper_analysis/all_papers_triage)",
    )
    ap.add_argument(
        "--download-tier-scope",
        default="tier1_tier2",
        choices=["tier1", "tier1_tier2", "tier3_tier4", "all"],
        help="Target priority tiers for paper-download stage (default: tier1_tier2)",
    )
    ap.add_argument(
        "--download-policy",
        default="report-only",
        choices=["strict", "report-only"],
        help="Failure policy for paper-download stage (default: report-only)",
    )
    ap.add_argument(
        "--trace-init-missing-policy",
        default="skip",
        choices=["skip", "fail"],
        help="Behavior when --survey-tex is missing in trace-init stage (default: skip)",
    )
    ap.add_argument(
        "--fail-fast",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stop pipeline immediately when a stage fails (default: on)",
    )

    args = ap.parse_args()

    root = Path(__file__).parent.parent.resolve()

    _resolve_survey_paths(args, root)

    # Resolve paths relative to project root
    if args.arxiv_json:
        arxiv_path = Path(args.arxiv_json)
        args.arxiv_json = str(arxiv_path if arxiv_path.is_absolute() else (root / arxiv_path).resolve())
    else:
        args.arxiv_json = args.discover_output

    analysis_path = Path(args.analysis_dir)
    args.analysis_dir = str(analysis_path if analysis_path.is_absolute() else (root / analysis_path).resolve())

    priority_path = Path(args.analysis_priority_json)
    if priority_path.is_absolute():
        args.analysis_priority_json = str(priority_path)
    else:
        # keep it survey-root-relative for _resolve_priority_path
        args.analysis_priority_json = str(priority_path)

    if args.fail_on_missing_analysis:
        args.analysis_report_policy = "strict"

    pdf_path = Path(args.pdf_dir)
    args.pdf_dir = str(pdf_path if pdf_path.is_absolute() else (root / pdf_path).resolve())

    trace_path = Path(args.trace_dir)
    args.trace_dir = str(trace_path if trace_path.is_absolute() else (root / trace_path).resolve())

    survey_tex_path = Path(args.survey_tex)
    args.survey_tex = str(survey_tex_path if survey_tex_path.is_absolute() else (root / survey_tex_path).resolve())

    if args.output_base:
        output_path = Path(args.output_base)
        args.output_base = str(output_path if output_path.is_absolute() else (root / output_path).resolve())

    try:
        _, profile_path = load_domain_profile(args.domain_profile, root)
    except DomainProfileError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    args.domain_profile = str(profile_path)

    print(f"SurveyMind Pipeline — {datetime.now().date()}")
    print(f"Stage: {args.stage}")
    print(f"Project root: {root}")
    print(f"Survey root: {args.survey_root}")
    print(f"Domain profile: {args.domain_profile}")

    if args.stage == "all":
        # Run in dependency order. batch-triage must run before paper-analysis so
        # paper_list.json is prepared in gate1_research_lit for coverage checks.
        # brainstorm runs first (if --scope-topic provided) or prints interactive instructions.
        stages_to_run = [
            "brainstorm",
            "arxiv-discover",
            "corpus-extract",
            "batch-triage",
            "paper-download",
            "paper-analysis",
            "taxonomy-build",
            "gap-identify",
            "survey-write",
            "trace-init",
            "taxonomy-alloc",
            "trace-sync",
            "validate-and-improve",
        ]
        if not args.discover_arxiv:
            stages_to_run = [s for s in stages_to_run if s != "arxiv-discover"]
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
            if args.fail_fast:
                break

    print("\n" + "=" * 60)
    if failed:
        print(f"FAILED stages: {', '.join(failed)}")
        sys.exit(1)
    else:
        print(f"All stages completed successfully: {', '.join(stages_to_run)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
