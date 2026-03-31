"""Stage: paper-analysis — priority-driven deep analysis + coverage reporting."""

from __future__ import annotations

import sys
from pathlib import Path

from stages._helpers import (
    _existing_analysis_ids,
    _generate_missing_analysis_drafts,
    _load_paper_index,
    _load_priority_targets,
    _resolve_priority_path,
    _write_coverage_report,
)


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
