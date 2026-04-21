"""Tests for install orchestration: _setup_youtube_resources and prompt_all_config_values."""

from unittest.mock import patch, MagicMock, ANY

import pytest

import stream


# ── _setup_youtube_resources ────────────────────────────────────────────────


class TestSetupYoutubeResources:
    def test_creates_stream_via_api_when_streamkey_missing(
        self, sample_config, sample_resources
    ):
        """When streamKey is empty, install calls create_stream_resource and populates URL and key fields."""
        sample_config["youtube"]["broadcastId"] = "existing-bcast"
        sample_config["youtube"]["streamKey"] = ""

        with patch("stream.build_youtube_service"), \
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

    def test_skips_stream_creation_when_streamkey_present(
        self, sample_config, sample_resources
    ):
        """If streamKey already exists in config, create_stream_resource is not called."""
        sample_config["youtube"]["broadcastId"] = "existing-bcast"
        sample_config["youtube"]["streamKey"] = "existing-key"

        with patch("stream.build_youtube_service"), \
             patch("stream.create_stream_resource") as mock_create, \
             patch("stream.find_stream_by_key", return_value="s-id"), \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"):
            stream._setup_youtube_resources(sample_config, MagicMock(), sample_resources)

        mock_create.assert_not_called()

    def test_binds_stream_to_broadcast(self, sample_config, sample_resources):
        """After stream creation, bind_stream_to_broadcast is called with the new IDs."""
        sample_config["youtube"]["broadcastId"] = "bcast-A"
        sample_config["youtube"]["streamKey"] = ""

        with patch("stream.build_youtube_service"), \
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
             patch("stream.find_stream_by_key", return_value="s-id"), \
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
        # Only client_secret is prompted (env is cleared). If any extra prompt
        # for streamKey/streamURL/backupStreamUrl appears, StopIteration fires.
        inputs = iter(["test-secret", "yes"])
        with patch("builtins.input", lambda *a, **kw: next(inputs)), \
             patch("stream.load_env"), \
             patch.dict("os.environ", {}, clear=False):
            config, secret = stream.prompt_all_config_values(sample_resources, existing=existing)

        # The three fields are carried through from existing, not prompted.
        assert config["youtube"]["streamURL"] == ""
        assert config["youtube"]["backupStreamUrl"] == ""
        assert config["youtube"]["streamKey"] == ""
        assert secret == "test-secret"
