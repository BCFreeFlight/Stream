"""Tests for install orchestration: _setup_youtube_resources and prompt_all_config_values."""

from unittest.mock import patch, MagicMock, ANY

import pytest

import stream


# ── _setup_youtube_resources ────────────────────────────────────────────────


class TestSetupYoutubeResources:
    def test_blank_input_creates_new_stream_resource(
        self, sample_config, sample_resources
    ):
        """Pressing Enter (blank) at the stream key prompt creates a new stream resource."""
        sample_config["youtube"]["broadcastId"] = "existing-bcast"
        sample_config["youtube"]["streamKey"] = ""

        with patch("stream.build_youtube_service"), \
             patch("builtins.input", return_value=""), \
             patch(
                 "stream.create_stream_resource",
                 return_value=("new-stream-id", "rtmp://primary", "rtmp://backup", "new-key"),
             ) as mock_create, \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"):
            stream._setup_youtube_resources(sample_config, MagicMock(), sample_resources)

        mock_create.assert_called_once()
        assert sample_config["youtube"]["streamURL"] == "rtmp://primary"
        assert sample_config["youtube"]["backupStreamUrl"] == "rtmp://backup"
        assert sample_config["youtube"]["streamKey"] == "new-key"

    def test_valid_existing_key_skips_create(self, sample_config, sample_resources):
        """Entering a valid stream key uses the existing resource and skips create_stream_resource."""
        sample_config["youtube"]["broadcastId"] = "existing-bcast"
        sample_config["youtube"]["streamKey"] = ""

        with patch("stream.build_youtube_service"), \
             patch("builtins.input", return_value="user-key"), \
             patch(
                 "stream.find_stream_resource_by_key",
                 return_value=("s-id", "rtmp://primary", "rtmp://backup"),
             ), \
             patch("stream.create_stream_resource") as mock_create, \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"):
            stream._setup_youtube_resources(sample_config, MagicMock(), sample_resources)

        mock_create.assert_not_called()
        assert sample_config["youtube"]["streamKey"] == "user-key"
        assert sample_config["youtube"]["streamURL"] == "rtmp://primary"
        assert sample_config["youtube"]["backupStreamUrl"] == "rtmp://backup"

    def test_invalid_key_falls_back_to_create(self, sample_config, sample_resources, capsys):
        """A key not found in the user's YouTube account falls back to creating a new resource."""
        sample_config["youtube"]["broadcastId"] = "existing-bcast"
        sample_config["youtube"]["streamKey"] = ""

        with patch("stream.build_youtube_service"), \
             patch("builtins.input", return_value="bad-key"), \
             patch("stream.find_stream_resource_by_key", return_value=None), \
             patch(
                 "stream.create_stream_resource",
                 return_value=("new-id", "rtmp://p", "rtmp://b", "new-key"),
             ) as mock_create, \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"):
            stream._setup_youtube_resources(sample_config, MagicMock(), sample_resources)

        mock_create.assert_called_once()
        assert "not found" in capsys.readouterr().out.lower() or mock_create.called

    def test_skips_stream_creation_when_streamkey_present(
        self, sample_config, sample_resources
    ):
        """If streamKey already exists in config, no prompt is shown and create is not called."""
        sample_config["youtube"]["broadcastId"] = "existing-bcast"
        sample_config["youtube"]["streamKey"] = "existing-key"

        with patch("stream.build_youtube_service"), \
             patch("stream.create_stream_resource") as mock_create, \
             patch(
                 "stream.find_stream_resource_by_key",
                 return_value=("s-id", "rtmp://p", "rtmp://b"),
             ), \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"), \
             patch("builtins.input") as mock_input:
            stream._setup_youtube_resources(sample_config, MagicMock(), sample_resources)

        mock_create.assert_not_called()
        mock_input.assert_not_called()

    def test_binds_stream_to_broadcast(self, sample_config, sample_resources):
        """After stream creation, bind_stream_to_broadcast is called with the new IDs."""
        sample_config["youtube"]["broadcastId"] = "bcast-A"
        sample_config["youtube"]["streamKey"] = ""

        with patch("stream.build_youtube_service"), \
             patch("builtins.input", return_value=""), \
             patch(
                 "stream.create_stream_resource",
                 return_value=("stream-A", "rtmp://p", "rtmp://b", "key-A"),
             ), \
             patch("stream.bind_stream_to_broadcast") as mock_bind, \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"):
            stream._setup_youtube_resources(sample_config, MagicMock(), sample_resources)

        mock_bind.assert_called_once()
        args = mock_bind.call_args.args
        assert "bcast-A" in args
        assert "stream-A" in args

    def test_api_failure_propagates(self, sample_config, sample_resources):
        """If create_stream_resource raises, the error is not silently swallowed."""
        sample_config["youtube"]["broadcastId"] = "bcast"
        sample_config["youtube"]["streamKey"] = ""

        with patch("stream.build_youtube_service"), \
             patch("builtins.input", return_value=""), \
             patch(
                 "stream.create_stream_resource",
                 side_effect=RuntimeError("API down"),
             ), \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"):
            with pytest.raises(RuntimeError, match="API down"):
                stream._setup_youtube_resources(sample_config, MagicMock(), sample_resources)

    def test_apply_video_embeddable_called_on_install(self, sample_config, sample_resources):
        """_setup_youtube_resources calls apply_video_embeddable with the broadcast ID and embeddable flag."""
        sample_config["youtube"]["broadcastId"] = "bcast-embed"
        sample_config["youtube"]["streamKey"] = "sk"
        sample_config["youtube"]["embeddable"] = True

        mock_yt_service = MagicMock()
        with patch("stream.build_youtube_service", return_value=mock_yt_service), \
             patch(
                 "stream.find_stream_resource_by_key",
                 return_value=("s-id", "rtmp://p", "rtmp://b"),
             ), \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable") as mock_embed:
            stream._setup_youtube_resources(sample_config, MagicMock(), sample_resources)

        mock_embed.assert_called_once_with(mock_yt_service, "bcast-embed", True, ANY)


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
