"""Tests for is_in_stream_window, do_recover orchestration, and --recover dispatch."""

import datetime

import pytest
from unittest.mock import patch

import stream


# ── is_in_stream_window ─────────────────────────────────────────────────────


class TestIsInStreamWindow:
    @pytest.fixture
    def window_config(self, sample_config):
        """Config with a 6:30am start / 6:25pm stop daily window."""
        sample_config["cron"]["start"] = "30 6 * * *"
        sample_config["cron"]["stop"] = "25 18 * * *"
        return sample_config

    @pytest.fixture
    def seasonal_config(self, sample_config):
        """Config with the production default: 6:30am–6:25pm, April–October."""
        sample_config["cron"]["start"] = "30 6 1-31 4-10 *"
        sample_config["cron"]["stop"] = "25 18 1-31 4-10 *"
        return sample_config

    def test_in_window_midday(self, window_config):
        """A time well between start and stop returns True."""
        now = datetime.datetime(2026, 5, 12, 12, 0, 0)
        assert stream.is_in_stream_window(window_config, now) is True

    def test_before_start(self, window_config):
        """A time before today's start returns False."""
        now = datetime.datetime(2026, 5, 12, 5, 0, 0)
        assert stream.is_in_stream_window(window_config, now) is False

    def test_after_stop(self, window_config):
        """A time after today's stop returns False."""
        now = datetime.datetime(2026, 5, 12, 20, 0, 0)
        assert stream.is_in_stream_window(window_config, now) is False

    def test_exactly_at_start(self, window_config):
        """At the start minute itself we are inside the window."""
        now = datetime.datetime(2026, 5, 12, 6, 30, 0)
        assert stream.is_in_stream_window(window_config, now) is True

    def test_exactly_at_stop(self, window_config):
        """At the stop minute the window has closed (last_stop == now, not before)."""
        now = datetime.datetime(2026, 5, 12, 18, 25, 0)
        assert stream.is_in_stream_window(window_config, now) is False

    def test_out_of_season(self, seasonal_config):
        """A time outside the April–October months returns False."""
        now = datetime.datetime(2026, 1, 15, 12, 0, 0)
        assert stream.is_in_stream_window(seasonal_config, now) is False

    def test_in_season_first_day(self, seasonal_config):
        """First day of the season, mid-window, returns True."""
        now = datetime.datetime(2026, 4, 1, 10, 0, 0)
        assert stream.is_in_stream_window(seasonal_config, now) is True

    def test_in_season_last_day(self, seasonal_config):
        """Last day of the season, mid-window, returns True."""
        now = datetime.datetime(2026, 10, 31, 10, 0, 0)
        assert stream.is_in_stream_window(seasonal_config, now) is True

    def test_default_now_uses_current_time(self, window_config):
        """When now is not provided, the function still returns a bool without error."""
        result = stream.is_in_stream_window(window_config)
        assert isinstance(result, bool)


# ── _stream_process_already_running ─────────────────────────────────────────


class TestStreamProcessAlreadyRunning:
    def test_no_pid_file(self, sample_config):
        """Returns False when there is no PID file."""
        with patch("stream.read_pid_file", return_value=None):
            assert stream._stream_process_already_running(sample_config) is False

    def test_pid_alive(self, sample_config):
        """Returns True when the PID file points to a live process."""
        with patch("stream.read_pid_file", return_value=4321), \
             patch("stream._is_process_running", return_value=True):
            assert stream._stream_process_already_running(sample_config) is True

    def test_pid_stale(self, sample_config):
        """Returns False when the PID file points to a dead process."""
        with patch("stream.read_pid_file", return_value=4321), \
             patch("stream._is_process_running", return_value=False):
            assert stream._stream_process_already_running(sample_config) is False


# ── do_recover ──────────────────────────────────────────────────────────────


class TestDoRecover:
    def test_recover_in_window_calls_do_start(
        self, sample_config, config_on_disk, env_on_disk, mock_logger
    ):
        """When in the daily window and no process is running, do_start is invoked."""
        with patch("stream.create_logger", return_value=mock_logger), \
             patch("stream._stream_process_already_running", return_value=False), \
             patch("stream.is_in_stream_window", return_value=True), \
             patch("stream.do_start") as mock_start:
            stream.do_recover()

        mock_start.assert_called_once()

    def test_recover_outside_window_does_nothing(
        self, sample_config, config_on_disk, env_on_disk, mock_logger
    ):
        """When outside the window, do_start is NOT invoked."""
        with patch("stream.create_logger", return_value=mock_logger), \
             patch("stream._stream_process_already_running", return_value=False), \
             patch("stream.is_in_stream_window", return_value=False), \
             patch("stream.do_start") as mock_start:
            stream.do_recover()

        mock_start.assert_not_called()
        mock_logger.close.assert_called_once()

    def test_recover_skips_when_already_running(
        self, sample_config, config_on_disk, env_on_disk, mock_logger
    ):
        """When a stream process is already alive, do_start is not invoked."""
        with patch("stream.create_logger", return_value=mock_logger), \
             patch("stream._stream_process_already_running", return_value=True), \
             patch("stream.is_in_stream_window", return_value=True), \
             patch("stream.do_start") as mock_start:
            stream.do_recover()

        mock_start.assert_not_called()
        mock_logger.close.assert_called_once()

    def test_recover_logs_version_banner(
        self, sample_config, config_on_disk, env_on_disk, mock_logger
    ):
        """do_recover logs an identifying banner mentioning 'recover'."""
        with patch("stream.create_logger", return_value=mock_logger), \
             patch("stream._stream_process_already_running", return_value=False), \
             patch("stream.is_in_stream_window", return_value=False):
            stream.do_recover()

        banner_calls = [c for c in mock_logger.info.call_args_list if "recover" in c.args[0].lower()]
        assert banner_calls, "expected a log line mentioning 'recover'"
