"""Tests for PID files, stop sentinel, process lifecycle, and signal handling."""

import os
import signal

from unittest.mock import MagicMock, patch

import stream


# ── PID File ────────────────────────────────────────────────────────────────


class TestWritePidFile:
    def test_write_pid_file(self, stream, tmp_script_dir, sample_config):
        """write_pid_file writes the current PID to disk."""
        stream.write_pid_file(sample_config)
        pid_path = tmp_script_dir / sample_config["pidFile"]
        assert pid_path.read_text().strip() == str(os.getpid())


class TestReadPidFile:
    def test_read_pid_file_exists(self, stream, tmp_script_dir, sample_config):
        """read_pid_file returns the integer PID from an existing file."""
        pid_path = tmp_script_dir / sample_config["pidFile"]
        pid_path.write_text("12345")
        assert stream.read_pid_file(sample_config) == 12345

    def test_read_pid_file_missing(self, stream, tmp_script_dir, sample_config):
        """read_pid_file returns None when the file does not exist."""
        assert stream.read_pid_file(sample_config) is None

    def test_read_pid_file_invalid(self, stream, tmp_script_dir, sample_config):
        """read_pid_file returns None when the file contains non-numeric text."""
        pid_path = tmp_script_dir / sample_config["pidFile"]
        pid_path.write_text("abc")
        assert stream.read_pid_file(sample_config) is None


class TestCleanupPidFile:
    def test_cleanup_pid_file(self, stream, tmp_script_dir, sample_config):
        """cleanup_pid_file removes an existing PID file."""
        pid_path = tmp_script_dir / sample_config["pidFile"]
        pid_path.write_text("12345")
        stream.cleanup_pid_file(sample_config)
        assert not pid_path.exists()

    def test_cleanup_pid_file_missing(self, stream, tmp_script_dir, sample_config):
        """cleanup_pid_file does not raise when the file is absent."""
        stream.cleanup_pid_file(sample_config)  # should not raise


# ── Stop Sentinel ───────────────────────────────────────────────────────────


class TestWriteStopSentinel:
    def test_write_stop_sentinel(self, stream, tmp_script_dir, sample_config):
        """write_stop_sentinel creates the sentinel file."""
        stream.write_stop_sentinel(sample_config)
        sentinel_path = tmp_script_dir / sample_config["stopSentinel"]
        assert sentinel_path.exists()


class TestStopSentinelExists:
    def test_stop_sentinel_exists_true(self, stream, tmp_script_dir, sample_config):
        """stop_sentinel_exists returns True when the file is present."""
        sentinel_path = tmp_script_dir / sample_config["stopSentinel"]
        sentinel_path.touch()
        assert stream.stop_sentinel_exists(sample_config) is True

    def test_stop_sentinel_exists_false(self, stream, tmp_script_dir, sample_config):
        """stop_sentinel_exists returns False when the file is absent."""
        assert stream.stop_sentinel_exists(sample_config) is False


class TestCleanupStopSentinel:
    def test_cleanup_stop_sentinel(self, stream, tmp_script_dir, sample_config):
        """cleanup_stop_sentinel removes an existing sentinel file."""
        sentinel_path = tmp_script_dir / sample_config["stopSentinel"]
        sentinel_path.touch()
        stream.cleanup_stop_sentinel(sample_config)
        assert not sentinel_path.exists()

    def test_cleanup_stop_sentinel_missing(self, stream, tmp_script_dir, sample_config):
        """cleanup_stop_sentinel does not raise when the file is absent."""
        stream.cleanup_stop_sentinel(sample_config)  # should not raise


# ── is_stop_requested ───────────────────────────────────────────────────────


class TestIsStopRequested:
    def test_is_stop_requested_sentinel(self, stream, tmp_script_dir, sample_config):
        """Returns True when the sentinel file exists (flag is False)."""
        stream._stop_requested = False
        sentinel_path = tmp_script_dir / sample_config["stopSentinel"]
        sentinel_path.touch()
        assert stream.is_stop_requested(sample_config) is True

    def test_is_stop_requested_flag(self, stream, tmp_script_dir, sample_config):
        """Returns True when _stop_requested flag is set (no sentinel)."""
        stream._stop_requested = True
        assert stream.is_stop_requested(sample_config) is True

    def test_is_stop_requested_neither(self, stream, tmp_script_dir, sample_config):
        """Returns False when neither flag nor sentinel are set."""
        stream._stop_requested = False
        assert stream.is_stop_requested(sample_config) is False


# ── Process Lifecycle ───────────────────────────────────────────────────────


class TestIsProcessRunning:
    def test_is_process_running_self(self, stream):
        """The current process PID is reported as running."""
        assert stream._is_process_running(os.getpid()) is True

    def test_is_process_running_nonexistent(self, stream):
        """A very high PID that does not exist is reported as not running."""
        assert stream._is_process_running(999999999) is False


class TestKillExistingProcess:
    def test_kill_existing_no_pid(self, stream, tmp_script_dir, sample_config, mock_logger):
        """When no PID file exists, the function returns without killing."""
        stream.kill_existing_process(sample_config, mock_logger)
        mock_logger.info.assert_not_called()

    def test_kill_existing_stale_pid(self, stream, tmp_script_dir, sample_config, mock_logger):
        """A stale PID file (dead process) is cleaned up with a log message."""
        pid_path = tmp_script_dir / sample_config["pidFile"]
        pid_path.write_text("999999999")

        stream.kill_existing_process(sample_config, mock_logger)

        assert not pid_path.exists()
        logged_messages = " ".join(call[0][0] for call in mock_logger.info.call_args_list)
        assert "stale" in logged_messages.lower()

    @patch("stream.time.sleep")
    @patch("stream.os.kill")
    @patch("stream._is_process_running")
    def test_kill_existing_running(
        self, mock_running, mock_kill, mock_sleep,
        stream, tmp_script_dir, sample_config, mock_logger,
    ):
        """A running process receives SIGTERM and the PID file is cleaned up."""
        pid_path = tmp_script_dir / sample_config["pidFile"]
        pid_path.write_text("42")

        # First call: process is running; subsequent calls: process has exited
        mock_running.side_effect = [True, False]

        stream.kill_existing_process(sample_config, mock_logger)

        mock_kill.assert_any_call(42, signal.SIGTERM)


# ── Signal Handling ─────────────────────────────────────────────────────────


class TestSignalHandler:
    def test_signal_handler_sets_flag(self, stream):
        """Calling _signal_handler sets _stop_requested to True."""
        stream._stop_requested = False
        stream._signal_handler(signal.SIGTERM, None)
        assert stream._stop_requested is True

    def test_signal_handler_writes_sentinel(
        self, stream, tmp_script_dir, sample_config
    ):
        """Calling _signal_handler creates the stop sentinel file."""
        stream._config = sample_config
        stream._signal_handler(signal.SIGTERM, None)
        sentinel_path = tmp_script_dir / sample_config["stopSentinel"]
        assert sentinel_path.exists()

    def test_signal_handler_terminates_ffmpeg(self, stream):
        """If ffmpeg is running, _signal_handler calls terminate()."""
        mock_proc = MagicMock(poll=MagicMock(return_value=None))
        stream._ffmpeg_process = mock_proc
        stream._signal_handler(signal.SIGTERM, None)
        mock_proc.terminate.assert_called_once()

    def test_signal_handler_no_ffmpeg(self, stream):
        """If _ffmpeg_process is None, _signal_handler does not raise."""
        stream._ffmpeg_process = None
        stream._signal_handler(signal.SIGTERM, None)  # should not raise


class TestRegisterSignalHandlers:
    @patch("stream.signal.signal")
    def test_register_signal_handlers(self, mock_signal, stream):
        """register_signal_handlers registers handlers for SIGINT and SIGTERM."""
        stream.register_signal_handlers()

        registered_signals = [call[0][0] for call in mock_signal.call_args_list]
        assert signal.SIGINT in registered_signals
        assert signal.SIGTERM in registered_signals
