"""Thin pipeline stages that delegate to CLI tools via subprocess."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── brainstorm ─────────────────────────────────────────────────────────────────

def run_brainstorm(args) -> int:
    """Generate SURVEY_SCOPE.md from topic keywords or interactive dialogue."""
    print("\n" + "=" * 60)
    print("STAGE: brainstorm — Survey topic refinement")
    print("=" * 60)

    if args.scope_topic:
        scope_path = Path(args.scope_file)
        scope_path.parent.mkdir(parents=True, exist_ok=True)
        keywords = args.topic_keywords.split(",")
        primary_kw = keywords[0].strip() if keywords else "research topic"
        secondary_kw = ", ".join(k.strip() for k in keywords[1:] if k.strip())
        literature_scope = getattr(args, 'literature_scope', 'standard')

        # Map literature scope to paper count
        scope_papers = {
            "focused": "~20-30 papers",
            "standard": "~50-100 papers",
            "comprehensive": "~100-200 papers",
        }
        papers_desc = scope_papers.get(literature_scope, "~50-100 papers")

        content = f"""# Survey Scope: {primary_kw.title()}

**Original idea**: {args.scope_topic}
**Refined by**: SurveyMind (auto-mode from --scope-topic)
**Date**: {datetime.now().date()}

## Refined Topic
A comprehensive survey focusing on {primary_kw}, covering representative methods, evaluation protocols, application settings, and open challenges.

## Target Keywords (for arXiv search)
- **Primary**: {primary_kw}
- **Secondary**: {secondary_kw or primary_kw}

## Literature Coverage
| Parameter | Value |
|-----------|-------|
| **Literature scope** | {literature_scope.capitalize()} ({papers_desc}) |
| **Target papers** | {papers_desc} |

## Survey Parameters
| Parameter | Value |
|-----------|-------|
| **Method scope** | Determined from scope and keyword evidence |
| **Target entities** | Determined from scope and keyword evidence |
| **Primary focus** | Methods, benchmarks, and practical challenges |
| **Target venue** | arXiv / survey |

## Next Steps
To proceed with the full pipeline:
```
python3 tools/surveymind_run.py --stage all --topic-keywords "{args.topic_keywords}" --literature-scope {literature_scope}
```
"""
        scope_path.write_text(content, encoding="utf-8")
        print(f"SURVEY_SCOPE.md written to: {scope_path}")
        print(f"Literature scope: {literature_scope.capitalize()} ({papers_desc})")
        return 0

    print("""
╔══════════════════════════════════════════════════════════════════════╗
║  STAGE: brainstorm — Interactive topic refinement                   ║
╠══════════════════════════════════════════════════════════════════════╣
║  For interactive brainstorming, please use the skill directly:       ║
║                                                                        ║
║      /survey-brainstorm "your fuzzy idea"                              ║
║                                                                        ║
║  Or provide --scope-topic for auto-mode:                               ║
║  Example:                                                             ║
║      python3 tools/surveymind_run.py \\                                  ║
║          --stage brainstorm \\                                           ║
║          --scope-topic "graph neural network robustness" \\            ║
║          --topic-keywords "graph neural network,robustness,adversarial"║
╚══════════════════════════════════════════════════════════════════════╝
""")
    return 0


# ── arxiv-discover ───────────────────────────────────────────────────────────────

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
    result = subprocess.run(cmd)

    # Use discovered arXiv results as canonical input for downstream stages.
    if result.returncode == 0:
        args.arxiv_json = str(out_path)

    return result.returncode


# ── corpus-extract ─────────────────────────────────────────────────────────────

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
        "--domain-profile", args.domain_profile,
    ]
    if args.dry_run:
        cmd.append("--dry-run")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


# ── trace-init ─────────────────────────────────────────────────────────────────

def run_trace_init(args) -> int:
    """Run survey_trace_init to create directory tree from survey LaTeX."""
    print("\n" + "=" * 60)
    print("STAGE: trace-init — Survey Trace directory initialisation")
    print("=" * 60)

    if not Path(args.survey_tex).exists():
        if getattr(args, "trace_init_missing_policy", "skip") == "skip":
            print(f"WARN: survey LaTeX not found, skipping trace-init: {args.survey_tex}")
            return 0
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
    result = subprocess.run(cmd)
    return result.returncode


# ── trace-sync ─────────────────────────────────────────────────────────────────

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
    if args.domain_profile:
        cmd.extend(["--domain-profile", args.domain_profile])
    if args.dry_run:
        cmd.append("--dry-run")
    if args.verbose:
        cmd.append("--verbose")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


# ── taxonomy-alloc ─────────────────────────────────────────────────────────────

def run_taxonomy_alloc(args) -> int:
    """Run taxonomy_alloc to derive paper fields from taxonomy and auto-generate routing."""
    print("\n" + "=" * 60)
    print("STAGE: taxonomy-alloc — Taxonomy-based field derivation and routing")
    print("=" * 60)

    cmd = [
        sys.executable, "tools/taxonomy_alloc.py",
        "--analysis-dir", args.analysis_dir,
        "--taxonomy-dir", args.gate3_dir,
        "--domain-profile", args.domain_profile,
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.verbose:
        cmd.append("--verbose")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


# ── batch-triage ─────────────────────────────────────────────────────────────────

def run_batch_triage(args) -> int:
    """Run batch_paper_triage to classify all arxiv papers with API enrichment."""
    print("\n" + "=" * 60)
    print("STAGE: batch-triage — Full multi-field classification via arXiv API")
    print("=" * 60)

    cmd = [
        sys.executable, "tools/batch_paper_triage.py",
        "--input", args.arxiv_json,
        "--output", args.output_base or args.batch_triage_base,
        "--topic-keywords", args.topic_keywords,
        "--min-score", str(args.coarse_filter_min_score),
        "--delay", "0.5",
    ]
    if args.coarse_prune:
        cmd.append("--coarse-prune")
    else:
        cmd.append("--no-coarse-prune")
    if args.routing_config:
        cmd.extend(["--routing-config", args.routing_config])
    if args.domain_profile:
        cmd.extend(["--domain-profile", args.domain_profile])
    if args.verbose:
        cmd.append("--verbose")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    # After batch-triage completes, generate paper_list.json for Stage 2
    if result.returncode == 0:
        from stages._helpers import _generate_paper_list_from_corpus
        _generate_paper_list_from_corpus(
            corpus_path=Path((args.output_base or args.corpus_report_base) + ".json"),
            paper_list_path=Path(args.paper_list),
        )

    return result.returncode


# ── validate ───────────────────────────────────────────────────────────────────

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
    if args.verbose:
        cmd.append("--verbose")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode
