#!/usr/bin/env python3
"""Initialise the project root findings.md file.

Creates findings.md with the standardised header if it does not exist,
or if it exists but is missing the header marker.

Usage
-----
    python3 tools/init_findings.py          # interactive (creates if missing)
    python3 tools/init_findings.py --force  # recreate from scratch
    python3 tools/init_findings.py --check   # just check status, no write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FINDINGS_PATH = PROJECT_ROOT / "findings.md"
HEADER_MARKER = "> **格式规范**"   # presence of this line = already initialised
DEPRECATION_NOTICE = (
    "# ⚠️  DEPRECATED — templates/FINDINGS_TEMPLATE.md is no longer used.\n"
    "# Content has moved to: ../findings.md (project root)\n\n"
)


STANDARD_HEADER = """\
# Research Findings

> **格式规范**：每个条目以 `## [YYYY-MM-DD] {Topic}` 开头，后跟 3–5 个固定字段。
> 所有字段可选，但出现的字段必须使用此格式，否则 grep/解析工具无法识别。

---

## Research Findings

### [YYYY-MM-DD] Topic

- **Finding**:  一句话描述（必须用 "Finding" 字段）
- **Evidence**: 来源，支持的指标或引用（paper_id、URL、wandb run 等）
- **Confidence**: high / medium / low
- **Context**: 什么情况下成立，什么情况下不成立（可选）
- **Tags**: comma-separated 标签，便于 grep（可选）

---

## Engineering Findings

### [YYYY-MM-DD] Topic

- **Problem**: 问题描述
- **Root Cause**: 根本原因
- **Fix Applied**: 应用的修复方案
"""


def check_status(path: Path) -> str:
    """Return 'ok' | 'missing' | 'needs_header'."""
    if not path.exists():
        return "missing"
    content = path.read_text(encoding="utf-8")
    if HEADER_MARKER in content:
        return "ok"
    return "needs_header"


def init_findings(force: bool = False) -> None:
    status = check_status(FINDINGS_PATH)

    if status == "ok" and not force:
        print(f"[init_findings] findings.md already initialised: {FINDINGS_PATH}")
        return

    if status == "missing":
        FINDINGS_PATH.write_text(STANDARD_HEADER, encoding="utf-8")
        print(f"[init_findings] created findings.md: {FINDINGS_PATH}")
        return

    if status == "needs_header":
        if force:
            FINDINGS_PATH.write_text(STANDARD_HEADER, encoding="utf-8")
            print(f"[init_findings] overwritten findings.md (--force): {FINDINGS_PATH}")
        else:
            print(f"[init_findings] findings.md exists but is missing the standardised header.")
            print(f"  Run with --force to overwrite it, or manually add the header.")
            print(f"  Path: {FINDINGS_PATH}")
            sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialise project root findings.md")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Overwrite existing findings.md with the standardised header")
    parser.add_argument("--check", "-c", action="store_true",
                        help="Only check status, do not write anything")
    args = parser.parse_args()

    if args.check:
        status = check_status(FINDINGS_PATH)
        print(f"findings.md status: {status} ({FINDINGS_PATH})")
        return 0

    init_findings(force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
