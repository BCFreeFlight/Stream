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

        mock_youtube = MagicMock()
        with patch("builtins.input", return_value=""), \
             patch(
                 "stream.create_stream_resource",
                 return_value=("new-stream-id", "rtmp://primary", "rtmp://backup", "new-key"),
             ) as mock_create, \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"):
            result = stream._setup_youtube_resources(
                mock_youtube, sample_config, MagicMock()
            )

        assert result["broadcastId"] == "existing-bcast"
        assert result["streamURL"] == "rtmp://primary"
        assert result["backupStreamUrl"] == "rtmp://backup"
        assert result["streamKey"] == "new-key"

    def test_valid_existing_key_skips_create(self, sample_config, sample_resources):
        """Entering a valid stream key uses the existing resource and skips create_stream_resource."""
        sample_config["youtube"]["broadcastId"] = "existing-bcast"
        sample_config["youtube"]["streamKey"] = ""

        mock_youtube = MagicMock()
        with patch("builtins.input", return_value="user-key"), \
             patch(
                 "stream.find_stream_resource_by_key",
                 return_value=("s-id", "rtmp://primary", "rtmp://backup"),
             ), \
             patch("stream.create_stream_resource") as mock_create, \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"):
            result = stream._setup_youtube_resources(
                mock_youtube, sample_config, MagicMock()
            )

        mock_create.assert_not_called()
        assert result["streamKey"] == "user-key"
        assert result["streamURL"] == "rtmp://primary"
        assert result["backupStreamUrl"] == "rtmp://backup"

    def test_invalid_key_falls_back_to_create(self, sample_config, sample_resources):
        """A key not found in the user's YouTube account falls back to creating a new resource."""
        sample_config["youtube"]["broadcastId"] = "existing-bcast"
        sample_config["youtube"]["streamKey"] = ""

        mock_youtube = MagicMock()
        with patch("builtins.input", return_value="bad-key"), \
             patch("stream.find_stream_resource_by_key", return_value=None), \
             patch(
                 "stream.create_stream_resource",
                 return_value=("new-id", "rtmp://p", "rtmp://b", "new-key"),
             ) as mock_create, \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"):
            result = stream._setup_youtube_resources(
                mock_youtube, sample_config, MagicMock()
            )

        assert result["streamKey"] == "new-key"

    def test_skips_stream_creation_when_streamkey_present(
        self, sample_config, sample_resources
    ):
        """If streamKey already exists in config, no prompt is shown and create is not called."""
        sample_config["youtube"]["broadcastId"] = "existing-bcast"
        sample_config["youtube"]["streamKey"] = "existing-key"

        mock_youtube = MagicMock()
        with patch("stream.create_stream_resource") as mock_create, \
             patch(
                 "stream.find_stream_resource_by_key",
                 return_value=("s-id", "rtmp://p", "rtmp://b"),
             ), \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"):
            result = stream._setup_youtube_resources(
                mock_youtube, sample_config, MagicMock()
            )

        assert result["streamKey"] == "existing-key"

    def test_binds_stream_to_broadcast(self, sample_config, sample_resources):
        """After stream creation, bind_stream_to_broadcast is called with the new IDs."""
        sample_config["youtube"]["broadcastId"] = "bcast-A"
        sample_config["youtube"]["streamKey"] = ""

        mock_youtube = MagicMock()
        with patch("builtins.input", return_value=""), \
             patch(
                 "stream.create_stream_resource",
                 return_value=("stream-A", "rtmp://p", "rtmp://b", "key-A"),
             ), \
             patch("stream.bind_stream_to_broadcast") as mock_bind, \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"):
            stream._setup_youtube_resources(
                mock_youtube, sample_config, MagicMock()
            )

        mock_bind.assert_called_once()
        args = mock_bind.call_args.args
        assert "bcast-A" in args
        assert "stream-A" in args

    def test_api_failure_propagates(self, sample_config):
        """If create_stream_resource raises, the error is not silently swallowed."""
        sample_config["youtube"]["broadcastId"] = "bcast"
        sample_config["youtube"]["streamKey"] = ""

        mock_youtube = MagicMock()
        with patch("builtins.input", return_value=""), \
             patch(
                 "stream.create_stream_resource",
                 side_effect=RuntimeError("API down"),
             ), \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"):
            with pytest.raises(RuntimeError, match="API down"):
                stream._setup_youtube_resources(
                    mock_youtube, sample_config, MagicMock()
                )

    def test_apply_video_embeddable_called_on_install(self, sample_config):
        """_setup_youtube_resources calls apply_video_embeddable with the broadcast ID and embeddable flag."""
        sample_config["youtube"]["broadcastId"] = "bcast-embed"
        sample_config["youtube"]["streamKey"] = "sk"
        sample_config["youtube"]["embeddable"] = True

        mock_yt_service = MagicMock()
        with patch(
            "stream.find_stream_resource_by_key",
            return_value=("s-id", "rtmp://p", "rtmp://b"),
        ), \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable") as mock_embed:
            stream._setup_youtube_resources(
                mock_yt_service, sample_config, MagicMock()
            )

        mock_embed.assert_called_once_with(mock_yt_service, "bcast-embed", True, ANY)

    def test_returns_required_keys(self):
        """Returned dict has all required keys: broadcastId, streamURL, backupStreamUrl, streamKey."""
        sample_config = {
            "youtube": {"broadcastId": "bcast-123", "streamKey": "sk"},
        }

        mock_youtube = MagicMock()
        with patch(
            "stream.find_stream_resource_by_key",
            return_value=("s-id", "rtmp://p", "rtmp://b"),
        ), \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"):
            result = stream._setup_youtube_resources(
                mock_youtube, sample_config, MagicMock()
            )

        assert set(result.keys()) == {"broadcastId", "streamURL", "backupStreamUrl", "streamKey"}

    def test_does_not_mutate_existing_config(self):
        """existing_config is not mutated — values remain unchanged."""
        original_bid = "original-bcast"
        sample_config = {
            "youtube": {"broadcastId": original_bid, "streamKey": "sk"},
        }

        mock_youtube = MagicMock()
        with patch(
            "stream.find_stream_resource_by_key",
            return_value=("s-id", "rtmp://p", "rtmp://b"),
        ), \
             patch("stream.bind_stream_to_broadcast"), \
             patch("stream.apply_broadcast_category"), \
             patch("stream.apply_video_embeddable"):
            stream._setup_youtube_resources(
                mock_youtube, sample_config, MagicMock()
            )

        assert sample_config["youtube"]["broadcastId"] == original_bid


# ── prompt_all_config_values ────────────────────────────────────────────────
