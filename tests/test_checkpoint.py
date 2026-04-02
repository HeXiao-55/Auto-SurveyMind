"""Tests for tools/checkpoint.py."""

import json

from tools.checkpoint import (
    Checkpoint,
    refine_checkpoint,
    review_checkpoint,
    survey_trace_checkpoint,
)


class TestCheckpointBasic:
    def test_save_and_load(self, tmp_path):
        ck = Checkpoint("state.json", project_root=tmp_path)
        ck.save({"phase": "review", "round": 2, "status": "in_progress"})
        loaded = ck.load()
        assert loaded is not None
        assert loaded["phase"] == "review"
        assert loaded["round"] == 2
        assert loaded["status"] == "in_progress"
        assert "version" in loaded
        assert "timestamp" in loaded

    def test_load_missing_returns_none(self, tmp_path):
        ck = Checkpoint("does_not_exist.json", project_root=tmp_path)
        assert ck.load() is None

    def test_clear_removes_file(self, tmp_path):
        ck = Checkpoint("state.json", project_root=tmp_path)
        ck.save({"round": 1})
        assert ck.exists()
        ck.clear()
        assert not ck.exists()

    def test_save_phase_helper(self, tmp_path):
        ck = Checkpoint("refine.json", project_root=tmp_path)
        ck.save_phase("proposal", round=3)
        loaded = ck.load()
        assert loaded["phase"] == "proposal"
        assert loaded["round"] == 3

    def test_save_review_helper(self, tmp_path):
        ck = Checkpoint("review.json", project_root=tmp_path)
        ck.save_review(round_num=4, thread_id="thread_xyz", status="completed")
        loaded = ck.load()
        assert loaded["round"] == 4
        assert loaded["threadId"] == "thread_xyz"
        assert loaded["status"] == "completed"


class TestCheckpointStaleness:
    def test_fresh_checkpoint_not_stale(self, tmp_path):
        ck = Checkpoint("state.json", project_root=tmp_path, ttl_hours=24)
        ck.save({"status": "in_progress"})
        assert ck.is_stale(ck.load()) is False

    def test_checkpoint_past_ttl_is_stale(self, tmp_path):
        ck = Checkpoint("state.json", project_root=tmp_path, ttl_hours=0.001)  # ~36ms
        ck.save({"status": "in_progress", "timestamp": "2020-01-01T00:00:00+00:00"})
        # Force a state dict with old timestamp
        old_path = tmp_path / "state.json"
        old_path.write_text(json.dumps({
            "version": 1,
            "status": "in_progress",
            "timestamp": "2020-01-01T00:00:00+00:00",
        }))
        state = ck.load()
        assert state is None  # Stale state should return None from load

    def test_load_or_init_returns_existing_when_valid(self, tmp_path):
        ck = Checkpoint("state.json", project_root=tmp_path)
        ck.save({"round": 5, "status": "completed"})
        result = ck.load_or_init({"round": 1, "status": "in_progress"})
        assert result["round"] == 5  # existing value, not default

    def test_load_or_init_returns_defaults_when_missing(self, tmp_path):
        ck = Checkpoint("new_state.json", project_root=tmp_path)
        result = ck.load_or_init({"round": 1, "status": "in_progress"})
        assert result["round"] == 1
        assert ck.exists()


class TestCheckpointPathResolution:
    def test_relative_path_resolved_from_root(self, tmp_path):
        ck = Checkpoint("subdir/state.json", project_root=tmp_path)
        assert ck.path.parent.name == "subdir"

    def test_absolute_path_not_modified(self):
        ck = Checkpoint("/tmp/absolute_state.json")
        assert str(ck.path).startswith("/tmp")


class TestPrebuiltCheckpoints:
    def test_review_checkpoint_defaults(self):
        ck = review_checkpoint()
        assert "REVIEW_STATE.json" in str(ck.path)
        assert ck.ttl_hours == 24.0

    def test_refine_checkpoint_defaults(self):
        ck = refine_checkpoint()
        assert "REFINE_STATE.json" in str(ck.path)
        assert ck.ttl_hours == 24.0

    def test_survey_trace_checkpoint_long_ttl(self):
        ck = survey_trace_checkpoint()
        assert ck.ttl_hours == 168.0  # 1 week
