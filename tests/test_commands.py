"""Tests for _validate_youtube_config, _connect_to_broadcast, main() dispatch,
do_start/do_stop orchestration."""

import pytest
from unittest.mock import MagicMock, patch, call

import stream


# ── _validate_youtube_config ────────────────────────────────────────────────


class TestValidateYoutubeConfig:
    @pytest.fixture
    def errors_res(self, sample_resources):
        """Return the resources dict (has 'errors' key with 'missing_config')."""
        return sample_resources

    def test_validate_config_all_present(self, sample_config, errors_res):
        """No exception when broadcastId, streamURL, and streamKey are all present."""
        stream._validate_youtube_config(sample_config, errors_res)

    def test_validate_config_missing_broadcast_id(self, sample_config, errors_res):
        """RuntimeError mentions 'broadcastId' when it is empty."""
        sample_config["youtube"]["broadcastId"] = ""
        with pytest.raises(RuntimeError, match="broadcastId"):
            stream._validate_youtube_config(sample_config, errors_res)

    def test_validate_config_missing_stream_url(self, sample_config, errors_res):
        """RuntimeError mentions 'streamURL' when it is empty."""
        sample_config["youtube"]["streamURL"] = ""
        with pytest.raises(RuntimeError, match="streamURL"):
            stream._validate_youtube_config(sample_config, errors_res)

    def test_validate_config_missing_stream_key(self, sample_config, errors_res):
        """RuntimeError mentions 'streamKey' when it is empty."""
        sample_config["youtube"]["streamKey"] = ""
        with pytest.raises(RuntimeError, match="streamKey"):
            stream._validate_youtube_config(sample_config, errors_res)

    def test_validate_config_multiple_missing(self, sample_config, errors_res):
        """All missing field names appear in the error when multiple are empty."""
        sample_config["youtube"]["broadcastId"] = ""
        sample_config["youtube"]["streamURL"] = ""
        sample_config["youtube"]["streamKey"] = ""
        with pytest.raises(RuntimeError) as exc_info:
            stream._validate_youtube_config(sample_config, errors_res)
        msg = str(exc_info.value)
        assert "broadcastId" in msg
        assert "streamURL" in msg
        assert "streamKey" in msg


# ── _connect_to_broadcast ───────────────────────────────────────────────────


class TestConnectToBroadcast:
    def test_connect_returns_context(self, sample_config, mock_logger):
        """_connect_to_broadcast returns a BroadcastContext with correct fields."""
        mock_creds = MagicMock()
        mock_youtube = MagicMock()

        with patch("stream.get_valid_credentials", return_value=mock_creds), \
             patch("stream.build_youtube_service", return_value=mock_youtube):
            ctx = stream._connect_to_broadcast(sample_config, mock_logger, attempt_number=0)

        assert isinstance(ctx, stream.BroadcastContext)
        assert ctx.broadcast_id == "bcast-123"
        assert ctx.stream_id == "stream-456"
        assert ctx.rtmp_url == "rtmp://a.rtmp.youtube.com/live2"
        assert ctx.stream_key == "xxxx-yyyy-zzzz"
        assert ctx.youtube is mock_youtube

    def test_connect_alternates_rtmp(self, sample_config, mock_logger):
        """Even attempts use the primary URL; odd attempts use the backup URL."""
        mock_creds = MagicMock()
        mock_youtube = MagicMock()

        with patch("stream.get_valid_credentials", return_value=mock_creds), \
             patch("stream.build_youtube_service", return_value=mock_youtube):
            ctx0 = stream._connect_to_broadcast(sample_config, mock_logger, attempt_number=0)
            ctx1 = stream._connect_to_broadcast(sample_config, mock_logger, attempt_number=1)

        assert ctx0.rtmp_url == sample_config["youtube"]["streamURL"]
        assert ctx1.rtmp_url == sample_config["youtube"]["backupStreamUrl"]

    def test_connect_finds_stream_when_id_empty(self, sample_config, mock_logger):
        """When streamId is empty, find_stream_by_key is called to locate it."""
        sample_config["youtube"]["streamId"] = ""
        mock_creds = MagicMock()
        mock_youtube = MagicMock()

        with patch("stream.get_valid_credentials", return_value=mock_creds), \
             patch("stream.build_youtube_service", return_value=mock_youtube), \
             patch("stream.find_stream_by_key", return_value="found-id") as mock_find:
            ctx = stream._connect_to_broadcast(sample_config, mock_logger, attempt_number=0)

        mock_find.assert_called_once_with(mock_youtube, "xxxx-yyyy-zzzz", mock_logger)
        assert ctx.stream_id == "found-id"


# ── main() dispatch ─────────────────────────────────────────────────────────


class TestMainDispatch:
    def test_main_install(self):
        """--install dispatches to do_install."""
        with patch("sys.argv", ["stream.py", "--install"]), \
             patch("stream.do_install") as mock_install:
            stream.main()
        mock_install.assert_called_once()

    def test_main_start(self):
        """--start dispatches to do_start."""
        with patch("sys.argv", ["stream.py", "--start"]), \
             patch("stream.do_start") as mock_start:
            stream.main()
        mock_start.assert_called_once()

    def test_main_stop(self):
        """--stop dispatches to do_stop."""
        with patch("sys.argv", ["stream.py", "--stop"]), \
             patch("stream.do_stop") as mock_stop:
            stream.main()
        mock_stop.assert_called_once()

    def test_main_update(self):
        """--update dispatches to do_update."""
        with patch("sys.argv", ["stream.py", "--update"]), \
             patch("stream.do_update") as mock_update:
            stream.main()
        mock_update.assert_called_once()

    def test_main_rollback_with_version(self):
        """--roll-back v0.1.2 dispatches to do_rollback with the version string."""
        with patch("sys.argv", ["stream.py", "--roll-back", "v0.1.2"]), \
             patch("stream.do_rollback") as mock_rollback:
            stream.main()
        mock_rollback.assert_called_once_with("v0.1.2")

    def test_main_rollback_no_version(self):
        """--roll-back without a version dispatches to do_rollback with None."""
        with patch("sys.argv", ["stream.py", "--roll-back"]), \
             patch("stream.do_rollback") as mock_rollback:
            stream.main()
        mock_rollback.assert_called_once_with(None)

    def test_main_no_args(self):
        """Running with no arguments raises SystemExit."""
        with patch("sys.argv", ["stream.py"]):
            with pytest.raises(SystemExit):
                stream.main()


# ── do_stop orchestration ──────────────────────────────────────────────────


class TestDoStopOrchestration:
    def test_do_stop_sequence(self, sample_config, mock_logger):
        """do_stop calls load_config, load_env, create_logger, signal, cleanup in order."""
        call_order = []

        def track(name):
            def side_effect(*args, **kwargs):
                call_order.append(name)
                if name == "load_config":
                    return sample_config
                if name == "create_logger":
                    return mock_logger
            return side_effect

        with patch("stream.load_config", side_effect=track("load_config")), \
             patch("stream.load_env", side_effect=track("load_env")), \
             patch("stream.create_logger", side_effect=track("create_logger")), \
             patch("stream._signal_running_process", side_effect=track("signal")), \
             patch("stream._cleanup_stop_files", side_effect=track("cleanup")):
            stream.do_stop()

        assert call_order == [
            "load_config", "load_env", "create_logger", "signal", "cleanup"
        ]
        # Verify the "Clean shutdown" message was logged
        info_messages = [str(c) for c in mock_logger.info.call_args_list]
        assert any("Clean shutdown" in msg for msg in info_messages)


# ── do_start orchestration ─────────────────────────────────────────────────


class TestDoStartOrchestration:
    def test_do_start_validates_config(self, sample_config, sample_resources):
        """do_start raises RuntimeError when broadcastId is missing."""
        sample_config["youtube"]["broadcastId"] = ""

        with patch("stream.load_config", return_value=sample_config), \
             patch("stream.load_env"), \
             patch("stream.load_resources", return_value=sample_resources):
            with pytest.raises(RuntimeError, match="broadcastId"):
                stream.do_start()
