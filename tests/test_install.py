"""Tests for install orchestration: _setup_youtube_resources and prompt_all_config_values."""

from unittest.mock import patch, MagicMock

import pytest

import stream


# ── _setup_youtube_resources ────────────────────────────────────────────────


class TestSetupYoutubeResources:
    def test_creates_stream_via_api_when_streamid_missing(
        self, sample_config, sample_resources
    ):
        """When streamId is empty, install calls create_stream_resource and populates all four fields."""
        sample_config["youtube"]["broadcastId"] = "existing-bcast"
        sample_config["youtube"]["streamId"] = ""

        with patch("stream.build_youtube_service"), \
             patch(
                 "stream.create_stream_resource",
                 return_value=("new-stream-id", "rtmp://primary", "rtmp://backup", "new-key"),
             ) as mock_create, \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.find_stream_by_key") as mock_find:
            stream._setup_youtube_resources(sample_config, MagicMock(), sample_resources)

        mock_create.assert_called_once()
        mock_find.assert_not_called()
        assert sample_config["youtube"]["streamId"] == "new-stream-id"
        assert sample_config["youtube"]["streamURL"] == "rtmp://primary"
        assert sample_config["youtube"]["backupStreamUrl"] == "rtmp://backup"
        assert sample_config["youtube"]["streamKey"] == "new-key"

    def test_skips_stream_creation_when_streamid_present(
        self, sample_config, sample_resources
    ):
        """If streamId already exists in config, the API is not re-invoked for a fresh stream."""
        sample_config["youtube"]["broadcastId"] = "existing-bcast"
        sample_config["youtube"]["streamId"] = "already-have-id"

        with patch("stream.build_youtube_service"), \
             patch("stream.create_stream_resource") as mock_create, \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"):
            stream._setup_youtube_resources(sample_config, MagicMock(), sample_resources)

        mock_create.assert_not_called()
        assert sample_config["youtube"]["streamId"] == "already-have-id"

    def test_binds_stream_to_broadcast(self, sample_config, sample_resources):
        """After stream creation, bind_stream_to_broadcast is called with the resulting IDs."""
        sample_config["youtube"]["broadcastId"] = "bcast-A"
        sample_config["youtube"]["streamId"] = ""

        with patch("stream.build_youtube_service"), \
             patch(
                 "stream.create_stream_resource",
                 return_value=("stream-A", "rtmp://p", "rtmp://b", "key-A"),
             ), \
             patch("stream.bind_stream_to_broadcast") as mock_bind, \
             patch("stream.apply_broadcast_category"):
            stream._setup_youtube_resources(sample_config, MagicMock(), sample_resources)

        mock_bind.assert_called_once()
        args = mock_bind.call_args.args
        assert "bcast-A" in args
        assert "stream-A" in args

    def test_api_failure_propagates(self, sample_config, sample_resources):
        """If create_stream_resource raises, the error is not silently swallowed."""
        sample_config["youtube"]["broadcastId"] = "bcast"
        sample_config["youtube"]["streamId"] = ""

        with patch("stream.build_youtube_service"), \
             patch(
                 "stream.create_stream_resource",
                 side_effect=RuntimeError("API down"),
             ), \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"):
            with pytest.raises(RuntimeError, match="API down"):
                stream._setup_youtube_resources(sample_config, MagicMock(), sample_resources)

        # streamId must stay empty rather than being written as ""
        assert sample_config["youtube"]["streamId"] == ""


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
            "cron": {"enabled": True, "start": "30 6 * * *", "stop": "25 18 * * *"},
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
