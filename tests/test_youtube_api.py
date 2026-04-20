"""Tests for YouTube API low-level wrappers and high-level orchestration."""

import datetime

import pytest
from unittest.mock import MagicMock, patch

import stream


# ── Low-Level API Wrappers ──────────────────────────────────────────────────


class TestLowLevelAPI:
    """Tests for _api_* functions that make exactly one YouTube API call."""

    # -- _api_insert_broadcast -----------------------------------------------

    def test_api_insert_broadcast_calls_execute(self, mock_youtube):
        """insert_broadcast chains liveBroadcasts().insert().execute()."""
        stream._api_insert_broadcast(mock_youtube, "title", "public", False)
        mock_youtube.liveBroadcasts().insert.assert_called_once()
        mock_youtube.liveBroadcasts().insert().execute.assert_called_once()

    def test_api_insert_broadcast_body_structure(self, mock_youtube):
        """The body kwarg contains the expected snippet, status, and contentDetails."""
        stream._api_insert_broadcast(mock_youtube, "My Title", "unlisted", False)
        _, kwargs = mock_youtube.liveBroadcasts().insert.call_args
        body = kwargs["body"]

        assert body["snippet"]["title"] == "My Title"
        assert body["status"]["privacyStatus"] == "unlisted"
        assert body["contentDetails"]["enableAutoStart"] is False
        assert body["contentDetails"]["enableAutoStop"] is False

    # -- _api_insert_stream --------------------------------------------------

    def test_api_insert_stream_calls_execute(self, mock_youtube):
        """insert_stream chains liveStreams().insert().execute()."""
        stream._api_insert_stream(mock_youtube)
        mock_youtube.liveStreams().insert.assert_called_once()
        mock_youtube.liveStreams().insert().execute.assert_called_once()

    # -- _api_bind_broadcast -------------------------------------------------

    def test_api_bind_broadcast_params(self, mock_youtube):
        """bind passes the correct broadcast ID and stream ID."""
        stream._api_bind_broadcast(mock_youtube, "bid", "sid")
        _, kwargs = mock_youtube.liveBroadcasts().bind.call_args
        assert kwargs["id"] == "bid"
        assert kwargs["streamId"] == "sid"

    # -- _api_transition_broadcast -------------------------------------------

    def test_api_transition_broadcast_params(self, mock_youtube):
        """transition passes the correct broadcastStatus and broadcast ID."""
        stream._api_transition_broadcast(mock_youtube, "bid", "live")
        _, kwargs = mock_youtube.liveBroadcasts().transition.call_args
        assert kwargs["broadcastStatus"] == "live"
        assert kwargs["id"] == "bid"

    # -- _api_get_stream_status ----------------------------------------------

    def test_api_get_stream_status_with_items(self, mock_youtube):
        """Returns the streamStatus string when items are present."""
        mock_youtube.liveStreams().list().execute.return_value = {
            "items": [{"status": {"streamStatus": "active"}}]
        }
        result = stream._api_get_stream_status(mock_youtube, "sid")
        assert result == "active"

    def test_api_get_stream_status_empty(self, mock_youtube):
        """Returns None when items list is empty."""
        mock_youtube.liveStreams().list().execute.return_value = {"items": []}
        result = stream._api_get_stream_status(mock_youtube, "sid")
        assert result is None

    # -- _api_get_broadcast_lifecycle ----------------------------------------

    def test_api_get_broadcast_lifecycle_with_items(self, mock_youtube):
        """Returns the lifeCycleStatus when items are present."""
        mock_youtube.liveBroadcasts().list().execute.return_value = {
            "items": [{"status": {"lifeCycleStatus": "live"}}]
        }
        result = stream._api_get_broadcast_lifecycle(mock_youtube, "bid")
        assert result == "live"

    def test_api_get_broadcast_lifecycle_empty(self, mock_youtube):
        """Returns None when items list is empty."""
        mock_youtube.liveBroadcasts().list().execute.return_value = {"items": []}
        result = stream._api_get_broadcast_lifecycle(mock_youtube, "bid")
        assert result is None

    # -- _api_list_my_streams ------------------------------------------------

    def test_api_list_my_streams_returns_items(self, mock_youtube):
        """Returns the items list from the API response."""
        mock_youtube.liveStreams().list().execute.return_value = {
            "items": [{"id": "s1"}]
        }
        result = stream._api_list_my_streams(mock_youtube)
        assert result == [{"id": "s1"}]

    def test_api_list_my_streams_empty(self, mock_youtube):
        """Returns an empty list when no items are present."""
        mock_youtube.liveStreams().list().execute.return_value = {"items": []}
        result = stream._api_list_my_streams(mock_youtube)
        assert result == []

    # -- _api_list_my_broadcasts -----------------------------------------------

    def test_api_list_my_broadcasts_returns_items(self, mock_youtube):
        """Returns the items list from the broadcasts response."""
        mock_youtube.liveBroadcasts().list().execute.return_value = {
            "items": [{"id": "b1", "status": {"lifeCycleStatus": "live"}}]
        }
        result = stream._api_list_my_broadcasts(mock_youtube)
        assert result == [{"id": "b1", "status": {"lifeCycleStatus": "live"}}]

    def test_api_list_my_broadcasts_empty(self, mock_youtube):
        """Returns an empty list when no broadcasts are present."""
        mock_youtube.liveBroadcasts().list().execute.return_value = {"items": []}
        result = stream._api_list_my_broadcasts(mock_youtube)
        assert result == []

    # -- _api_get_video_snippet ----------------------------------------------

    def test_api_get_video_snippet_found(self, mock_youtube):
        """Returns the snippet dict when the video is found."""
        mock_youtube.videos().list().execute.return_value = {
            "items": [{"snippet": {"title": "T"}}]
        }
        result = stream._api_get_video_snippet(mock_youtube, "vid")
        assert result == {"title": "T"}

    def test_api_get_video_snippet_not_found(self, mock_youtube):
        """Returns None when no items are returned."""
        mock_youtube.videos().list().execute.return_value = {"items": []}
        result = stream._api_get_video_snippet(mock_youtube, "vid")
        assert result is None


# ── High-Level Orchestration ────────────────────────────────────────────────


class TestHighLevelOrchestration:
    """Tests for functions that compose the low-level API wrappers."""

    # -- interpolate_broadcast_title -----------------------------------------

    def test_interpolate_title_with_date(self, sample_config):
        """The {date} token is replaced with today's ISO date."""
        sample_config["youtube"]["broadcastTitle"] = "Test: {date}"
        result = stream.interpolate_broadcast_title(sample_config)
        assert result == f"Test: {datetime.date.today().isoformat()}"

    def test_interpolate_title_no_token(self, sample_config):
        """A title without {date} is returned unchanged."""
        sample_config["youtube"]["broadcastTitle"] = "Static"
        result = stream.interpolate_broadcast_title(sample_config)
        assert result == "Static"

    # -- create_broadcast ----------------------------------------------------

    @patch("stream._api_insert_broadcast")
    def test_create_broadcast_returns_id(self, mock_insert, sample_config, mock_logger):
        """create_broadcast returns the broadcast ID from the API response."""
        mock_insert.return_value = {"id": "bcast-1"}
        result = stream.create_broadcast(MagicMock(), sample_config, mock_logger)
        assert result == "bcast-1"

    # -- create_stream_resource ----------------------------------------------

    @patch("stream._api_insert_stream")
    def test_create_stream_resource_returns_tuple(self, mock_insert, mock_logger):
        """Returns (stream_id, rtmp_url, backup_url, stream_key)."""
        mock_insert.return_value = {
            "id": "s1",
            "cdn": {
                "ingestionInfo": {
                    "ingestionAddress": "rtmp://url",
                    "backupIngestionAddress": "rtmp://backup",
                    "streamName": "key1",
                }
            },
        }
        result = stream.create_stream_resource(MagicMock(), mock_logger)
        assert result == ("s1", "rtmp://url", "rtmp://backup", "key1")

    @patch("stream._api_insert_stream")
    def test_create_stream_resource_no_backup(self, mock_insert, mock_logger):
        """Returns empty string for backup when backupIngestionAddress is absent."""
        mock_insert.return_value = {
            "id": "s1",
            "cdn": {
                "ingestionInfo": {
                    "ingestionAddress": "rtmp://url",
                    "streamName": "key1",
                }
            },
        }
        result = stream.create_stream_resource(MagicMock(), mock_logger)
        assert result == ("s1", "rtmp://url", "", "key1")

    # -- bind_stream_to_broadcast --------------------------------------------

    @patch("stream._api_bind_broadcast")
    def test_bind_stream_calls_api(self, mock_bind, mock_logger):
        """bind_stream_to_broadcast delegates to _api_bind_broadcast."""
        yt = MagicMock()
        stream.bind_stream_to_broadcast(yt, "bid", "sid", mock_logger)
        mock_bind.assert_called_once_with(yt, "bid", "sid")

    # -- apply_broadcast_category --------------------------------------------

    @patch("stream._api_update_video_snippet")
    @patch("stream._api_get_video_snippet")
    def test_apply_category_success(self, mock_get, mock_update, mock_logger):
        """Sets categoryId on the snippet and calls update."""
        mock_get.return_value = {"categoryId": "1"}
        yt = MagicMock()
        stream.apply_broadcast_category(yt, "bid", "22", mock_logger)
        mock_update.assert_called_once()
        _, kwargs = mock_update.call_args
        # positional args: youtube, video_id, snippet
        args = mock_update.call_args[0]
        assert args[2]["categoryId"] == "22"

    @patch("stream._api_get_video_snippet")
    def test_apply_category_no_snippet(self, mock_get, mock_logger):
        """No error when snippet is None."""
        mock_get.return_value = None
        stream.apply_broadcast_category(MagicMock(), "bid", "22", mock_logger)
        # Should simply return without error

    @patch("stream._api_get_video_snippet")
    def test_apply_category_http_error(self, mock_get, mock_logger):
        """HttpError is caught and logged as a warning, no exception raised."""
        from googleapiclient.errors import HttpError

        mock_get.side_effect = HttpError(
            resp=MagicMock(status=400), content=b"error"
        )
        stream.apply_broadcast_category(MagicMock(), "bid", "22", mock_logger)
        mock_logger.warn.assert_called_once()

    # -- find_stream_by_key --------------------------------------------------

    @patch("stream._api_list_my_streams")
    def test_find_stream_by_key_found(self, mock_list, mock_logger):
        """Returns the stream ID when a matching streamName is found."""
        mock_list.return_value = [
            {"id": "s1", "cdn": {"ingestionInfo": {"streamName": "key1"}}}
        ]
        result = stream.find_stream_by_key(MagicMock(), "key1", mock_logger)
        assert result == "s1"

    @patch("stream._api_list_my_streams")
    def test_find_stream_by_key_not_found(self, mock_list, mock_logger):
        """Returns None when no stream matches the key."""
        mock_list.return_value = [
            {"id": "s1", "cdn": {"ingestionInfo": {"streamName": "other"}}}
        ]
        result = stream.find_stream_by_key(MagicMock(), "key1", mock_logger)
        assert result is None

    # -- wait_for_stream_active ----------------------------------------------

    @patch("time.sleep")
    @patch("stream._api_get_stream_status")
    def test_wait_for_stream_active_immediate(
        self, mock_status, mock_sleep, mock_logger
    ):
        """Returns True when the stream is active on the first poll."""
        mock_status.return_value = "active"
        result = stream.wait_for_stream_active(MagicMock(), "sid", mock_logger)
        assert result is True

    @patch("time.sleep")
    @patch("stream._api_get_stream_status")
    def test_wait_for_stream_active_stop_requested(
        self, mock_status, mock_sleep, mock_logger
    ):
        """Returns False when _stop_requested is set."""
        mock_status.return_value = "inactive"
        stream._stop_requested = True
        result = stream.wait_for_stream_active(MagicMock(), "sid", mock_logger)
        assert result is False

    # -- transition_to_live --------------------------------------------------

    @patch("time.sleep")
    @patch("stream._api_transition_broadcast")
    @patch("stream._attempt_testing_transition")
    def test_transition_to_live_calls_testing_then_live(
        self, mock_testing, mock_transition, mock_sleep, mock_logger
    ):
        """Calls _attempt_testing_transition then transitions to live."""
        yt = MagicMock()
        stream.transition_to_live(yt, "bid", mock_logger)
        mock_testing.assert_called_once_with(yt, "bid", mock_logger)
        mock_transition.assert_called_once_with(yt, "bid", "live")

    # -- ensure_broadcast_live -----------------------------------------------

    @patch("stream._api_get_broadcast_lifecycle")
    def test_ensure_broadcast_live_already_live(self, mock_lifecycle, mock_logger, sample_config):
        """No transition when the broadcast is already live."""
        mock_lifecycle.return_value = "live"
        with patch("stream.transition_to_live") as mock_trans:
            stream.ensure_broadcast_live(MagicMock(), "bid", sample_config, mock_logger)
            mock_trans.assert_not_called()

    @patch("stream.transition_to_live")
    @patch("stream._api_get_broadcast_lifecycle")
    def test_ensure_broadcast_live_ready(self, mock_lifecycle, mock_trans, mock_logger, sample_config):
        """Calls transition_to_live when status is 'ready'."""
        mock_lifecycle.return_value = "ready"
        stream.ensure_broadcast_live(MagicMock(), "bid", sample_config, mock_logger)
        mock_trans.assert_called_once()

    @patch("stream._api_transition_broadcast")
    @patch("stream._api_get_broadcast_lifecycle")
    def test_ensure_broadcast_live_testing(
        self, mock_lifecycle, mock_transition, mock_logger, sample_config
    ):
        """Transitions directly to live when status is 'testing'."""
        mock_lifecycle.return_value = "testing"
        yt = MagicMock()
        stream.ensure_broadcast_live(yt, "bid", sample_config, mock_logger)
        mock_transition.assert_called_once_with(yt, "bid", "live")

    @patch("stream.transition_to_live")
    @patch("stream._create_fresh_broadcast", return_value="new-bid")
    @patch("stream._api_get_broadcast_lifecycle")
    def test_ensure_broadcast_live_complete_creates_new(
        self, mock_lifecycle, mock_create, mock_trans, mock_logger, sample_config
    ):
        """Creates a new broadcast and transitions to live when status is 'complete'."""
        mock_lifecycle.return_value = "complete"
        yt = MagicMock()
        stream.ensure_broadcast_live(yt, "bid", sample_config, mock_logger)
        mock_create.assert_called_once_with(yt, sample_config, mock_logger)
        mock_trans.assert_called_once_with(yt, "new-bid", mock_logger)

    @patch("stream._api_get_broadcast_lifecycle")
    def test_ensure_broadcast_live_unknown_raises(self, mock_lifecycle, mock_logger, sample_config):
        """Raises RuntimeError for an unexpected lifecycle status."""
        mock_lifecycle.return_value = "revoked"
        with pytest.raises(RuntimeError):
            stream.ensure_broadcast_live(MagicMock(), "bid", sample_config, mock_logger)

    # -- cleanup_orphaned_broadcasts -----------------------------------------

    @patch("stream._api_transition_broadcast")
    @patch("stream._api_list_my_broadcasts")
    def test_cleanup_orphaned_broadcasts_completes_orphans(
        self, mock_list, mock_trans, mock_logger
    ):
        """Orphaned live broadcasts are transitioned to complete."""
        mock_list.return_value = [
            {"id": "orphan-1", "status": {"lifeCycleStatus": "live"}},
            {"id": "current", "status": {"lifeCycleStatus": "live"}},
        ]
        yt = MagicMock()
        stream.cleanup_orphaned_broadcasts(yt, "current", mock_logger)
        mock_trans.assert_called_once_with(yt, "orphan-1", "complete")
        mock_list.assert_called_once_with(yt)

    @patch("stream._api_transition_broadcast")
    @patch("stream._api_list_my_broadcasts")
    def test_cleanup_orphaned_broadcasts_filters_lifecycles_client_side(
        self, mock_list, mock_trans, mock_logger
    ):
        """Only live/ready/testing/created lifecycles are transitioned."""
        mock_list.return_value = [
            {"id": "live-one", "status": {"lifeCycleStatus": "live"}},
            {"id": "ready-one", "status": {"lifeCycleStatus": "ready"}},
            {"id": "testing-one", "status": {"lifeCycleStatus": "testing"}},
            {"id": "created-one", "status": {"lifeCycleStatus": "created"}},
            {"id": "complete-one", "status": {"lifeCycleStatus": "complete"}},
            {"id": "revoked-one", "status": {"lifeCycleStatus": "revoked"}},
        ]
        yt = MagicMock()
        stream.cleanup_orphaned_broadcasts(yt, "current", mock_logger)
        transitioned = {call.args[1] for call in mock_trans.call_args_list}
        assert transitioned == {"live-one", "ready-one", "testing-one", "created-one"}

    @patch("stream._api_transition_broadcast")
    @patch("stream._api_list_my_broadcasts")
    def test_cleanup_orphaned_broadcasts_skips_current(
        self, mock_list, mock_trans, mock_logger
    ):
        """The current broadcast is never completed."""
        mock_list.return_value = [
            {"id": "current", "status": {"lifeCycleStatus": "live"}},
        ]
        stream.cleanup_orphaned_broadcasts(MagicMock(), "current", mock_logger)
        mock_trans.assert_not_called()

    @patch("stream._api_transition_broadcast")
    @patch("stream._api_list_my_broadcasts")
    def test_cleanup_orphaned_broadcasts_no_orphans(
        self, mock_list, mock_trans, mock_logger
    ):
        """No transitions when there are no orphaned broadcasts."""
        mock_list.return_value = []
        stream.cleanup_orphaned_broadcasts(MagicMock(), "current", mock_logger)
        mock_trans.assert_not_called()

    @patch("stream._api_list_my_broadcasts")
    def test_cleanup_orphaned_broadcasts_handles_api_error(
        self, mock_list, mock_logger
    ):
        """API errors during listing are logged and do not crash."""
        mock_list.side_effect = Exception("API error")
        stream.cleanup_orphaned_broadcasts(MagicMock(), "current", mock_logger)
        mock_logger.warn.assert_called()

    @patch("stream._api_transition_broadcast")
    @patch("stream._api_list_my_broadcasts")
    def test_cleanup_orphaned_broadcasts_handles_transition_error(
        self, mock_list, mock_trans, mock_logger
    ):
        """Transition errors for individual orphans are logged, not raised."""
        mock_list.return_value = [
            {"id": "orphan-1", "status": {"lifeCycleStatus": "live"}},
        ]
        mock_trans.side_effect = Exception("transition failed")
        stream.cleanup_orphaned_broadcasts(MagicMock(), "current", mock_logger)
        mock_logger.warn.assert_called()
