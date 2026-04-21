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

    def test_main_recover(self):
        """--recover dispatches to do_recover."""
        with patch("sys.argv", ["stream.py", "--recover"]), \
             patch("stream.do_recover") as mock_recover:
            stream.main()
        mock_recover.assert_called_once()

    def test_main_uninstall(self):
        """--uninstall dispatches to do_uninstall."""
        with patch("sys.argv", ["stream.py", "--uninstall"]), \
             patch("stream.do_uninstall") as mock_uninstall:
            stream.main()
        mock_uninstall.assert_called_once()

    def test_main_reinstall(self):
        """--reinstall dispatches to do_reinstall."""
        with patch("sys.argv", ["stream.py", "--reinstall"]), \
             patch("stream.do_reinstall") as mock_reinstall:
            stream.main()
        mock_reinstall.assert_called_once()

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


class TestCompleteBroadcast:
    def test_complete_broadcast_live(self, sample_config, mock_logger):
        """Transitions the broadcast to complete when it is live."""
        mock_creds = MagicMock()
        mock_youtube = MagicMock()

        with patch("stream.get_valid_credentials", return_value=mock_creds), \
             patch("stream.build_youtube_service", return_value=mock_youtube), \
             patch("stream._api_get_broadcast_lifecycle", return_value="live"), \
             patch("stream._api_transition_broadcast") as mock_trans:
            stream._complete_broadcast(sample_config, mock_logger)

        mock_trans.assert_called_once_with(mock_youtube, "bcast-123", "complete")

    def test_complete_broadcast_already_complete(self, sample_config, mock_logger):
        """Does not call transition when already complete."""
        mock_creds = MagicMock()
        mock_youtube = MagicMock()

        with patch("stream.get_valid_credentials", return_value=mock_creds), \
             patch("stream.build_youtube_service", return_value=mock_youtube), \
             patch("stream._api_get_broadcast_lifecycle", return_value="complete"), \
             patch("stream._api_transition_broadcast") as mock_trans:
            stream._complete_broadcast(sample_config, mock_logger)

        mock_trans.assert_not_called()

    def test_complete_broadcast_no_broadcast_id(self, sample_config, mock_logger):
        """Skips completion when broadcast ID is empty."""
        sample_config["youtube"]["broadcastId"] = ""

        with patch("stream.get_valid_credentials") as mock_creds:
            stream._complete_broadcast(sample_config, mock_logger)

        mock_creds.assert_not_called()

    def test_complete_broadcast_handles_error(self, sample_config, mock_logger):
        """Logs a warning if completion fails instead of crashing."""
        with patch("stream.get_valid_credentials", side_effect=Exception("auth failed")):
            stream._complete_broadcast(sample_config, mock_logger)

        mock_logger.warn.assert_called_once()


class TestCleanupOrphanedBroadcastsSafely:
    def test_cleanup_calls_cleanup_function(self, sample_config, mock_logger):
        """Authenticates and calls cleanup_orphaned_broadcasts."""
        mock_creds = MagicMock()
        mock_youtube = MagicMock()

        with patch("stream.get_valid_credentials", return_value=mock_creds), \
             patch("stream.build_youtube_service", return_value=mock_youtube), \
             patch("stream.cleanup_orphaned_broadcasts") as mock_cleanup:
            stream._cleanup_orphaned_broadcasts_safely(sample_config, mock_logger)

        mock_cleanup.assert_called_once_with(mock_youtube, "bcast-123", mock_logger)

    def test_cleanup_handles_auth_error(self, sample_config, mock_logger):
        """Authentication errors are logged, not raised."""
        with patch("stream.get_valid_credentials", side_effect=Exception("auth failed")):
            stream._cleanup_orphaned_broadcasts_safely(sample_config, mock_logger)

        mock_logger.warn.assert_called_once()


class TestCreateFreshBroadcast:
    def test_create_fresh_broadcast(self, tmp_script_dir, sample_config, mock_logger):
        """Creates a new broadcast, binds stream, saves config, returns new ID."""
        mock_youtube = MagicMock()

        with patch("stream.create_broadcast", return_value="new-bcast-456"), \
             patch("stream.find_stream_by_key", return_value="stream-resolved") as mock_find, \
             patch("stream.bind_stream_to_broadcast") as mock_bind, \
             patch("stream.apply_broadcast_category") as mock_cat, \
             patch("stream.apply_video_embeddable") as mock_embed, \
             patch("stream.save_config") as mock_save:
            result = stream._create_fresh_broadcast(mock_youtube, sample_config, mock_logger)

        assert result == "new-bcast-456"
        assert sample_config["youtube"]["broadcastId"] == "new-bcast-456"
        mock_find.assert_called_once_with(mock_youtube, "xxxx-yyyy-zzzz", mock_logger)
        mock_bind.assert_called_once_with(mock_youtube, "new-bcast-456", "stream-resolved", mock_logger)
        mock_cat.assert_called_once_with(mock_youtube, "new-bcast-456", "22", mock_logger)
        mock_embed.assert_called_once_with(mock_youtube, "new-bcast-456", True, mock_logger)
        mock_save.assert_called_once_with(sample_config)


class TestDoStopOrchestration:
    def test_do_stop_sequence(self, sample_config, mock_logger):
        """do_stop calls load_config, load_env, create_logger, signal, complete, cleanup in order."""
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
             patch("stream._complete_broadcast", side_effect=track("complete")), \
             patch("stream._cleanup_stop_files", side_effect=track("cleanup")):
            stream.do_stop()

        assert call_order == [
            "load_config", "load_env", "create_logger", "signal", "complete", "cleanup"
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


# ── do_set_property ─────────────────────────────────────────────────────────


class TestDoSetProperty:
    def test_sets_single_property(self, config_on_disk, capsys):
        """A single property is written to config.toml and confirmed."""
        stream.do_set_property([["youtube.privacy", "unlisted"]])

        result = stream.load_config()
        assert result["youtube"]["privacy"] == "unlisted"
        out = capsys.readouterr().out
        assert "youtube.privacy" in out
        assert "Config saved" in out

    def test_sets_multiple_properties(self, config_on_disk):
        """Multiple properties are all written in one call."""
        stream.do_set_property([
            ["youtube.privacy", "private"],
            ["cron.autoUpdate", "true"],
            ["logRetentionDays", "30"],
        ])

        result = stream.load_config()
        assert result["youtube"]["privacy"] == "private"
        assert result["cron"]["autoUpdate"] is True
        assert result["logRetentionDays"] == 30

    def test_coerces_bool(self, config_on_disk):
        """String 'true'/'false' are coerced to native bool."""
        stream.do_set_property([["stream.mute", "true"]])
        assert stream.load_config()["stream"]["mute"] is True

        stream.do_set_property([["stream.mute", "false"]])
        assert stream.load_config()["stream"]["mute"] is False

    def test_coerces_int(self, config_on_disk):
        """String integer is coerced to int."""
        stream.do_set_property([["retryDelaySecs", "10"]])
        result = stream.load_config()
        assert result["retryDelaySecs"] == 10
        assert isinstance(result["retryDelaySecs"], int)

    def test_sets_key_missing_from_config_but_in_schema(self, tmp_script_dir, sample_config):
        """A key absent from config.toml but present in CONFIG_DEFAULTS is accepted."""
        del sample_config["cron"]["autoUpdate"]
        import tomli_w
        with open(tmp_script_dir / "config.toml", "wb") as fh:
            tomli_w.dump(sample_config, fh)

        stream.do_set_property([["cron.autoUpdate", "true"]])
        assert stream.load_config()["cron"]["autoUpdate"] is True

    def test_unknown_key_raises(self, config_on_disk):
        """Unknown dot-notation key raises ValueError without touching config."""
        with pytest.raises(ValueError, match="Unknown config key"):
            stream.do_set_property([["totally.unknown", "val"]])

    def test_section_path_raises(self, config_on_disk):
        """Providing a section name raises ValueError."""
        with pytest.raises(ValueError, match="section"):
            stream.do_set_property([["youtube", "something"]])

    def test_invalid_bool_raises(self, config_on_disk):
        """An invalid value for a bool key raises ValueError."""
        with pytest.raises(ValueError, match="boolean"):
            stream.do_set_property([["cron.autoUpdate", "banana"]])

    def test_dispatch_single(self):
        """main() routes --set-property key val to do_set_property."""
        with patch("sys.argv", ["stream.py", "--set-property", "youtube.privacy", "private"]), \
             patch("stream.do_set_property") as mock_set:
            stream.main()
        mock_set.assert_called_once_with([["youtube.privacy", "private"]])

    def test_dispatch_multiple(self):
        """main() collects repeated --set-property into a list of pairs."""
        with patch("sys.argv", [
            "stream.py",
            "--set-property", "youtube.privacy", "private",
            "--set-property", "cron.autoUpdate", "true",
        ]), patch("stream.do_set_property") as mock_set:
            stream.main()
        mock_set.assert_called_once_with([
            ["youtube.privacy", "private"],
            ["cron.autoUpdate", "true"],
        ])
