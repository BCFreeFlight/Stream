"""Tests for is_in_stream_window, do_recover orchestration, and --recover dispatch."""

import datetime
import socket

import pytest
import tomli_w
from unittest.mock import MagicMock, call, patch

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
             patch("stream.wait_for_network", return_value=True), \
             patch("stream.do_start") as mock_start:
            stream.do_recover()

        mock_start.assert_called_once()

    def test_recover_waits_for_network_before_start(
        self, sample_config, config_on_disk, env_on_disk, mock_logger
    ):
        """The network wait runs before do_start is invoked."""
        order = MagicMock()
        with patch("stream.create_logger", return_value=mock_logger), \
             patch("stream._stream_process_already_running", return_value=False), \
             patch("stream.is_in_stream_window", return_value=True), \
             patch("stream.wait_for_network") as mock_wait, \
             patch("stream.do_start") as mock_start:
            order.attach_mock(mock_wait, "wait")
            order.attach_mock(mock_start, "start")
            stream.do_recover()

        assert [c[0] for c in order.mock_calls] == ["wait", "start"]

    def test_recover_starts_even_if_network_wait_expires(
        self, sample_config, config_on_disk, env_on_disk, mock_logger
    ):
        """An expired network wait still delegates to do_start (the retry loop applies)."""
        with patch("stream.create_logger", return_value=mock_logger), \
             patch("stream._stream_process_already_running", return_value=False), \
             patch("stream.is_in_stream_window", return_value=True), \
             patch("stream.wait_for_network", return_value=False), \
             patch("stream.do_start") as mock_start:
            stream.do_recover()

        mock_start.assert_called_once()

    @pytest.mark.parametrize("in_window, running", [(False, False), (True, True)])
    def test_recover_skips_network_wait_when_not_starting(
        self, in_window, running, sample_config, config_on_disk, env_on_disk, mock_logger
    ):
        """No network wait when outside the window or a stream is already running."""
        with patch("stream.create_logger", return_value=mock_logger), \
             patch("stream._stream_process_already_running", return_value=running), \
             patch("stream.is_in_stream_window", return_value=in_window), \
             patch("stream.wait_for_network") as mock_wait, \
             patch("stream.do_start"):
            stream.do_recover()

        mock_wait.assert_not_called()

    def test_recover_migrates_config_missing_network_wait(
        self, sample_config, tmp_script_dir, env_on_disk, mock_logger
    ):
        """A config.toml from a release without networkWaitSecs is migrated first.

        --recover reads networkWaitSecs before delegating to --start (which is
        where migration used to happen), so it must migrate itself.
        """
        del sample_config["networkWaitSecs"]
        with open(tmp_script_dir / "config.toml", "wb") as fh:
            tomli_w.dump(sample_config, fh)

        seen = {}

        def capture(config, logger):
            seen["networkWaitSecs"] = config["networkWaitSecs"]
            return True

        with patch("stream.create_logger", return_value=mock_logger), \
             patch("stream._stream_process_already_running", return_value=False), \
             patch("stream.is_in_stream_window", return_value=True), \
             patch("stream.wait_for_network", side_effect=capture), \
             patch("stream.do_start"):
            stream.do_recover()

        assert seen["networkWaitSecs"] == stream.CONFIG_DEFAULTS["networkWaitSecs"]
        assert stream.load_config()["networkWaitSecs"] == stream.CONFIG_DEFAULTS["networkWaitSecs"]

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


# ── wait_for_network ────────────────────────────────────────────────────────


class TestWaitForNetwork:
    def test_probe_host_is_primary_rtmp_host(self, sample_config):
        """The probe host comes from youtube.streamURL — nothing is hardcoded."""
        assert stream._network_probe_host(sample_config) == "a.rtmp.youtube.com"

    def test_probe_host_none_when_stream_url_empty(self, sample_config):
        sample_config["youtube"]["streamURL"] = ""
        assert stream._network_probe_host(sample_config) is None

    def test_host_resolves_true(self):
        with patch("stream.socket.getaddrinfo", return_value=[("addr",)]):
            assert stream._host_resolves("a.rtmp.youtube.com") is True

    def test_host_resolves_false_on_gaierror(self):
        with patch("stream.socket.getaddrinfo", side_effect=socket.gaierror("no dns")):
            assert stream._host_resolves("a.rtmp.youtube.com") is False

    def test_host_resolves_false_on_oserror(self):
        with patch("stream.socket.getaddrinfo", side_effect=OSError("network unreachable")):
            assert stream._host_resolves("a.rtmp.youtube.com") is False

    def test_returns_immediately_when_network_up(self, sample_config, mock_logger):
        """No sleep and no noise when DNS already works."""
        with patch("stream._host_resolves", return_value=True) as mock_resolve, \
             patch("stream.time.sleep") as mock_sleep:
            assert stream.wait_for_network(sample_config, mock_logger) is True

        mock_resolve.assert_called_once_with("a.rtmp.youtube.com")
        mock_sleep.assert_not_called()
        mock_logger.info.assert_not_called()
        mock_logger.warn.assert_not_called()

    def test_waits_until_network_comes_up(self, sample_config, mock_logger):
        """Retries every retryDelaySecs until the host resolves, then logs recovery."""
        with patch("stream._host_resolves", side_effect=[False, False, True]), \
             patch("stream.time.sleep") as mock_sleep:
            assert stream.wait_for_network(sample_config, mock_logger) is True

        assert mock_sleep.call_args_list == [call(5), call(5)]
        infos = [c[0][0] for c in mock_logger.info.call_args_list]
        assert infos[0].startswith("Waiting up to 120s for the network")
        assert infos[-1] == "Network is up (a.rtmp.youtube.com resolves)"
        mock_logger.warn.assert_not_called()

    def test_gives_up_after_network_wait_secs(self, sample_config, mock_logger):
        """Stops after ceil(networkWaitSecs / retryDelaySecs) checks and warns."""
        sample_config["networkWaitSecs"] = 12
        sample_config["retryDelaySecs"] = 5
        with patch("stream._host_resolves", return_value=False) as mock_resolve, \
             patch("stream.time.sleep") as mock_sleep:
            assert stream.wait_for_network(sample_config, mock_logger) is False

        assert mock_resolve.call_count == 3
        # No pointless sleep after the final failed check.
        assert mock_sleep.call_count == 2
        mock_logger.warn.assert_called_once_with(
            "Network still unavailable after 12s — starting stream anyway"
        )

    @pytest.mark.parametrize("wait_secs", [0, -5])
    def test_zero_or_negative_wait_checks_once(self, wait_secs, sample_config, mock_logger):
        """networkWaitSecs <= 0 still performs a single check and never sleeps."""
        sample_config["networkWaitSecs"] = wait_secs
        with patch("stream._host_resolves", return_value=False) as mock_resolve, \
             patch("stream.time.sleep") as mock_sleep:
            assert stream.wait_for_network(sample_config, mock_logger) is False

        mock_resolve.assert_called_once()
        mock_sleep.assert_not_called()

    def test_zero_retry_delay_does_not_divide_by_zero(self, sample_config, mock_logger):
        """retryDelaySecs = 0 falls back to a 1-second interval."""
        sample_config["retryDelaySecs"] = 0
        sample_config["networkWaitSecs"] = 3
        with patch("stream._host_resolves", return_value=False) as mock_resolve, \
             patch("stream.time.sleep") as mock_sleep:
            stream.wait_for_network(sample_config, mock_logger)

        assert mock_resolve.call_count == 3
        assert mock_sleep.call_args_list == [call(1), call(1)]

    def test_skipped_without_stream_url(self, sample_config, mock_logger):
        """With no RTMP URL configured there is nothing to probe — returns True."""
        sample_config["youtube"]["streamURL"] = ""
        with patch("stream._host_resolves") as mock_resolve:
            assert stream.wait_for_network(sample_config, mock_logger) is True

        mock_resolve.assert_not_called()
