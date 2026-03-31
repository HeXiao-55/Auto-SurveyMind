#!/usr/bin/env python3
"""Atomic write utilities for SurveyMind.

Replaces bare ``path.write_text()`` / ``path.write_bytes()`` calls that can
leave corrupted files when the process is killed mid-write.

Usage
-----
    from atomic_write import atomic_write_text, atomic_write_json

    atomic_write_text(path, content)
    atomic_write_json(path, data, indent=2)

    # Also works for bytes
    atomic_write_bytes(path, pdf_data)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _write(path: Path, content: Any, encoding: str = "utf-8") -> None:
    """Write content to path atomically via temp-file rename.

    Writes to a temp file in the same directory (ensuring same filesystem
    for atomic rename), then atomically replaces the target via Path.replace().
    """
    path = Path(path)
    dir_path = path.parent
    dir_path.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        suffix=path.suffix + ".tmp",
        prefix="." + path.name,
        dir=str(dir_path),
    )
    try:
        mode = "wb" if isinstance(content, bytes) else "w"
        enc = encoding if isinstance(content, str) else None
        with os.fdopen(fd, mode=mode, encoding=enc) as fh:
            fh.write(content)
        Path(tmp_path).replace(path)
    except Exception:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def atomic_write_text(path: str | Path, content: str) -> None:
    """Atomically write a text file."""
    _write(Path(path), content)


def atomic_write_bytes(path: str | Path, content: bytes) -> None:
    """Atomically write a binary file."""
    _write(Path(path), content)


def atomic_write_json(
    path: str | Path,
    data: Any,
    *,
    indent: int | None = 2,
    ensure_ascii: bool = False,
) -> None:
    """Atomically write a JSON file.

    Parameters
    ----------
    path : Path
        Destination file path.
    data : Any
        JSON-serialisable object.
    indent : int | None
        Passed to ``json.dumps``. Use ``None`` for compact single-line output.
    ensure_ascii : bool
        Passed to ``json.dumps``.
    """
    if indent is None:
        content = json.dumps(data, indent=None, ensure_ascii=ensure_ascii, separators=(",", ":"))
    else:
        content = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
    atomic_write_text(path, content)


# ── Convenience wrappers for SurveyMind tools ──────────────────────────────────

def write_analysis(path: str | Path, content: str) -> None:
    """Atomically write a paper analysis markdown file."""
    atomic_write_text(path, content)


def write_json_report(path: str | Path, data: dict) -> None:
    """Atomically write a JSON report (paper_list, corpus_report, etc.)."""
    atomic_write_json(path, data)
