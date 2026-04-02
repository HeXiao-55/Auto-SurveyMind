"""Tests for tools/logging_config.py."""

import logging

from tools.logging_config import get_logger, setup_logging


class TestSetupLogging:
    def test_returns_named_logger(self):
        logger = setup_logging("test_module")
        assert logger.name == "test_module"
        assert logger.level == logging.INFO

    def test_level_from_env_var(self, monkeypatch):
        monkeypatch.setenv("SURVEYMIND_LOG_LEVEL", "DEBUG")
        logger = setup_logging("test_env")
        assert logger.level == logging.DEBUG

    def test_explicit_level_overrides_env(self, monkeypatch):
        monkeypatch.setenv("SURVEYMIND_LOG_LEVEL", "WARNING")
        logger = setup_logging("test_explicit", level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_file_handler_added(self, tmp_path):
        log_file = tmp_path / "test.log"
        logger = setup_logging("test_file", log_file=log_file)
        assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)

    def test_idempotent_no_duplicate_handlers(self):
        logger = setup_logging("test_idempotent")
        logger.setLevel(logging.INFO)

        def count_handlers() -> int:
            return sum(1 for h in logger.handlers if not isinstance(h, logging.NullHandler))

        before = count_handlers()
        setup_logging("test_idempotent")  # second call
        after = count_handlers()
        assert before == after  # no new handlers added


class TestGetLogger:
    def test_returns_logger_without_adding_handlers(self):
        logger1 = get_logger("test_get")
        logger2 = get_logger("test_get")
        assert logger1 is logger2  # same instance
