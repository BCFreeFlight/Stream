"""Tests for Logger, PrintLogger, _parse_log_date, and create_logger."""

import datetime
import re
from pathlib import Path

import stream


# ── Logger (constructed directly with tmp_path) ─────────────────────────────


class TestLoggerInit:
    def test_logger_creates_log_directory(self, tmp_path):
        """Logger.__init__ creates the log_dir when it does not exist."""
        log_dir = tmp_path / "new_logs"
        assert not log_dir.exists()
        stream.Logger(str(log_dir), retention_days=15)
        assert log_dir.is_dir()

    def test_logger_creates_daily_log_file(self, tmp_path):
        """After init, a file named YYYY-MM-DD.log exists in log_dir."""
        log_dir = tmp_path / "logs"
        stream.Logger(str(log_dir), retention_days=15)
        expected = log_dir / f"{datetime.date.today().isoformat()}.log"
        assert expected.exists()


class TestLoggerWrite:
    def test_logger_info_writes_correct_format(self, tmp_path):
        """info('msg') writes a line matching [timestamp] [INFO] msg."""
        log_dir = tmp_path / "logs"
        logger = stream.Logger(str(log_dir), retention_days=15)
        logger.info("hello world")
        logger.close()

        log_file = log_dir / f"{datetime.date.today().isoformat()}.log"
        content = log_file.read_text()
        assert re.search(r"\[.+\] \[INFO\] hello world", content)

    def test_logger_warn_writes_warn_level(self, tmp_path):
        """warn('msg') writes a line containing [WARN]."""
        log_dir = tmp_path / "logs"
        logger = stream.Logger(str(log_dir), retention_days=15)
        logger.warn("a warning")
        logger.close()

        log_file = log_dir / f"{datetime.date.today().isoformat()}.log"
        content = log_file.read_text()
        assert "[WARN]" in content

    def test_logger_error_writes_error_level(self, tmp_path):
        """error('msg') writes a line containing [ERROR]."""
        log_dir = tmp_path / "logs"
        logger = stream.Logger(str(log_dir), retention_days=15)
        logger.error("an error")
        logger.close()

        log_file = log_dir / f"{datetime.date.today().isoformat()}.log"
        content = log_file.read_text()
        assert "[ERROR]" in content

    def test_logger_mirrors_to_stdout(self, capsys, tmp_path):
        """info() output also appears on stdout."""
        log_dir = tmp_path / "logs"
        logger = stream.Logger(str(log_dir), retention_days=15)
        logger.info("test stdout")
        logger.close()

        captured = capsys.readouterr()
        assert "test stdout" in captured.out


class TestLoggerCleanup:
    def test_logger_cleanup_deletes_old_logs(self, tmp_path):
        """cleanup_old_logs removes files with dates older than retention_days."""
        log_dir = tmp_path / "logs"
        logger = stream.Logger(str(log_dir), retention_days=15)

        old_file = log_dir / "2020-01-01.log"
        old_file.write_text("old data")

        logger.cleanup_old_logs()
        assert not old_file.exists()
        logger.close()

    def test_logger_cleanup_keeps_recent_logs(self, tmp_path):
        """cleanup_old_logs does not delete today's log file."""
        log_dir = tmp_path / "logs"
        logger = stream.Logger(str(log_dir), retention_days=15)

        today_file = log_dir / f"{datetime.date.today().isoformat()}.log"
        assert today_file.exists()

        logger.cleanup_old_logs()
        assert today_file.exists()
        logger.close()

    def test_logger_cleanup_ignores_non_date_files(self, tmp_path):
        """cleanup_old_logs does not delete files without date-based names."""
        log_dir = tmp_path / "logs"
        logger = stream.Logger(str(log_dir), retention_days=15)

        notes_file = log_dir / "notes.log"
        notes_file.write_text("keep me")

        logger.cleanup_old_logs()
        assert notes_file.exists()
        logger.close()


class TestLoggerClose:
    def test_logger_close(self, tmp_path):
        """Calling close() does not raise an error."""
        log_dir = tmp_path / "logs"
        logger = stream.Logger(str(log_dir), retention_days=15)
        logger.close()


# ── _parse_log_date ─────────────────────────────────────────────────────────


class TestParseLogDate:
    def test_parse_log_date_valid(self):
        """A valid date stem returns the corresponding date object."""
        result = stream._parse_log_date(Path("2026-04-12.log"))
        assert result == datetime.date(2026, 4, 12)

    def test_parse_log_date_invalid(self):
        """A non-date stem returns None."""
        result = stream._parse_log_date(Path("notes.log"))
        assert result is None

    def test_parse_log_date_bad_date(self):
        """An impossible date returns None."""
        result = stream._parse_log_date(Path("2026-13-45.log"))
        assert result is None


# ── create_logger ───────────────────────────────────────────────────────────


class TestCreateLogger:
    def test_create_logger_returns_instance(self, tmp_script_dir, sample_config):
        """create_logger returns a Logger backed by the configured logDir."""
        logger = stream.create_logger(sample_config)
        assert isinstance(logger, stream.Logger)
        logger.close()


# ── PrintLogger ─────────────────────────────────────────────────────────────


class TestPrintLogger:
    def test_print_logger_info(self, capsys):
        """PrintLogger.info() writes [INFO] to stdout."""
        pl = stream.PrintLogger()
        pl.info("msg")
        captured = capsys.readouterr()
        assert "[INFO]" in captured.out

    def test_print_logger_warn(self, capsys):
        """PrintLogger.warn() writes [WARN] to stdout."""
        pl = stream.PrintLogger()
        pl.warn("msg")
        captured = capsys.readouterr()
        assert "[WARN]" in captured.out

    def test_print_logger_error(self, capsys):
        """PrintLogger.error() writes [ERROR] to stdout."""
        pl = stream.PrintLogger()
        pl.error("msg")
        captured = capsys.readouterr()
        assert "[ERROR]" in captured.out
