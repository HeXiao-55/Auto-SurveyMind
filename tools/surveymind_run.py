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
import re
import sys
from pathlib import Path
from datetime import datetime

# ─── Available stages ───────────────────────────────────────────────────────

STAGES = [
    "brainstorm",        # Stage 0: Refine fuzzy idea → SURVEY_SCOPE.md
    "arxiv-discover",    # Stage 1: Broad arXiv retrieval → arxiv_results.json
    "corpus-extract",    # Parse arxiv JSON → corpus report + tier classification
    "paper-analysis",    # Validate/prepare per-paper analysis artifacts
    "batch-triage",     # Full 12-field triage of all arxiv papers (API enrichment)
    "trace-init",        # Parse survey LaTeX → create survey_trace/ directory tree
    "trace-sync",        # Sync paper analyses → survey_trace subsection records
    "convert-12field",   # Convert 8-field analyses → 12-field with POST_TASK_QC
    "validate",          # Run citation/data/guardrails validation gate
    "all",               # Run all stages in order
]


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


def run_brainstorm(args) -> int:
    """Generate SURVEY_SCOPE.md from topic keywords or interactive dialogue."""
    print("\n" + "=" * 60)
    print("STAGE: brainstorm — Survey topic refinement")
    print("=" * 60)

    if args.scope_topic:
        # Auto-mode: generate SURVEY_SCOPE.md from provided topic
        scope_path = Path(args.scope_file)
        scope_path.parent.mkdir(parents=True, exist_ok=True)
        keywords = args.topic_keywords.split(",")
        primary_kw = keywords[0].strip() if keywords else "quantization"
        secondary_kw = ", ".join(k.strip() for k in keywords[1:] if k.strip())

        content = f"""# Survey Scope: {primary_kw.title()}

**Original idea**: {args.scope_topic}
**Refined by**: SurveyMind (auto-mode from --scope-topic)
**Date**: {datetime.now().date()}

## Refined Topic
A comprehensive survey focusing on {primary_kw} for large language models, covering algorithms, hardware co-design, and benchmark evaluation.

## Target Keywords (for arXiv search)
- **Primary**: {primary_kw}
- **Secondary**: {secondary_kw or primary_kw}

## Survey Parameters
| Parameter | Value |
|-----------|-------|
| **Bit-width focus** | Ultra-low (<2-bit) and low-bit (2-4 bit) |
| **Method scope** | PTQ + QAT |
| **Model types** | Decoder-only LLMs |
| **Primary focus** | Algorithm innovation + hardware co-design |
| **Target venue** | arXiv / survey |

## Next Steps
To proceed with the full pipeline:
```
python3 tools/surveymind_run.py --stage all --topic-keywords "{args.topic_keywords}"
```
"""
        scope_path.write_text(content, encoding="utf-8")
        print(f"SURVEY_SCOPE.md written to: {scope_path}")
        return 0

    # Interactive mode: explain how to use the skill
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║  STAGE: brainstorm — Interactive topic refinement                   ║
╠══════════════════════════════════════════════════════════════════════╣
║  For interactive brainstorming, please use the skill directly:       ║
║                                                                      ║
║      /survey-brainstorm "your fuzzy idea"                            ║
║                                                                      ║
║  Or provide --scope-topic for auto-mode:                            ║
║  Example:                                                            ║
║      python3 tools/surveymind_run.py \\                              ║
║          --stage brainstorm \\                                        ║
║          --scope-topic "ultra-low bit quantization for LLMs" \\      ║
║          --topic-keywords "quantization,LLM,binary,ternary"        ║
╚══════════════════════════════════════════════════════════════════════╝
""")
    return 0


def run_arxiv_discover(args) -> int:
    """Run broad arXiv discovery after scope confirmation."""
    print("\n" + "=" * 60)
    print("STAGE: arxiv-discover — Broad arXiv retrieval")
    print("=" * 60)

    out_path = Path(args.discover_output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "tools/arxiv_discover.py",
        "--topic-keywords", args.topic_keywords,
        "--output", str(out_path),
        "--max-per-query", str(args.discover_max_per_query),
        "--page-size", str(args.discover_page_size),
        "--max-queries", str(args.discover_max_queries),
    ]
    if args.discover_require_scope:
        cmd.append("--require-scope")
    else:
        cmd.append("--no-require-scope")
    if args.scope_file:
        cmd.extend(["--scope-file", args.scope_file])
    if args.discover_queries:
        cmd.extend(["--discover-queries", args.discover_queries])

    print(f"Running: {' '.join(cmd)}")
    import subprocess
    result = subprocess.run(cmd)

    # Use discovered arXiv results as canonical input for downstream stages.
    if result.returncode == 0:
        args.arxiv_json = str(out_path)

    return result.returncode


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
        "--output", args.output_base or args.corpus_report_base,
    ]
    if args.dry_run:
        cmd.append("--dry-run")

    print(f"Running: {' '.join(cmd)}")
    import subprocess
    result = subprocess.run(cmd)
    return result.returncode


def run_paper_analysis(args) -> int:
    """Check paper analysis coverage against paper_list.json.

    This stage does not run LLM deep reading by itself. It verifies whether
    `paper_analysis_results/*_analysis.md` covers papers in `paper_list.json`.
    """
    print("\n" + "=" * 60)
    print("STAGE: paper-analysis — Coverage check vs paper_list.json")
    print("=" * 60)

    paper_list_path = Path(args.paper_list)
    analysis_dir = Path(args.analysis_dir)

    if not paper_list_path.exists():
        print(f"ERROR: paper_list.json not found: {paper_list_path}", file=sys.stderr)
        return 1

    import json

    data = json.loads(paper_list_path.read_text(encoding="utf-8"))
    papers = data.get("papers", [])
    expected_ids = []
    for p in papers:
        pid = str(p.get("paper_id", "")).strip()
        aid = str(p.get("arXiv_id", p.get("arxiv_id", ""))).strip()
        expected_ids.append(pid or aid)
    expected_ids = [x for x in expected_ids if x]

    existing = {p.name.replace("_analysis.md", "") for p in analysis_dir.glob("*_analysis.md")}
    missing = [pid for pid in expected_ids if pid not in existing]

    print(f"paper_list entries: {len(expected_ids)}")
    print(f"analysis files found: {len(existing)}")
    print(f"missing analyses: {len(missing)}")

    if missing:
        sample = ", ".join(missing[:8])
        print(f"Missing sample: {sample}")
        print(
            "Note: deep paper analysis relies on LLM skill execution; this stage only checks coverage.",
            file=sys.stderr,
        )
        if args.fail_on_missing_analysis:
            return 1

    return 0


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
        "--output", args.output_base or args.batch_triage_base,
        "--topic-keywords", args.topic_keywords,
        "--min-score", str(args.coarse_filter_min_score),
        "--delay", "0.5",   # 500ms between API calls
    ]
    if args.coarse_prune:
        cmd.append("--coarse-prune")
    else:
        cmd.append("--no-coarse-prune")
    if args.routing_config:
        cmd.extend(["--routing-config", args.routing_config])
    if args.verbose:
        cmd.append("--verbose")

    print(f"Running: {' '.join(cmd)}")
    import subprocess
    result = subprocess.run(cmd)

    # After batch-triage completes, generate paper_list.json for Stage 2
    if result.returncode == 0:
        _generate_paper_list_from_corpus(
            corpus_path=Path((args.output_base or args.corpus_report_base) + ".json"),
            paper_list_path=Path(args.paper_list),
        )

    return result.returncode


def _generate_paper_list_from_corpus(corpus_path: Path, paper_list_path: Path):
    """Convert corpus_report.json to paper_list.json format for Stage 2."""
    if not corpus_path.exists():
        print(f"Warning: corpus report not found ({corpus_path}), skipping paper_list.json generation")
        return

    import json
    from datetime import datetime

    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    all_papers = corpus.get("all_papers", [])

    topic = corpus.get("keywords_used", ["unknown"])[0] if corpus.get("keywords_used") else "unknown"

    paper_list = {
        "topic": topic,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "description": f"Survey paper collection from arxiv_results.json ({len(all_papers)} papers)",
        "papers": []
    }

    for p in all_papers:
        arxiv_id = p.get("arxiv_id", "")
        # Extract year from published date
        published = p.get("published", "")
        year = int(published[:4]) if published and len(published) >= 4 else 2024

        # Format authors as "LastName, FirstName" style
        authors_raw = p.get("authors", [])
        authors = [a.strip() for a in authors_raw]

        paper_entry = {
            "paper_id": arxiv_id,
            "title": p.get("title", "Unknown"),
            "authors": authors,
            "year": year,
            "venue": "arXiv",
            "arXiv_id": arxiv_id,
            "category": p.get("tier", "Tier 3").split("–")[0].strip() if "–" in p.get("tier", "") else p.get("tier", "Tier 3"),
            "subcategory": "",
            "priority": "HIGH" if "Tier 1" in p.get("tier", "") else ("MED" if "Tier 2" in p.get("tier", "") else "LOW"),
            "contribution": "",
            "pdf_path": p.get("pdf_path"),
            "source": "arxiv_results.json",
            "abstract": p.get("abstract", ""),
            "tier": p.get("tier", ""),
            "score": p.get("score", 0),
            "matched_keywords": p.get("matched_keywords", [])
        }
        paper_list["papers"].append(paper_entry)

    paper_list_path.parent.mkdir(parents=True, exist_ok=True)
    paper_list_path.write_text(json.dumps(paper_list, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Generated paper_list.json: {len(paper_list['papers'])} papers")
    print(f"Tier breakdown:")
    tier_counts = {}
    for p in paper_list["papers"]:
        tier = p.get("tier", "Unknown")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    for tier, count in sorted(tier_counts.items()):
        print(f"  {tier}: {count}")


def run_validate(args) -> int:
    """Run validation gate for citations, benchmark data, and guardrails."""
    print("\n" + "=" * 60)
    print("STAGE: validate — Citation/Data/Guardrails validation")
    print("=" * 60)

    cmd = [
        sys.executable, "validation/run_validation.py",
        "--scope", args.validation_scope,
        "--retry", str(args.validation_retry),
        "--survey-root", args.survey_root,
        "--report-dir", args.validation_dir,
    ]
    if args.validation_strict:
        cmd.append("--strict")
    if args.record_guardrails_baseline:
        cmd.append("--record-guardrails-baseline")

    print(f"Running: {' '.join(cmd)}")
    import subprocess
    result = subprocess.run(cmd)
    return result.returncode


# ─── Main ─────────────────────────────────────────────────────────────────

STAGE_HANDLERS = {
    "brainstorm": run_brainstorm,
    "arxiv-discover": run_arxiv_discover,
    "corpus-extract": run_corpus_extract,
    "paper-analysis": run_paper_analysis,
    "batch-triage": run_batch_triage,
    "trace-init": run_trace_init,
    "trace-sync": run_trace_sync,
    "convert-12field": run_convert_12field,
    "validate": run_validate,
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
        default="quantization,LLM,binary,ternary,low-bit,post-training,1-bit,1.58-bit",
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
        "--routing-config",
        help="JSON routing config for trace-sync (default: built-in ultra-low bit rules)"
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

    pdf_path = Path(args.pdf_dir)
    args.pdf_dir = str(pdf_path if pdf_path.is_absolute() else (root / pdf_path).resolve())

    trace_path = Path(args.trace_dir)
    args.trace_dir = str(trace_path if trace_path.is_absolute() else (root / trace_path).resolve())

    survey_tex_path = Path(args.survey_tex)
    args.survey_tex = str(survey_tex_path if survey_tex_path.is_absolute() else (root / survey_tex_path).resolve())

    if args.output_base:
        output_path = Path(args.output_base)
        args.output_base = str(output_path if output_path.is_absolute() else (root / output_path).resolve())

    print(f"SurveyMind Pipeline — {datetime.now().date()}")
    print(f"Stage: {args.stage}")
    print(f"Project root: {root}")
    print(f"Survey root: {args.survey_root}")

    if args.stage == "all":
        # Run in dependency order. batch-triage must run before paper-analysis so
        # paper_list.json is prepared in gate1_research_lit for coverage checks.
        # brainstorm runs first (if --scope-topic provided) or prints interactive instructions.
        stages_to_run = [
            "brainstorm",
            "arxiv-discover",
            "corpus-extract",
            "batch-triage",
            "paper-analysis",
            "trace-init",
            "convert-12field",
            "trace-sync",
            "validate",
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

    print("\n" + "=" * 60)
    if failed:
        print(f"FAILED stages: {', '.join(failed)}")
        sys.exit(1)
    else:
        print(f"All stages completed successfully: {', '.join(stages_to_run)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
