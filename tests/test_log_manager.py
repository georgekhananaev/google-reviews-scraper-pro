"""Tests for structured logging setup (log_manager.py)."""

import json
import logging
from pathlib import Path

import pytest

from modules.log_manager import setup_logging


@pytest.fixture(autouse=True)
def _reset_root_logger():
    """Reset root logger between tests to avoid handler leaks."""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.level = original_level


class TestSetupLogging:
    def test_creates_log_dir(self, tmp_path):
        log_dir = tmp_path / "testlogs"
        setup_logging(log_dir=str(log_dir), log_file="test.log")
        assert log_dir.exists()

    def test_creates_log_file(self, tmp_path):
        log_dir = tmp_path / "testlogs"
        setup_logging(log_dir=str(log_dir), log_file="test.log")
        # Emit a record so the file handler writes
        logging.getLogger("test").info("hello")
        assert (log_dir / "test.log").exists()

    def test_json_format(self, tmp_path):
        log_dir = tmp_path / "testlogs"
        setup_logging(log_dir=str(log_dir), log_file="test.log")
        logging.getLogger("test.json").warning("structured message")
        # Flush handlers
        for h in logging.getLogger().handlers:
            h.flush()
        content = (log_dir / "test.log").read_text(encoding="utf-8").strip()
        lines = content.splitlines()
        assert len(lines) >= 1
        entry = json.loads(lines[-1])
        assert entry["level"] == "WARNING"
        assert entry["msg"] == "structured message"
        assert entry["logger"] == "test.json"

    def test_level_filtering(self, tmp_path):
        log_dir = tmp_path / "testlogs"
        setup_logging(level="WARNING", log_dir=str(log_dir), log_file="test.log")
        logger = logging.getLogger("test.level")
        logger.info("should not appear")
        logger.warning("should appear")
        for h in logging.getLogger().handlers:
            h.flush()
        content = (log_dir / "test.log").read_text(encoding="utf-8").strip()
        lines = [l for l in content.splitlines() if l.strip()]
        assert len(lines) == 1
        assert "should appear" in lines[0]

    def test_noisy_loggers_suppressed(self, tmp_path):
        log_dir = tmp_path / "testlogs"
        setup_logging(log_dir=str(log_dir), log_file="test.log")
        # These should be suppressed at WARNING level
        for name in ("selenium", "urllib3", "botocore"):
            assert logging.getLogger(name).level >= logging.WARNING

    def test_two_handlers_attached(self, tmp_path):
        setup_logging(log_dir=str(tmp_path), log_file="test.log")
        root = logging.getLogger()
        # Should have exactly 2 handlers: RichHandler + RotatingFileHandler
        assert len(root.handlers) == 2

    def test_reinit_clears_old_handlers(self, tmp_path):
        setup_logging(log_dir=str(tmp_path), log_file="test.log")
        setup_logging(log_dir=str(tmp_path), log_file="test.log")
        root = logging.getLogger()
        assert len(root.handlers) == 2
