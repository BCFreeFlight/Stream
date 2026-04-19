"""Tests for do_uninstall orchestration."""

from unittest.mock import patch

import stream


class TestDoUninstall:
    def test_removes_cron_entries(self, sample_config, config_on_disk, env_on_disk, capsys):
        """remove_cron_entries is called to clear start/stop/recover lines."""
        with patch("stream.do_stop"), \
             patch("stream.remove_cron_entries") as mock_remove, \
             patch("stream._stream_process_already_running", return_value=False):
            # Clear broadcastId so do_stop is not called.
            sample_config["youtube"]["broadcastId"] = ""
            with patch("stream.load_config", return_value=sample_config):
                stream.do_uninstall()

        mock_remove.assert_called_once()

    def test_calls_do_stop_when_stream_running(
        self, sample_config, config_on_disk, env_on_disk, capsys
    ):
        """When a stream process is alive, do_stop is invoked before removing cron."""
        with patch("stream._stream_process_already_running", return_value=True), \
             patch("stream.do_stop") as mock_stop, \
             patch("stream.remove_cron_entries") as mock_remove, \
             patch("stream.load_config", return_value=sample_config):
            stream.do_uninstall()

        mock_stop.assert_called_once()
        mock_remove.assert_called_once()

    def test_calls_do_stop_when_broadcast_exists_even_without_running_process(
        self, sample_config, config_on_disk, env_on_disk, capsys
    ):
        """If no local process but a broadcastId is configured, do_stop still runs
        so YouTube's broadcast is archived cleanly."""
        with patch("stream._stream_process_already_running", return_value=False), \
             patch("stream.do_stop") as mock_stop, \
             patch("stream.remove_cron_entries"), \
             patch("stream.load_config", return_value=sample_config):
            stream.do_uninstall()

        mock_stop.assert_called_once()

    def test_skips_do_stop_when_nothing_to_stop(
        self, sample_config, config_on_disk, env_on_disk, capsys
    ):
        """If no stream is running AND no broadcast is configured, do_stop is skipped."""
        sample_config["youtube"]["broadcastId"] = ""
        with patch("stream._stream_process_already_running", return_value=False), \
             patch("stream.do_stop") as mock_stop, \
             patch("stream.remove_cron_entries"), \
             patch("stream.load_config", return_value=sample_config):
            stream.do_uninstall()

        mock_stop.assert_not_called()

    def test_preserves_config_file(
        self, sample_config, config_on_disk, env_on_disk
    ):
        """The config.toml file remains on disk after --uninstall."""
        with patch("stream._stream_process_already_running", return_value=False), \
             patch("stream.do_stop"), \
             patch("stream.remove_cron_entries"), \
             patch("stream.load_config", return_value=sample_config):
            stream.do_uninstall()

        assert config_on_disk.exists()

    def test_preserves_env_file(
        self, sample_config, config_on_disk, env_on_disk
    ):
        """The .env file remains on disk after --uninstall."""
        with patch("stream._stream_process_already_running", return_value=False), \
             patch("stream.do_stop"), \
             patch("stream.remove_cron_entries"), \
             patch("stream.load_config", return_value=sample_config):
            stream.do_uninstall()

        assert env_on_disk.exists()

    def test_prints_summary_of_preserved_files(
        self, sample_config, config_on_disk, env_on_disk, capsys
    ):
        """User-facing output points at the files left on disk."""
        sample_config["youtube"]["broadcastId"] = ""
        with patch("stream._stream_process_already_running", return_value=False), \
             patch("stream.remove_cron_entries"), \
             patch("stream.load_config", return_value=sample_config):
            stream.do_uninstall()

        captured = capsys.readouterr()
        assert "preserved" in captured.out.lower()
        assert "config.toml" in captured.out
        assert ".env" in captured.out
