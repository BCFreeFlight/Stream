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

    def test_logger_debug_writes_debug_level(self, tmp_path):
        """debug('msg') writes a line containing [DEBUG] when level=DEBUG."""
        log_dir = tmp_path / "logs"
        logger = stream.Logger(str(log_dir), retention_days=15, level=stream.LOG_LEVELS["debug"])
        logger.debug("verbose detail")
        logger.close()

        log_file = log_dir / f"{datetime.date.today().isoformat()}.log"
        content = log_file.read_text()
        assert "[DEBUG]" in content
        assert "verbose detail" in content


class TestLoggerLevelFiltering:
    def _make_logger(self, tmp_path, level_name):
        log_dir = tmp_path / "logs"
        return stream.Logger(str(log_dir), retention_days=15, level=stream.LOG_LEVELS[level_name])

    def _log_contents(self, log_dir):
        log_file = log_dir / f"{datetime.date.today().isoformat()}.log"
        return log_file.read_text()

    def test_debug_suppressed_at_info_level(self, tmp_path):
        """debug() messages are not written when level=info."""
        logger = self._make_logger(tmp_path, "info")
        logger.debug("should not appear")
        logger.close()
        assert "should not appear" not in self._log_contents(tmp_path / "logs")

    def test_info_suppressed_at_warning_level(self, tmp_path):
        """info() messages are not written when level=warning."""
        logger = self._make_logger(tmp_path, "warning")
        logger.info("should not appear")
        logger.close()
        assert "should not appear" not in self._log_contents(tmp_path / "logs")

    def test_warn_suppressed_at_error_level(self, tmp_path):
        """warn() messages are not written when level=error."""
        logger = self._make_logger(tmp_path, "error")
        logger.warn("should not appear")
        logger.close()
        assert "should not appear" not in self._log_contents(tmp_path / "logs")

    def test_info_written_at_info_level(self, tmp_path):
        """info() messages are written when level=info."""
        logger = self._make_logger(tmp_path, "info")
        logger.info("should appear")
        logger.close()
        assert "should appear" in self._log_contents(tmp_path / "logs")

    def test_warn_written_at_info_level(self, tmp_path):
        """warn() messages pass the filter when level=info."""
        logger = self._make_logger(tmp_path, "info")
        logger.warn("warning passes")
        logger.close()
        assert "warning passes" in self._log_contents(tmp_path / "logs")

    def test_error_written_at_warning_level(self, tmp_path):
        """error() messages pass the filter when level=warning."""
        logger = self._make_logger(tmp_path, "warning")
        logger.error("error passes")
        logger.close()
        assert "error passes" in self._log_contents(tmp_path / "logs")

    def test_debug_written_at_debug_level(self, tmp_path):
        """debug() messages are written when level=debug."""
        logger = self._make_logger(tmp_path, "debug")
        logger.debug("debug passes")
        logger.close()
        assert "debug passes" in self._log_contents(tmp_path / "logs")


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

    def test_create_logger_uses_config_level(self, tmp_script_dir, sample_config):
        """create_logger reads logLevel from config."""
        sample_config["logLevel"] = "warning"
        logger = stream.create_logger(sample_config)
        assert logger._level == stream.LOG_LEVELS["warning"]
        logger.close()

    def test_create_logger_level_override_wins(self, tmp_script_dir, sample_config):
        """A level_override argument takes precedence over config logLevel."""
        sample_config["logLevel"] = "info"
        debug_level = stream.LOG_LEVELS["debug"]
        logger = stream.create_logger(sample_config, level_override=debug_level)
        assert logger._level == debug_level
        logger.close()

    def test_create_logger_defaults_to_info(self, tmp_script_dir, sample_config):
        """When logLevel is absent from config, level defaults to info."""
        del sample_config["logLevel"]
        logger = stream.create_logger(sample_config)
        assert logger._level == stream.LOG_LEVELS["info"]
        logger.close()

    def test_create_logger_invalid_config_level_falls_back_to_info(
        self, tmp_script_dir, sample_config
    ):
        """An unrecognised logLevel string falls back to info."""
        sample_config["logLevel"] = "verbose"
        logger = stream.create_logger(sample_config)
        assert logger._level == stream.LOG_LEVELS["info"]
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

    def test_print_logger_debug_shown_at_debug_level(self, capsys):
        """PrintLogger.debug() writes [DEBUG] when level=debug."""
        pl = stream.PrintLogger(level=stream.LOG_LEVELS["debug"])
        pl.debug("verbose")
        captured = capsys.readouterr()
        assert "[DEBUG]" in captured.out

    def test_print_logger_debug_suppressed_at_info_level(self, capsys):
        """PrintLogger.debug() produces no output when level=info."""
        pl = stream.PrintLogger(level=stream.LOG_LEVELS["info"])
        pl.debug("verbose")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_print_logger_info_suppressed_at_warning_level(self, capsys):
        """PrintLogger.info() produces no output when level=warning."""
        pl = stream.PrintLogger(level=stream.LOG_LEVELS["warning"])
        pl.info("should be silent")
        captured = capsys.readouterr()
        assert captured.out == ""


# ── LOG_LEVELS constant ──────────────────────────────────────────────────────


class TestLogLevels:
    def test_log_levels_ordering(self):
        """debug < info < warning < error."""
        lvl = stream.LOG_LEVELS
        assert lvl["debug"] < lvl["info"] < lvl["warning"] < lvl["error"]

    def test_log_levels_keys(self):
        """LOG_LEVELS contains exactly the four expected keys."""
        assert set(stream.LOG_LEVELS.keys()) == {"debug", "info", "warning", "error"}


# ── --log-level CLI argument ─────────────────────────────────────────────────


class TestLogLevelCli:
    def _parse(self, argv):
        """Parse argv through stream.main() argument parser via sys.argv mock."""
        import sys
        from unittest.mock import patch

        # We test argument parsing by calling main() with patched sys.argv and
        # patching the dispatched command so we don't actually run the stream.
        with patch.object(sys, "argv", ["stream.py"] + argv):
            with patch.object(stream, "do_start") as mock_start:
                stream.main()
                return mock_start

    def test_log_level_debug_accepted(self):
        """--log-level debug passes level 0 to do_start."""
        mock_start = self._parse(["--start", "--log-level", "debug"])
        mock_start.assert_called_once_with(stream.LOG_LEVELS["debug"])

    def test_log_level_info_accepted(self):
        """--log-level info passes level 1 to do_start."""
        mock_start = self._parse(["--start", "--log-level", "info"])
        mock_start.assert_called_once_with(stream.LOG_LEVELS["info"])

    def test_log_level_case_insensitive(self):
        """--log-level DEBUG (uppercase) is accepted."""
        mock_start = self._parse(["--start", "--log-level", "DEBUG"])
        mock_start.assert_called_once_with(stream.LOG_LEVELS["debug"])

    def test_log_level_warning_accepted(self):
        """--log-level warning is accepted."""
        mock_start = self._parse(["--start", "--log-level", "warning"])
        mock_start.assert_called_once_with(stream.LOG_LEVELS["warning"])

    def test_log_level_error_accepted(self):
        """--log-level error is accepted."""
        mock_start = self._parse(["--start", "--log-level", "error"])
        mock_start.assert_called_once_with(stream.LOG_LEVELS["error"])

    def test_log_level_none_passes_none(self):
        """Omitting --log-level passes None to do_start."""
        mock_start = self._parse(["--start"])
        mock_start.assert_called_once_with(None)

    def test_invalid_log_level_exits(self):
        """An invalid --log-level value exits with a non-zero code."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, "argv", ["stream.py", "--start", "--log-level", "verbose"]):
            try:
                stream.main()
                assert False, "Expected SystemExit"
            except SystemExit as exc:
                assert exc.code != 0
