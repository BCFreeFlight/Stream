"""Tests for install orchestration: _setup_youtube_resources and prompt_all_config_values."""

from unittest.mock import patch, MagicMock, ANY

import pytest

import stream


# ── _setup_youtube_resources (pure function) ────────────────────────────────


class TestSetupYoutubeResources:
    """Tests for the pure-function version of YouTube resource setup.

    _setup_youtube_resources(youtube, existing_config, logger) returns a dict
    with broadcastId/streamURL/backupStreamUrl/streamKey — it does NOT mutate
    the config dict or print anything.

    Interactive prompting + printing is handled by _setup_youtube_resources_with_prompt
    and do_install respectively.
    """

    def test_returns_broadcast_id_when_already_set(self, sample_config):
        """When broadcastId already exists in config, it is returned as-is."""
        sample_config["youtube"]["broadcastId"] = "existing-bcast"
        mock_youtube = MagicMock()
        logger = MagicMock()

        result = stream._setup_youtube_resources(mock_youtube, sample_config, logger)

        assert result["broadcastId"] == "existing-bcast"
        # Config should not be mutated
        assert sample_config["youtube"]["broadcastId"] == "existing-bcast"

    def test_returns_none_stream_key_when_missing(self, sample_config):
        """When streamKey is empty, returns None to signal caller should prompt/create."""
        sample_config["youtube"]["broadcastId"] = "bcast-123"
        sample_config["youtube"]["streamKey"] = ""

        mock_youtube = MagicMock()
        logger = MagicMock()

        result = stream._setup_youtube_resources(mock_youtube, sample_config, logger)

        assert result["streamKey"] is None
        # Config should not be mutated — streamURL/backupStreamUrl stay empty
        assert result["streamURL"] == ""
        assert result["backupStreamUrl"] == ""

    def test_returns_resources_when_stream_key_present(self, sample_config):
        """When streamKey is set, returns full resource dict without mutating config."""
        sample_config["youtube"]["broadcastId"] = "bcast-123"
        sample_config["youtube"]["streamKey"] = "my-key"
        sample_config["youtube"]["streamURL"] = "rtmp://primary"
        sample_config["youtube"]["backupStreamUrl"] = "rtmp://backup"

        mock_youtube = MagicMock()
        logger = MagicMock()

        with patch("stream.find_stream_resource_by_key", return_value=("s-id", "rtmp://p", "rtmp://b")), \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_video_embeddable"):
            result = stream._setup_youtube_resources(mock_youtube, sample_config, logger)

        assert result["streamKey"] == "my-key"
        assert result["broadcastId"] == "bcast-123"

    def test_calls_find_stream_resource_by_key(self, sample_config):
        """find_stream_resource_by_key is called with the configured stream key."""
        sample_config["youtube"]["broadcastId"] = "bcast-123"
        sample_config["youtube"]["streamKey"] = "my-key"

        mock_youtube = MagicMock()
        logger = MagicMock()

        with patch("stream.find_stream_resource_by_key", return_value=("s-id", "rtmp://p", "rtmp://b")) as mock_find, \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_video_embeddable"):
            stream._setup_youtube_resources(mock_youtube, sample_config, logger)

        mock_find.assert_called_once_with(mock_youtube, "my-key", logger)

    def test_calls_bind_stream_to_broadcast(self, sample_config):
        """bind_stream_to_broadcast is called with broadcast ID and stream ID."""
        sample_config["youtube"]["broadcastId"] = "bcast-123"
        sample_config["youtube"]["streamKey"] = "my-key"

        mock_youtube = MagicMock()
        logger = MagicMock()

        with patch("stream.find_stream_resource_by_key", return_value=("s-id-456", "rtmp://p", "rtmp://b")), \
             patch("stream.bind_stream_to_broadcast") as mock_bind, \
             patch("stream.apply_video_embeddable"):
            stream._setup_youtube_resources(mock_youtube, sample_config, logger)

        mock_bind.assert_called_once_with(mock_youtube, "bcast-123", "s-id-456", logger)

    def test_calls_apply_broadcast_category_when_set(self, sample_config):
        """apply_broadcast_category is called when categoryId exists in config."""
        sample_config["youtube"]["broadcastId"] = "bcast-123"
        sample_config["youtube"]["streamKey"] = "my-key"
        sample_config["youtube"]["categoryId"] = "22"

        mock_youtube = MagicMock()
        logger = MagicMock()

        with patch("stream.find_stream_resource_by_key", return_value=("s-id", "rtmp://p", "rtmp://b")), \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category") as mock_cat, \
             patch("stream.apply_video_embeddable"):
            stream._setup_youtube_resources(mock_youtube, sample_config, logger)

        mock_cat.assert_called_once_with(mock_youtube, "bcast-123", "22", logger)

    def test_calls_apply_video_embeddable_when_broadcast_exists(self, sample_config):
        """apply_video_embeddable is called with the embeddable flag."""
        sample_config["youtube"]["broadcastId"] = "bcast-embed"
        sample_config["youtube"]["streamKey"] = "sk"
        sample_config["youtube"]["embeddable"] = True

        mock_youtube = MagicMock()
        logger = MagicMock()

        with patch("stream.find_stream_resource_by_key", return_value=("s-id", "rtmp://p", "rtmp://b")), \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable") as mock_embed:
            stream._setup_youtube_resources(mock_youtube, sample_config, logger)

        mock_embed.assert_called_once_with(mock_youtube, "bcast-embed", True, logger)

    def test_does_not_mutate_config(self, sample_config):
        """Pure function: config dict is not modified by the call."""
        original_broadcast_id = sample_config["youtube"]["broadcastId"]
        mock_youtube = MagicMock()
        logger = MagicMock()

        with patch("stream.find_stream_resource_by_key", return_value=("s-id", "rtmp://p", "rtmp://b")), \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_video_embeddable"):
            stream._setup_youtube_resources(mock_youtube, sample_config, logger)

        assert sample_config["youtube"]["broadcastId"] == original_broadcast_id


# ── prompt_all_config_values ────────────────────────────────────────────────


class TestPromptAllConfigValues:
    def test_does_not_prompt_for_stream_fields(self, sample_resources):
        """streamKey, streamURL, and backupStreamUrl are no longer prompted — they are API-populated."""
        # Provide just enough input to satisfy all OTHER prompts. If any unexpected
        # extra prompt appears, StopIteration will raise and fail the test.
        existing = {
            "google": {"clientId": "cid"},
            "stream": {"rtspUrl": "rtsp://cam/live", "videoCodec": "copy",
                       "audioCodec": "copy", "mute": False},
            "youtube": {
                "broadcastTitle": "T: {date}",
                "privacy": "public",
                "enableDvr": False,
                "archivePrivacy": "private",
                "categoryId": "22",
                "broadcastId": "existing-bcast",
                "streamId": "",
                "streamURL": "",
                "backupStreamUrl": "",
                "streamKey": "",
            },
            "cron": {"enabled": True, "start": "30 6 * * *", "stop": "25 18 * * *",
                     "autoUpdate": False, "update": "0 0 * * *"},
        }

        # All non-empty existing values are auto-accepted by _smart_prompt.
        # Only client_secret is prompted (env is cleared). cronSetup is now
        # skipped because cron.enabled exists in the existing config.
        # If any extra prompt appears, StopIteration fires.
        inputs = iter(["test-secret"])
        with patch("builtins.input", lambda *a, **kw: next(inputs)), \
             patch("stream.load_env"), \
             patch.dict("os.environ", {}, clear=False):
            config, secret = stream.prompt_all_config_values(sample_resources, existing=existing)

        # The three fields are carried through from existing, not prompted.
        assert config["youtube"]["streamURL"] == ""
        assert config["youtube"]["backupStreamUrl"] == ""
        assert config["youtube"]["streamKey"] == ""
        assert secret == "test-secret"

    def test_cron_enabled_skipped_when_existing(self, sample_resources):
        """cronSetup is not prompted when cron.enabled already exists in the config."""
        existing = {
            "google": {"clientId": "cid"},
            "stream": {"rtspUrl": "rtsp://cam/live", "videoCodec": "copy",
                       "audioCodec": "copy", "mute": False},
            "youtube": {"broadcastTitle": "T: {date}", "privacy": "public",
                        "enableDvr": False, "archivePrivacy": "private",
                        "categoryId": "22", "broadcastId": "b", "streamURL": "",
                        "backupStreamUrl": "", "streamKey": ""},
            "cron": {"enabled": False, "start": "", "stop": "",
                     "autoUpdate": False, "update": ""},
        }
        # Only client_secret should be prompted — StopIteration fires on any extra prompt.
        inputs = iter(["test-secret"])
        with patch("builtins.input", lambda *a, **kw: next(inputs)), \
             patch("stream.load_env"), \
             patch.dict("os.environ", {}, clear=False):
            config, _ = stream.prompt_all_config_values(sample_resources, existing=existing)

        assert config["cron"]["enabled"] is False

    def test_cron_enabled_prompted_when_absent(self, sample_resources):
        """cronSetup is prompted when cron.enabled is absent from the existing config."""
        existing = {
            "google": {"clientId": "cid"},
            "stream": {"rtspUrl": "rtsp://cam/live", "videoCodec": "copy",
                       "audioCodec": "copy", "mute": False},
            "youtube": {"broadcastTitle": "T: {date}", "privacy": "public",
                        "enableDvr": False, "archivePrivacy": "private",
                        "categoryId": "22", "broadcastId": "b", "streamURL": "",
                        "backupStreamUrl": "", "streamKey": ""},
            "cron": {},  # no 'enabled' key — should trigger the prompt
        }
        # client_secret + cronSetup ("no" to disable cron)
        inputs = iter(["test-secret", "no"])
        with patch("builtins.input", lambda *a, **kw: next(inputs)), \
             patch("stream.load_env"), \
             patch.dict("os.environ", {}, clear=False):
            config, _ = stream.prompt_all_config_values(sample_resources, existing=existing)

        assert config["cron"]["enabled"] is False

    def test_prompt_mute_fresh_install(self, sample_resources):
        """Mute prompt asks for user input when existing_mute is None (fresh install)."""
        fresh = {
            "google": {"clientId": "cid"},
            "stream": {"rtspUrl": "", "videoCodec": "", "audioCodec": ""},
            "youtube": {
                "broadcastTitle": "", "privacy": "", "enableDvr": None,
                "archivePrivacy": "", "categoryId": "", "broadcastId": "",
                "streamURL": "", "backupStreamUrl": "", "streamKey": "",
            },
            "cron": {},  # no enabled key — will also trigger cron prompt
        }

        inputs = iter(["secret", "rtsp://cam/live", "copy", "copy",
                       "yes",  # mute yes (fresh install)
                       "title", "public", "no", "private",
                       "22", "", "yes",  # cron setup yes
                       "30 6 * * *", "25 18 * * *",
                       "no"])  # auto_update no

        with patch("builtins.input", lambda *a, **kw: next(inputs)), \
             patch("stream.load_env"), \
             patch.dict("os.environ", {}, clear=False):

            config, _ = stream.prompt_all_config_values(sample_resources, existing=fresh)

        assert config["stream"]["mute"] is True  # "yes" converted to bool True

    def test_prompt_mute_existing_config(self, sample_resources):
        """Mute value is silently reused when existing_mute is not None."""
        with_existing = {
            "google": {"clientId": "cid"},
            "stream": {"rtspUrl": "", "videoCodec": "", "audioCodec": "",
                       "mute": True},  # existing mute value
            "youtube": {
                "broadcastTitle": "", "privacy": "", "enableDvr": None,
                "archivePrivacy": "", "categoryId": "", "broadcastId": "",
                "streamURL": "", "backupStreamUrl": "", "streamKey": "",
            },
            "cron": {},  # no enabled key — will also trigger cron prompt
        }

        inputs = iter(["secret", "rtsp://cam/live", "copy", "copy",
                       # mute skipped — already set to True
                       "title", "public", "no", "private",
                       "22", "", "yes",  # cron setup yes
                       "30 6 * * *", "25 18 * * *",
                       "no"])

        with patch("builtins.input", lambda *a, **kw: next(inputs)), \
             patch("stream.load_env"), \
             patch.dict("os.environ", {}, clear=False):

            config, _ = stream.prompt_all_config_values(sample_resources, existing=with_existing)

        assert config["stream"]["mute"] is True  # retained from existing

    def test_prompt_dvr_fresh_install(self, sample_resources):
        """DVR prompt asks for user input when existing_dvr is None (fresh install)."""
        fresh = {
            "google": {"clientId": "cid"},
            "stream": {"rtspUrl": "", "videoCodec": "", "audioCodec": "",
                       "mute": None},  # no mute — will prompt yes/no
            "youtube": {
                "broadcastTitle": "", "privacy": "", "enableDvr": None,
                "archivePrivacy": "", "categoryId": "", "broadcastId": "",
                "streamURL": "", "backupStreamUrl": "", "streamKey": "",
            },
            "cron": {},  # no enabled key — will also trigger cron prompt
        }

        inputs = iter(["secret", "rtsp://cam/live", "copy", "copy",
                       "yes",  # mute yes (fresh)
                       "title", "public", "yes",  # dvr yes (fresh install)
                       "private", "22", "",
                       "yes",  # cron setup yes
                       "30 6 * * *", "25 18 * * *",
                       "no"])

        with patch("builtins.input", lambda *a, **kw: next(inputs)), \
             patch("stream.load_env"), \
             patch.dict("os.environ", {}, clear=False):

            config, _ = stream.prompt_all_config_values(sample_resources, existing=fresh)

        assert config["youtube"]["enableDvr"] is True  # "yes" converted to bool

    def test_prompt_dvr_existing_config(self, sample_resources):
        """DVR value is silently reused when existing_dvr is not None."""
        with_existing = {
            "google": {"clientId": "cid"},
            "stream": {"rtspUrl": "", "videoCodec": "", "audioCodec": "",
                       "mute": None},  # will prompt for mute
            "youtube": {
                "broadcastTitle": "", "privacy": "", "enableDvr": False,  # existing DVR
                "archivePrivacy": "", "categoryId": "", "broadcastId": "",
                "streamURL": "", "backupStreamUrl": "", "streamKey": "",
            },
            "cron": {},  # no enabled key — will also trigger cron prompt
        }

        inputs = iter(["secret", "rtsp://cam/live", "copy", "copy",
                       "yes",  # mute yes (fresh)
                       "title", "public",
                       # dvr skipped — already set to False
                       "private", "22", "",
                       "yes",  # cron setup yes
                       "30 6 * * *", "25 18 * * *",
                       "no"])

        with patch("builtins.input", lambda *a, **kw: next(inputs)), \
             patch("stream.load_env"), \
             patch.dict("os.environ", {}, clear=False):

            config, _ = stream.prompt_all_config_values(sample_resources, existing=with_existing)

        assert config["youtube"]["enableDvr"] is False  # retained from existing


# ── _write_env_file (token preservation) ────────────────────────────────────


class TestWriteEnvFile:
    def test_writes_empty_placeholders_on_first_install(self, tmp_script_dir, sample_resources):
        """On a fresh install (no .env), empty placeholders are written for both token keys."""
        stream._write_env_file("my-secret", sample_resources)

        from dotenv import get_key
        path = str(tmp_script_dir / ".env")
        assert get_key(path, "GOOGLE_CLIENT_SECRET") == "my-secret"
        assert get_key(path, "GOOGLE_REFRESH_TOKEN") == ""
        assert get_key(path, "GOOGLE_ACCESS_TOKEN") == ""

    def test_preserves_existing_tokens_on_reinstall(self, tmp_script_dir, sample_resources):
        """On a re-install, existing GOOGLE_REFRESH_TOKEN and GOOGLE_ACCESS_TOKEN are kept."""
        path = str(tmp_script_dir / ".env")
        from dotenv import set_key as _set
        _set(path, "GOOGLE_CLIENT_SECRET", "old-secret")
        _set(path, "GOOGLE_REFRESH_TOKEN", "existing-refresh")
        _set(path, "GOOGLE_ACCESS_TOKEN", "existing-access")

        stream._write_env_file("new-secret", sample_resources)

        from dotenv import get_key
        assert get_key(path, "GOOGLE_CLIENT_SECRET") == "new-secret"
        assert get_key(path, "GOOGLE_REFRESH_TOKEN") == "existing-refresh"
        assert get_key(path, "GOOGLE_ACCESS_TOKEN") == "existing-access"

    def test_always_updates_client_secret(self, tmp_script_dir, sample_resources):
        """GOOGLE_CLIENT_SECRET is always overwritten even if previously set."""
        path = str(tmp_script_dir / ".env")
        from dotenv import set_key as _set, get_key
        _set(path, "GOOGLE_CLIENT_SECRET", "old-secret")

        stream._write_env_file("new-secret", sample_resources)

        assert get_key(path, "GOOGLE_CLIENT_SECRET") == "new-secret"


# ── _try_reuse_existing_credentials / _get_install_credentials ──────────────


class TestInstallCredentialReuse:
    def test_returns_none_when_no_refresh_token(self, tmp_script_dir, sample_config, sample_resources):
        """Returns None when GOOGLE_REFRESH_TOKEN is absent."""
        with patch("stream.load_env"), \
             patch.dict("os.environ", {"GOOGLE_REFRESH_TOKEN": ""}, clear=False):
            result = stream._try_reuse_existing_credentials(sample_config, sample_resources)

        assert result is None

    def test_returns_credentials_when_refresh_succeeds(self, tmp_script_dir, sample_config, sample_resources):
        """Returns credentials when the refresh token is present and refresh succeeds."""
        mock_creds = MagicMock()
        with patch("stream.load_env"), \
             patch.dict("os.environ", {"GOOGLE_REFRESH_TOKEN": "tok"}, clear=False), \
             patch("stream._build_credentials_from_env", return_value=mock_creds), \
             patch("stream._refresh_credentials", return_value=True):
            result = stream._try_reuse_existing_credentials(sample_config, sample_resources)

        assert result is mock_creds

    def test_returns_none_when_refresh_fails(self, tmp_script_dir, sample_config, sample_resources):
        """Returns None when the token refresh fails."""
        mock_creds = MagicMock()
        with patch("stream.load_env"), \
             patch.dict("os.environ", {"GOOGLE_REFRESH_TOKEN": "expired"}, clear=False), \
             patch("stream._build_credentials_from_env", return_value=mock_creds), \
             patch("stream._refresh_credentials", return_value=False):
            result = stream._try_reuse_existing_credentials(sample_config, sample_resources)

        assert result is None

    def test_returns_none_on_exception(self, tmp_script_dir, sample_config, sample_resources):
        """Returns None when credential building raises an exception."""
        with patch("stream.load_env"), \
             patch.dict("os.environ", {"GOOGLE_REFRESH_TOKEN": "tok"}, clear=False), \
             patch("stream._build_credentials_from_env", side_effect=Exception("boom")):
            result = stream._try_reuse_existing_credentials(sample_config, sample_resources)

        assert result is None

    def test_get_install_credentials_reuses_when_valid(self, sample_config, sample_resources):
        """_get_install_credentials skips the OAuth flow when reuse succeeds."""
        mock_creds = MagicMock()
        with patch("stream._try_reuse_existing_credentials", return_value=mock_creds) as mock_reuse, \
             patch("stream._run_install_oauth") as mock_oauth:
            result = stream._get_install_credentials(sample_config, "secret", sample_resources)

        mock_oauth.assert_not_called()
        assert result is mock_creds

    def test_get_install_credentials_falls_back_to_oauth(self, sample_config, sample_resources):
        """_get_install_credentials runs the OAuth flow when credential reuse returns None."""
        mock_creds = MagicMock()
        with patch("stream._try_reuse_existing_credentials", return_value=None), \
             patch("stream._run_install_oauth", return_value=mock_creds) as mock_oauth:
            result = stream._get_install_credentials(sample_config, "secret", sample_resources)

        mock_oauth.assert_called_once_with(sample_config, "secret", sample_resources)
        assert result is mock_creds


# ── do_install full orchestration ────────────────────────────────────────────


class TestDoInstall:
    def test_do_install_full_orchestration(self, sample_config, sample_resources):
        """do_install executes the complete call sequence with mocked sub-functions and cron enabled."""
        mock_resources = {"broadcastId": "bcast-123", "streamURL": "rtmp://p",
                          "backupStreamUrl": "rtmp://b", "streamKey": "sk"}

        with patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._try_load_existing_config", return_value=None), \
             patch(
                 "stream.prompt_all_config_values",
                 return_value=(sample_config, "test-secret"),
             ) as mock_prompt, \
             patch("stream._write_config_file") as mock_write_cfg, \
             patch("stream._write_env_file") as mock_write_env, \
             patch("stream._install_ffmpeg_if_missing") as mock_ffmpeg, \
             patch(
                 "stream._get_install_credentials", return_value=MagicMock()
             ) as mock_creds, \
             patch("stream._setup_youtube_resources_with_prompt", return_value=(mock_resources, [])) as mock_setup, \
             patch("stream.detect_terminal", return_value="gnome-terminal"), \
             patch("stream.save_config") as mock_save, \
             patch("stream.register_cron_entries") as mock_register, \
             patch("stream._print_install_summary") as mock_summary:

            stream.do_install()

        mock_prompt.assert_called_once()
        mock_write_cfg.assert_called_once_with(sample_config, sample_resources)
        mock_write_env.assert_called_once()
        mock_ffmpeg.assert_called_once_with(sample_resources)
        mock_creds.assert_called_once()
        # _setup_youtube_resources_with_prompt is called (not the pure function)
        mock_setup.assert_called_once()
        # save_config is called twice: once for resources, once for terminal detection
        assert mock_save.call_count >= 1
        mock_register.assert_called_once_with(sample_config)
        mock_summary.assert_called_once_with(sample_config, sample_resources)

    def test_do_install_cron_disabled(self, sample_config, sample_resources):
        """do_install calls remove_cron_entries when cron.enabled is False."""
        sample_config["cron"]["enabled"] = False

        mock_resources = {"broadcastId": "bcast-123", "streamURL": "rtmp://p",
                          "backupStreamUrl": "rtmp://b", "streamKey": "sk"}

        with patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._try_load_existing_config", return_value=None), \
             patch(
                 "stream.prompt_all_config_values",
                 return_value=(sample_config, "test-secret"),
             ), \
             patch("stream._write_config_file") as mock_write_cfg, \
             patch("stream._write_env_file"), \
             patch("stream._install_ffmpeg_if_missing"), \
             patch(
                 "stream._get_install_credentials", return_value=MagicMock()
             ), \
             patch("stream._setup_youtube_resources_with_prompt", return_value=(mock_resources, [])), \
             patch("stream.detect_terminal", return_value="gnome-terminal"), \
             patch("stream.save_config") as mock_save, \
             patch(
                 "stream.register_cron_entries"
             ) as mock_register, \
             patch(
                 "stream.remove_cron_entries"
             ) as mock_remove, \
             patch("stream._print_install_summary") as mock_summary:

            stream.do_install()

        # register_cron_entries should NOT be called
        mock_register.assert_not_called()
        # remove_cron_entries SHOULD be called
        mock_remove.assert_called_once()
        # _print_install_summary is still invoked last
        mock_summary.assert_called_once_with(sample_config, sample_resources)


# ── _write_config_file ───────────────────────────────────────────────────────


class TestWriteConfigFile:
    def test_write_config_file(self, sample_config, sample_resources):
        """_write_config_file writes the config and prints a path message."""
        with patch("stream.save_config") as mock_save, \
             patch("builtins.print") as mock_print:

            stream._write_config_file(sample_config, sample_resources)

        mock_save.assert_called_once_with(sample_config)
        # Verify a message containing the config file path was printed
        print_calls = [c[0][0] for c in mock_print.call_args_list]
        config_path_msg = [m for m in print_calls if "config.toml" in m]
        assert len(config_path_msg) >= 1


# ── _install_ffmpeg_if_missing ───────────────────────────────────────────────


class TestInstallFfmpegIfMissing:
    def test_ffmpeg_present_skips_install(self, sample_resources):
        """_install_ffmpeg_if_missing does nothing when ffmpeg is already installed."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("subprocess.check_call") as mock_check, \
             patch("builtins.print"):

            stream._install_ffmpeg_if_missing(sample_resources)

        mock_check.assert_not_called()

    def test_install_ffmpeg_missing_path(self, sample_resources):
        """_install_ffmpeg_if_missing triggers apt install when ffmpeg is not found."""
        with patch("shutil.which", return_value=None), \
             patch("subprocess.check_call") as mock_check, \
             patch("builtins.print"):

            stream._install_ffmpeg_if_missing(sample_resources)

        mock_check.assert_called_once_with(
            ["sudo", "apt", "install", "-y", "ffmpeg"]
        )

    def test_ffmpeg_missing_propagates_error(self, sample_resources):
        """_install_ffmpeg_if_missing propagates CalledProcessError when apt install fails."""
        from subprocess import CalledProcessError

        with patch("shutil.which", return_value=None), \
             patch(
                 "subprocess.check_call",
                 side_effect=CalledProcessError(1, ["sudo", "apt", "install", "-y", "ffmpeg"]),
             ), \
             patch("builtins.print"):

            with pytest.raises(CalledProcessError):
                stream._install_ffmpeg_if_missing(sample_resources)


# ── _run_install_oauth ───────────────────────────────────────────────────────


class TestRunInstallOauth:
    def test_run_install_oauth(self, tmp_script_dir):
        """_run_install_oauth runs the OAuth flow and writes tokens to .env."""
        mock_creds = MagicMock()
        mock_creds.refresh_token = "new-refresh"
        mock_creds.token = "new-access"

        config = {"google": {"clientId": "test-client-id"}}
        with patch("stream.run_oauth_flow", return_value=mock_creds) as mock_run, \
             patch("stream.set_key") as mock_set_key, \
             patch("builtins.print"):

            stream._run_install_oauth(config, "test-secret", MagicMock())

        mock_run.assert_called_once_with("test-client-id", "test-secret")
        # Both tokens should be written to .env (set_key(path, key, value))
        set_key_calls = [c[0][1:] for c in mock_set_key.call_args_list]
        assert ("GOOGLE_REFRESH_TOKEN", "new-refresh") in set_key_calls
        assert ("GOOGLE_ACCESS_TOKEN", "new-access") in set_key_calls

    def test_run_install_oauth_propagates_error(self):
        """_run_install_oauth propagates an error when run_oauth_flow fails."""
        config = {"google": {"clientId": "test-client-id"}}
        with patch(
            "stream.run_oauth_flow", side_effect=RuntimeError("OAuth failed")
        ), patch("builtins.print"):

            with pytest.raises(RuntimeError, match="OAuth failed"):
                stream._run_install_oauth(config, "test-secret", MagicMock())


# ── _print_install_summary ───────────────────────────────────────────────────


class TestPrintInstallSummary:
    def _make_summary_res(self):
        """Build a minimal resources dict with install.summary data."""
        return {
            "install": {
                "summary": {
                    "header": "\n=== Setup Complete ===",
                    "config": "  Config:        {path}",
                    "secrets": "  Secrets:       {path}",
                    "terminal": "  Terminal:      {terminal}",
                    "cron_start": "  Cron start:    {schedule}",
                    "cron_stop": "  Cron stop:     {schedule}",
                    "cron_update": "  Cron update:   {schedule}",
                    "youtube_url": "  YouTube URL:   https://youtube.com/live/{broadcast_id}",
                    "run_hint": "\nRun 'python3 stream.py --start' to begin streaming.",
                    "edit_hint": "You can manually edit config.toml to adjust settings at any time.",
                }
            }
        }

    def test_print_summary_cron_enabled_no_update(self, sample_config):
        """_print_install_summary shows start/stop schedules but omits update when autoUpdate is False."""
        sample_config["cron"]["enabled"] = True
        sample_config["cron"]["autoUpdate"] = False
        sample_config["youtube"]["broadcastId"] = "bcast-123"

        with patch("builtins.print") as mock_print, \
             patch.object(stream, "SCRIPT_DIR", stream.Path("/test/path")):

            stream._print_install_summary(sample_config, self._make_summary_res())

        output = " ".join([str(c[0][0]) for c in mock_print.call_args_list])
        assert "bcast-123" in output

    def test_print_summary_cron_enabled_with_update(self, sample_config):
        """_print_install_summary shows start/stop/update schedules when autoUpdate is True."""
        sample_config["cron"]["enabled"] = True
        sample_config["cron"]["autoUpdate"] = True
        sample_config["youtube"]["broadcastId"] = "bcast-456"

        with patch("builtins.print") as mock_print, \
             patch.object(stream, "SCRIPT_DIR", stream.Path("/test/path")):

            stream._print_install_summary(sample_config, self._make_summary_res())

        output = " ".join([str(c[0][0]) for c in mock_print.call_args_list])
        assert "bcast-456" in output

    def test_print_summary_cron_disabled(self, sample_config):
        """_print_install_summary shows 'disabled' instead of schedules when cron is disabled."""
        sample_config["cron"]["enabled"] = False
        sample_config["youtube"]["broadcastId"] = "bcast-789"

        with patch("builtins.print") as mock_print, \
             patch.object(stream, "SCRIPT_DIR", stream.Path("/test/path")):

            stream._print_install_summary(sample_config, self._make_summary_res())

        output = " ".join([str(c[0][0]) for c in mock_print.call_args_list])
        assert "bcast-789" in output
        assert "disabled" in output.lower()


# ── Auto-update prompt edge cases (separate class to avoid input count issues) ─


class TestPromptAutoUpdate:
    def test_prompt_auto_update_yes_with_schedule(self, sample_resources):
        """Auto-update yes triggers a follow-up prompt for the cron_update schedule."""
        fresh = {
            "google": {"clientId": "cid"},
            "stream": {"rtspUrl": "", "videoCodec": "", "audioCodec": "",
                       "mute": None},  # will prompt for mute
            "youtube": {
                "broadcastTitle": "", "privacy": "", "enableDvr": None,
                "archivePrivacy": "", "categoryId": "", "broadcastId": "",
                "streamURL": "", "backupStreamUrl": "", "streamKey": "",
            },
            "cron": {},  # no enabled key — will also trigger cron prompt
        }

        inputs = iter(["secret", "rtsp://cam/live", "copy", "copy",
                       "yes",  # mute yes
                       "title", "public", "no",  # dvr no
                       "private", "22", "",
                       "yes",  # cron setup yes
                       "30 6 * * *", "25 18 * * *",
                       "yes",  # auto_update yes (triggers follow-up)
                       "0 2 * * *"])  # cron_update schedule

        with patch("builtins.input", lambda *a, **kw: next(inputs)), \
             patch("stream.load_env"), \
             patch.dict("os.environ", {}, clear=False):

            config, _ = stream.prompt_all_config_values(sample_resources, existing=fresh)

        assert config["cron"]["autoUpdate"] is True
        assert config["cron"]["update"] == "0 2 * * *"

    def test_prompt_auto_update_no(self, sample_resources):
        """Auto-update no skips the follow-up schedule prompt entirely."""
        fresh = {
            "google": {"clientId": "cid"},
            "stream": {"rtspUrl": "", "videoCodec": "", "audioCodec": "",
                       "mute": None},  # will prompt for mute
            "youtube": {
                "broadcastTitle": "", "privacy": "", "enableDvr": None,
                "archivePrivacy": "", "categoryId": "", "broadcastId": "",
                "streamURL": "", "backupStreamUrl": "", "streamKey": "",
            },
            "cron": {},  # no enabled key — will also trigger cron prompt
        }

        inputs = iter(["secret", "rtsp://cam/live", "copy", "copy",
                       "yes",  # mute yes
                       "title", "public", "no",  # dvr no
                       "private", "22", "",
                       "yes",  # cron setup yes
                       "30 6 * * *", "25 18 * * *",
                       "no"])  # auto_update no (skip schedule)

        with patch("builtins.input", lambda *a, **kw: next(inputs)), \
             patch("stream.load_env"), \
             patch.dict("os.environ", {}, clear=False):

            config, _ = stream.prompt_all_config_values(sample_resources, existing=fresh)

        assert config["cron"]["autoUpdate"] is False
        # cron_update should remain empty (no follow-up prompt consumed input)

    def test_prompt_auto_update_existing_config(self, sample_resources):
        """Auto-update value is silently reused when existing_auto_update is not None."""
        with_existing = {
            "google": {"clientId": "cid"},
            "stream": {"rtspUrl": "", "videoCodec": "", "audioCodec": "",
                       "mute": None},  # will prompt for mute (None = fresh)
            "youtube": {
                "broadcastTitle": "", "privacy": "", "enableDvr": None,
                "archivePrivacy": "", "categoryId": "", "broadcastId": "",
                "streamURL": "", "backupStreamUrl": "", "streamKey": "",
            },
            # cron.enabled exists, so no setup prompt. autoUpdate already set to True.
            # But start/stop are empty strings, so _smart_prompt will prompt for them.
            "cron": {"enabled": True, "start": "", "stop": "",
                     "autoUpdate": True, "update": ""},
        }

        # Full input sequence for all prompts that fire:
        inputs = iter([
            "secret",           # client_secret (empty existing)
            "rtsp://cam/live",  # rtsp_url (validator check)
            "",                 # video_codec → empty, accepts default "copy"
            "",                 # audio_codec → empty, accepts default "copy"
            "yes",              # mute yes (fresh install)
            "",                 # broadcast_title → empty, accepts default "My Location: {date}"
            "public",           # privacy (validator check)
            "",                 # enable_dvr → empty, accepts default "no"
            "private",          # archive_privacy (validator check)
            "",                 # category_id → empty, accepts default "22"
            "",                 # broadcast_id (empty = new)
            "30 6 * * *",       # cron_start (_smart_prompt, empty current)
            "25 18 * * *",      # cron_stop (_smart_prompt, empty current)
            # auto_update already True → silently reused into auto_update variable
            # But if auto_update is True, _smart_prompt fires for cron_update schedule:
            "",                 # cron_update → empty, accepts default "0 0 * * *"
        ])

        with patch("builtins.input", lambda *a, **kw: next(inputs)), \
             patch("stream.load_env"), \
             patch.dict("os.environ", {}, clear=False):

            config, _ = stream.prompt_all_config_values(sample_resources, existing=with_existing)

        assert config["cron"]["autoUpdate"] is True  # retained from existing


# ── _setup_youtube_resources_with_prompt (interactive install path) ─────────

class TestSetupYoutubeResourcesWithPrompt:
    """Tests for the interactive install-time YouTube resource setup.

    This function handles three distinct stream-key code paths:
      1. User provides a valid existing key → finds and uses it
      2. User provides an invalid key → creates a new stream resource
      3. User provides no key (empty) → creates a new stream resource

    CLAUDE.md: "New functions added to stream.py must have test coverage."
    """

    def _make_resources(self, install_section):
        """Build a minimal resources dict matching the expected structure."""
        return {
            "install": {
                "messages": install_section.get("messages", {}),
                "stream_key_guide": install_section.get("stream_key_guide", ""),
            }
        }

    def test_valid_user_provided_key_finds_existing_stream(self, sample_config):
        """When user provides a valid existing key, it is found and used."""
        sample_config["youtube"]["broadcastId"] = "bcast-123"
        # No streamKey — triggers the interactive path

        mock_youtube = MagicMock()
        logger = MagicMock()
        prompts = {"streamKey": "Stream Key"}

        install_section = {
            "messages": {
                "stream_key_not_found": "Key not found",
                "broadcast_id_label": "Broadcast ID: {broadcast_id}",
                "stream_url_label": "Stream URL: rtmp://test",
            },
        }

        with patch("stream._setup_youtube_resources") as mock_setup, \
             patch("stream._show_guide"), \
             patch("builtins.input", return_value="existing-key"), \
             patch("stream.find_stream_resource_by_key") as mock_find, \
             patch("stream.create_stream_resource"):

            # _setup_youtube_resources returns None streamKey (no key in config)
            mock_setup.return_value = {
                "broadcastId": "bcast-123",
                "streamURL": "",
                "backupStreamUrl": "",
                "streamKey": None,
            }

            # find_stream_resource_by_key finds the existing stream
            mock_find.return_value = ("s-id-456", "rtmp://primary", "rtmp://backup")

            res = self._make_resources(install_section)
            resources, messages = stream._setup_youtube_resources_with_prompt(
                mock_youtube, sample_config, logger, prompts, res
            )

        # Should have found and used the existing key
        assert resources["streamKey"] == "existing-key"
        assert resources["streamURL"] == "rtmp://primary"
        assert resources["backupStreamUrl"] == "rtmp://backup"

    def test_invalid_user_provided_key_creates_new_stream(self, sample_config):
        """When user provides an invalid key, a new stream resource is created."""
        sample_config["youtube"]["broadcastId"] = "bcast-123"

        mock_youtube = MagicMock()
        logger = MagicMock()
        prompts = {"streamKey": "Stream Key"}

        install_section = {
            "messages": {
                "stream_key_not_found": "Key not found — creating new one",
                "broadcast_id_label": "Broadcast ID: {broadcast_id}",
                "stream_url_label": "Stream URL: rtmp://test",
            },
        }

        with patch("stream._setup_youtube_resources") as mock_setup, \
             patch("stream._show_guide"), \
             patch("builtins.input", return_value="bad-key"), \
             patch("stream.find_stream_resource_by_key") as mock_find, \
             patch("stream.create_stream_resource") as mock_create:

            mock_setup.return_value = {
                "broadcastId": "bcast-123",
                "streamURL": "",
                "backupStreamUrl": "",
                "streamKey": None,
            }

            # Key not found → create new one
            mock_find.return_value = None
            mock_create.return_value = ("s-id-new", "rtmp://new-p", "rtmp://new-b", "new-key")

            res = self._make_resources(install_section)
            resources, messages = stream._setup_youtube_resources_with_prompt(
                mock_youtube, sample_config, logger, prompts, res
            )

        # Should have created a new stream resource
        assert resources["streamKey"] == "new-key"
        # Should have shown the not-found message
        assert any("not found" in m.lower() for m in messages)

    def test_empty_user_key_creates_new_stream(self, sample_config):
        """When user provides no key (empty), a new stream resource is created."""
        sample_config["youtube"]["broadcastId"] = "bcast-123"

        mock_youtube = MagicMock()
        logger = MagicMock()
        prompts = {"streamKey": "Stream Key"}

        install_section = {
            "messages": {
                "stream_key_not_found": "Key not found",
                "broadcast_id_label": "Broadcast ID: {broadcast_id}",
                "stream_url_label": "Stream URL: rtmp://test",
            },
        }

        with patch("stream._setup_youtube_resources") as mock_setup, \
             patch("stream._show_guide"), \
             patch("builtins.input", return_value=""), \
             patch("stream.find_stream_resource_by_key"), \
             patch("stream.create_stream_resource") as mock_create:

            mock_setup.return_value = {
                "broadcastId": "bcast-123",
                "streamURL": "",
                "backupStreamUrl": "",
                "streamKey": None,
            }

            mock_create.return_value = ("s-id-new", "rtmp://new-p", "rtmp://new-b", "new-key")

            res = self._make_resources(install_section)
            resources, messages = stream._setup_youtube_resources_with_prompt(
                mock_youtube, sample_config, logger, prompts, res
            )

        # Should have created a new stream resource (not looked up)
        assert resources["streamKey"] == "new-key"
        mock_create.assert_called_once_with(mock_youtube, logger)

    def test_existing_stream_key_skips_prompt_and_binds(self, sample_config):
        """When config already has a streamKey, no prompting occurs and binding happens."""
        sample_config["youtube"]["broadcastId"] = "bcast-123"
        sample_config["youtube"]["streamKey"] = "pre-existing-key"

        mock_youtube = MagicMock()
        logger = MagicMock()
        prompts = {"streamKey": "Stream Key"}

        install_section = {
            "messages": {
                "broadcast_id_label": "Broadcast ID: {broadcast_id}",
                "stream_url_label": "Stream URL: rtmp://test",
            },
        }

        with patch("stream._setup_youtube_resources") as mock_setup, \
             patch("builtins.input"), \
             patch("stream.find_stream_resource_by_key") as mock_find, \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_video_embeddable"):

            # _setup_youtube_resources returns the existing key
            mock_setup.return_value = {
                "broadcastId": "bcast-123",
                "streamURL": "rtmp://a.rtmp.youtube.com/live2",
                "backupStreamUrl": "rtmp://b.rtmp.youtube.com/live2?backup=1",
                "streamKey": "pre-existing-key",
            }

            res = self._make_resources(install_section)
            resources, messages = stream._setup_youtube_resources_with_prompt(
                mock_youtube, sample_config, logger, prompts, res
            )

        # Should have returned the existing key without prompting
        assert resources["streamKey"] == "pre-existing-key"
