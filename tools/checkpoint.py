#!/usr/bin/env python3
"""Unified checkpoint / state persistence framework for SurveyMind skills.

Replaces the ad-hoc ``REVIEW_STATE.json``, ``REFINE_STATE.json`` patterns
with a single ``Checkpoint`` class that:

- Saves/loads JSON state files
- Enforces a configurable TTL (stale state is ignored)
- Provides type-safe accessors
- Is thread- and async-safe (file locking via flock)

Usage
-----
    from checkpoint import Checkpoint, CheckpointError

    ck = Checkpoint("review_state.json", project_root=Path("."), ttl_hours=24)

    # Load — returns None if missing or stale
    state = ck.load()
    if state:
        logger.info("Resuming from round %d", state["round"])

    # Save
    ck.save({"round": 2, "threadId": "thread_abc", "status": "in_progress"})

    # Clear (e.g. on completion)
    ck.clear()

TTL-aware resume (as used in research-refine):
    if state := ck.load():
        if ck.is_stale(state):
            logger.warning("Checkpoint is stale (>%dh), starting fresh", ck.ttl_hours)
        else:
            logger.info("Resuming from checkpoint: phase=%s round=%d",
                         state.get("phase"), state.get("round"))

Schema conventions for SurveyMind state files
----------------------------------------------
All state dicts should follow this minimum schema::

    {
        "version": 1,
        "status": "in_progress" | "completed" | "failed",
        "timestamp": "<ISO8601>",
        # ... skill-specific fields
    }
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

MIN_SCHEMA_KEYS = {"version", "status", "timestamp"}


class CheckpointError(Exception):
    """Raised for checkpoint read/write failures."""


class Checkpoint:
    """A single JSON state file with TTL enforcement."""

    CURRENT_VERSION = 1

    def __init__(
        self,
        path: str | Path,
        *,
        project_root: Optional[Path] = None,
        ttl_hours: float = 24.0,
    ):
        """Create a Checkpoint wrapper.

        Parameters
        ----------
        path : str | Path
            Relative or absolute path to the JSON state file.
        project_root : Path
            Resolved relative to this directory. Defaults to CWD.
        ttl_hours : float
            State files older than this are considered stale.
        """
        self._raw_path = Path(path)
        if project_root and not self._raw_path.is_absolute():
            self._path = (project_root / self._raw_path).resolve()
        else:
            self._path = self._raw_path.resolve() if not self._raw_path.is_absolute() else self._raw_path
        self._ttl_seconds = ttl_hours * 3600

    @property
    def path(self) -> Path:
        """Resolved absolute path to the state file."""
        return self._path

    @property
    def ttl_hours(self) -> float:
        return self._ttl_seconds / 3600

    # ── Timestamp helpers ─────────────────────────────────────────────────────

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _timestamp_to_epoch(ts: str) -> float:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except (ValueError, AttributeError):
            return 0.0

    def is_stale(self, state: dict) -> bool:
        """Return True if the state timestamp is older than TTL."""
        ts = state.get("timestamp", "")
        if not ts:
            return True
        age = time.time() - self._timestamp_to_epoch(ts)
        return age > self._ttl_seconds

    def age_seconds(self, state: dict) -> float:
        """Return seconds since the state was saved, or infinity if missing."""
        ts = state.get("timestamp", "")
        if not ts:
            return float("inf")
        return time.time() - self._timestamp_to_epoch(ts)

    # ── Core operations ───────────────────────────────────────────────────────

    def _acquire_lock(self) -> int:
        """Acquire an exclusive lock on the state file. Returns lock file descriptor."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
        try:
            # blocking exclusive lock
            fcntl.flock(fd, fcntl.LOCK_EX)
            return fd
        except OSError:
            os.close(fd)
            raise

    def _release_lock(self, fd: int) -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        except OSError:
            pass

    def _read_raw(self) -> Optional[dict]:
        if not self._path.exists():
            return None
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read checkpoint %s: %s", self._path, exc)
            return None

    def _write_raw(self, state: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def save(self, state: dict, *, version: int | None = None) -> None:
        """Atomically save state to the checkpoint file.

        Always writes a "version" and "timestamp" field.
        """
        merged: dict[str, Any] = {
            "version": version if version is not None else self.CURRENT_VERSION,
            "timestamp": self.now_iso(),
            **state,
        }
        fd = self._acquire_lock()
        try:
            self._write_raw(merged)
        finally:
            self._release_lock(fd)
        logger.debug("Checkpoint saved: %s", self._path)

    def load(self) -> Optional[dict]:
        """Load and return the checkpoint state, or None if missing / corrupt."""
        fd = self._acquire_lock()
        try:
            state = self._read_raw()
            if state and self.is_stale(state):
                logger.debug("Checkpoint %s is stale (age=%.1fh > %.1fh)",
                             self._path, self.age_seconds(state) / 3600, self.ttl_hours)
                return None
            return state
        finally:
            self._release_lock(fd)

    def clear(self) -> None:
        """Remove the checkpoint file if it exists."""
        fd = self._acquire_lock()
        try:
            self._path.unlink(missing_ok=True)
            logger.debug("Checkpoint cleared: %s", self._path)
        finally:
            self._release_lock(fd)

    def exists(self) -> bool:
        """Return True if a non-stale checkpoint exists."""
        state = self._read_raw()
        if state is None:
            return False
        return not self.is_stale(state)

    # ── High-level helpers ────────────────────────────────────────────────────

    def save_phase(self, phase: str, **extra: Any) -> None:
        """Convenience: save with a 'phase' field (used by research-refine)."""
        self.save({"phase": phase, **extra})

    def save_review(
        self,
        round_num: int,
        thread_id: str,
        status: str,
        **extra: Any,
    ) -> None:
        """Convenience: save review loop state (used by auto-review-loop)."""
        self.save({
            "round": round_num,
            "threadId": thread_id,
            "status": status,
            **extra,
        })

    def load_or_init(
        self,
        defaults: dict,
        *,
        version: int | None = None,
    ) -> dict:
        """Load existing checkpoint or initialise with defaults.

        If a valid checkpoint exists, returns it (not the defaults).
        If missing or stale, saves defaults and returns them.
        """
        state = self.load()
        if state:
            return state
        self.save(defaults, version=version)
        return defaults


# ── Pre-built checkpoint instances for SurveyMind skills ───────────────────────

def review_checkpoint(
    project_root: Path | None = None,
    ttl_hours: float = 24.0,
) -> Checkpoint:
    return Checkpoint("REVIEW_STATE.json", project_root=project_root, ttl_hours=ttl_hours)


def refine_checkpoint(
    project_root: Path | None = None,
    ttl_hours: float = 24.0,
) -> Checkpoint:
    return Checkpoint("REFINE_STATE.json", project_root=project_root, ttl_hours=ttl_hours)


def survey_trace_checkpoint(
    project_root: Path | None = None,
    ttl_hours: float = 168.0,   # 1 week — survey traces are long-lived
) -> Checkpoint:
    return Checkpoint("survey_trace/.checkpoint.json",
                       project_root=project_root, ttl_hours=ttl_hours)
