"""Stage: paper-download — priority-driven PDF download."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

from stages._helpers import (
    _ensure_local_pdf_for_targets,
    _load_paper_index,
    _load_priority_targets,
    _resolve_priority_path,
)


def run_paper_download(args) -> int:
    """Download PDFs for target tiers from triage output."""
    print("\n" + "=" * 60)
    print("STAGE: paper-download — Priority-driven PDF download")
    print("=" * 60)

    priority_path = _resolve_priority_path(args)
    if not priority_path.exists():
        print(
            f"ERROR: priority triage file not found: {priority_path} (run batch-triage first)",
            file=sys.stderr,
        )
        return 1

    targets, tier_counts = _load_priority_targets(priority_path, args.download_tier_scope)
    target_ids = sorted(targets)
    if not target_ids:
        print(f"No target papers found for scope={args.download_tier_scope}. Nothing to download.")
        return 0

    paper_index = _load_paper_index(Path(args.paper_list), Path(args.survey_root))
    dl = _ensure_local_pdf_for_targets(
        target_ids=target_ids,
        paper_index=paper_index,
        pdf_dir=Path(args.pdf_dir),
        verbose=args.verbose,
    )

    print(f"priority source: {priority_path}")
    print(f"download scope: {args.download_tier_scope}")
    print(f"target papers: {len(target_ids)}")
    for tier, count in sorted(tier_counts.items()):
        print(f"  {tier}: {count}")
    print(f"pdf ready: {dl['ready']}")
    print(f"pdf downloaded now: {dl['downloaded']}")
    print(f"pdf failed: {dl['failed']}")
    failed_ids = cast(list[str], dl["failed_ids"])
    failed_count = cast(int, dl["failed"])
    if failed_ids:
        print(f"failed sample: {', '.join(failed_ids[:8])}")

    if args.download_policy == "strict" and failed_count > 0:
        print("paper-download strict policy failed: some PDFs could not be downloaded", file=sys.stderr)
        return 1
    return 0
