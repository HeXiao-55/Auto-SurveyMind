"""Tests for tools/atomic_write.py."""

import json

from tools.atomic_write import (
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
)


class TestAtomicWriteText:
    def test_writes_content(self, tmp_path):
        path = tmp_path / "output.txt"
        atomic_write_text(path, "hello world")
        assert path.read_text() == "hello world"

    def test_overwrites_existing(self, tmp_path):
        path = tmp_path / "output.txt"
        path.write_text("old")
        atomic_write_text(path, "new")
        assert path.read_text() == "new"

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "output.txt"
        atomic_write_text(path, "content")
        assert path.read_text() == "content"

    def test_preserves_suffix(self, tmp_path):
        path = tmp_path / "data.json"
        atomic_write_text(path, '{"key": 1}')
        assert path.suffix == ".json"


class TestAtomicWriteBytes:
    def test_writes_bytes(self, tmp_path):
        path = tmp_path / "data.bin"
        atomic_write_bytes(path, b"\x00\x01\x02")
        assert path.read_bytes() == b"\x00\x01\x02"


class TestAtomicWriteJson:
    def test_writes_valid_json(self, tmp_path):
        path = tmp_path / "report.json"
        data = {"papers": [{"id": "2301.12345", "title": "Test"}]}
        atomic_write_json(path, data)
        assert json.loads(path.read_text()) == data

    def test_indent_parameter(self, tmp_path):
        path = tmp_path / "pretty.json"
        atomic_write_json(path, {"a": 1}, indent=4)
        text = path.read_text()
        assert "    " in text  # 4-space indent

    def test_compact_when_indent_none(self, tmp_path):
        path = tmp_path / "compact.json"
        atomic_write_json(path, {"a": 1}, indent=None)
        text = path.read_text()
        assert " " not in text  # compact, no spaces
