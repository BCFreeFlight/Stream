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
        stream._api_insert_broadcast(mock_youtube, "title", "public", False, True)
        mock_youtube.liveBroadcasts().insert.assert_called_once()
        mock_youtube.liveBroadcasts().insert().execute.assert_called_once()

    def test_api_insert_broadcast_body_structure(self, mock_youtube):
        """The body kwarg contains the expected snippet, status, and contentDetails."""
        stream._api_insert_broadcast(mock_youtube, "My Title", "unlisted", False, True)
        _, kwargs = mock_youtube.liveBroadcasts().insert.call_args
        body = kwargs["body"]

        assert body["snippet"]["title"] == "My Title"
        assert body["status"]["privacyStatus"] == "unlisted"
        assert body["contentDetails"]["enableAutoStart"] is False
        assert body["contentDetails"]["enableAutoStop"] is False

    def test_api_insert_broadcast_embeddable_true(self, mock_youtube):
        """embeddable=True is set in the status body."""
        stream._api_insert_broadcast(mock_youtube, "T", "public", False, True)
        _, kwargs = mock_youtube.liveBroadcasts().insert.call_args
        assert kwargs["body"]["status"]["embeddable"] is True

    def test_api_insert_broadcast_embeddable_false(self, mock_youtube):
        """embeddable=False is set in the status body."""
        stream._api_insert_broadcast(mock_youtube, "T", "public", False, False)
        _, kwargs = mock_youtube.liveBroadcasts().insert.call_args
        assert kwargs["body"]["status"]["embeddable"] is False

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

    # -- _api_delete_broadcast -----------------------------------------------

    def test_api_delete_broadcast_calls_execute(self, mock_youtube):
        """delete chains liveBroadcasts().delete().execute()."""
        stream._api_delete_broadcast(mock_youtube, "bid")
        mock_youtube.liveBroadcasts().delete.assert_called_once_with(id="bid")
        mock_youtube.liveBroadcasts().delete().execute.assert_called_once()

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

    @patch("stream._api_insert_broadcast")
    def test_create_broadcast_passes_embeddable_true(self, mock_insert, sample_config, mock_logger):
        """create_broadcast forwards embeddable=True from config to the API call."""
        sample_config["youtube"]["embeddable"] = True
        mock_insert.return_value = {"id": "bcast-2"}
        stream.create_broadcast(MagicMock(), sample_config, mock_logger)
        assert mock_insert.call_args[0][4] is True

    @patch("stream._api_insert_broadcast")
    def test_create_broadcast_passes_embeddable_false(self, mock_insert, sample_config, mock_logger):
        """create_broadcast forwards embeddable=False from config to the API call."""
        sample_config["youtube"]["embeddable"] = False
        mock_insert.return_value = {"id": "bcast-3"}
        stream.create_broadcast(MagicMock(), sample_config, mock_logger)
        assert mock_insert.call_args[0][4] is False

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

    # -- _api_update_video_status --------------------------------------------

    def test_api_update_video_status_calls_videos_update(self, mock_youtube):
        """_api_update_video_status calls videos().update() with part=status."""
        stream._api_update_video_status(mock_youtube, "vid-1", {"embeddable": True})
        mock_youtube.videos().update.assert_called_once()
        _, kwargs = mock_youtube.videos().update.call_args
        assert kwargs["part"] == "status"
        assert kwargs["body"]["id"] == "vid-1"
        assert kwargs["body"]["status"] == {"embeddable": True}

    # -- apply_video_embeddable ----------------------------------------------

    @patch("stream.time.sleep")
    @patch("stream._api_update_video_status")
    @patch("stream._api_get_video_status")
    def test_apply_video_embeddable_true(self, mock_get, mock_update, mock_sleep, mock_logger):
        """Sets embeddable=True on the video status when the resource is immediately available."""
        mock_get.return_value = {"embeddable": False, "privacyStatus": "public"}
        yt = MagicMock()
        stream.apply_video_embeddable(yt, "bid", True, mock_logger)
        mock_update.assert_called_once_with(yt, "bid", {"embeddable": True, "privacyStatus": "public"})
        mock_logger.debug.assert_called_once()

    @patch("stream.time.sleep")
    @patch("stream._api_update_video_status")
    @patch("stream._api_get_video_status")
    def test_apply_video_embeddable_false(self, mock_get, mock_update, mock_sleep, mock_logger):
        """Sets embeddable=False on the video status."""
        mock_get.return_value = {"embeddable": True, "privacyStatus": "public"}
        yt = MagicMock()
        stream.apply_video_embeddable(yt, "bid", False, mock_logger)
        mock_update.assert_called_once_with(yt, "bid", {"embeddable": False, "privacyStatus": "public"})

    @patch("stream.time.sleep")
    @patch("stream._api_update_video_status")
    @patch("stream._api_get_video_status")
    def test_apply_video_embeddable_http_error(self, mock_get, mock_update, mock_sleep, mock_logger):
        """HttpError is caught and logged as a warning, no exception raised."""
        from googleapiclient.errors import HttpError

        mock_get.return_value = {"embeddable": True}
        mock_update.side_effect = HttpError(
            resp=MagicMock(status=403), content=b"forbidden"
        )
        stream.apply_video_embeddable(MagicMock(), "bid", True, mock_logger)
        mock_logger.warn.assert_called_once()

    @patch("stream.time.sleep")
    @patch("stream._api_update_video_status")
    @patch("stream._api_get_video_status")
    def test_apply_video_embeddable_video_not_ready_warns(
        self, mock_get, mock_update, mock_sleep, mock_logger
    ):
        """Logs a warning and skips the update when the video resource never becomes available."""
        mock_get.return_value = None
        stream.apply_video_embeddable(MagicMock(), "bid", True, mock_logger)
        mock_update.assert_not_called()
        mock_logger.warn.assert_called_once()

    @patch("stream.time.sleep")
    @patch("stream._api_update_video_status")
    @patch("stream._api_get_video_status")
    def test_apply_video_embeddable_retries_until_ready(
        self, mock_get, mock_update, mock_sleep, mock_logger
    ):
        """Polls until the video resource exists, then applies the embeddable flag."""
        mock_get.side_effect = [None, None, {"embeddable": False}]
        yt = MagicMock()
        stream.apply_video_embeddable(yt, "bid", True, mock_logger)
        assert mock_get.call_count == 3
        mock_update.assert_called_once()
        assert mock_sleep.call_count == 2

    # -- find_stream_resource_by_key -----------------------------------------

    @patch("stream._api_list_my_streams")
    def test_find_stream_resource_by_key_found(self, mock_list, mock_logger):
        """Returns (stream_id, rtmp_url, backup_url) when a matching key is found."""
        mock_list.return_value = [
            {
                "id": "s1",
                "cdn": {
                    "ingestionInfo": {
                        "streamName": "key1",
                        "ingestionAddress": "rtmp://primary",
                        "backupIngestionAddress": "rtmp://backup",
                    }
                },
            }
        ]
        result = stream.find_stream_resource_by_key(MagicMock(), "key1", mock_logger)
        assert result == ("s1", "rtmp://primary", "rtmp://backup")

    @patch("stream._api_list_my_streams")
    def test_find_stream_resource_by_key_not_found(self, mock_list, mock_logger):
        """Returns None when no stream matches the key."""
        mock_list.return_value = [
            {"id": "s1", "cdn": {"ingestionInfo": {"streamName": "other",
                                                   "ingestionAddress": "rtmp://x",
                                                   "backupIngestionAddress": ""}}}
        ]
        result = stream.find_stream_resource_by_key(MagicMock(), "key1", mock_logger)
        assert result is None

    @patch("stream._api_list_my_streams")
    def test_find_stream_resource_by_key_no_backup_url(self, mock_list, mock_logger):
        """backup_url defaults to empty string when backupIngestionAddress is absent."""
        mock_list.return_value = [
            {
                "id": "s1",
                "cdn": {
                    "ingestionInfo": {
                        "streamName": "key1",
                        "ingestionAddress": "rtmp://primary",
                    }
                },
            }
        ]
        result = stream.find_stream_resource_by_key(MagicMock(), "key1", mock_logger)
        assert result == ("s1", "rtmp://primary", "")

    # -- find_stream_by_key --------------------------------------------------

    @patch("stream._api_list_my_streams")
    def test_find_stream_by_key_found(self, mock_list, mock_logger):
        """Returns the stream ID when a matching streamName is found."""
        mock_list.return_value = [
            {
                "id": "s1",
                "cdn": {
                    "ingestionInfo": {
                        "streamName": "key1",
                        "ingestionAddress": "rtmp://primary",
                        "backupIngestionAddress": "rtmp://backup",
                    }
                },
            }
        ]
        result = stream.find_stream_by_key(MagicMock(), "key1", mock_logger)
        assert result == "s1"

    @patch("stream._api_list_my_streams")
    def test_find_stream_by_key_not_found(self, mock_list, mock_logger):
        """Returns None when no stream matches the key."""
        mock_list.return_value = [
            {
                "id": "s1",
                "cdn": {
                    "ingestionInfo": {
                        "streamName": "other",
                        "ingestionAddress": "rtmp://x",
                        "backupIngestionAddress": "",
                    }
                },
            }
        ]
        result = stream.find_stream_by_key(MagicMock(), "key1", mock_logger)
        assert result is None

    # -- stream ID resolution in _connect_to_broadcast ----------------------

    @patch("stream.get_valid_credentials")
    @patch("stream.build_youtube_service")
    @patch("stream.find_stream_by_key")
    def test_connect_to_broadcast_resolves_stream_id_from_key(
        self, mock_find, mock_build_yt, mock_creds, mock_logger, sample_config
    ):
        """_connect_to_broadcast uses find_stream_by_key to resolve the stream ID."""
        mock_find.return_value = "s-resolved"
        ctx = stream._connect_to_broadcast(sample_config, mock_logger)
        mock_find.assert_called_once_with(mock_build_yt.return_value, "xxxx-yyyy-zzzz", mock_logger)
        assert ctx.stream_id == "s-resolved"

    @patch("stream.get_valid_credentials")
    @patch("stream.build_youtube_service")
    @patch("stream.find_stream_by_key")
    def test_connect_to_broadcast_empty_stream_id_when_key_not_found(
        self, mock_find, mock_build_yt, mock_creds, mock_logger, sample_config
    ):
        """stream_id is empty string when find_stream_by_key returns None."""
        mock_find.return_value = None
        ctx = stream._connect_to_broadcast(sample_config, mock_logger)
        assert ctx.stream_id == ""

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

    # -- _retire_orphaned_broadcast ------------------------------------------

    def test_retire_orphaned_completes_live(self, mock_logger):
        """A live broadcast is transitioned to complete."""
        yt = MagicMock()
        stream._retire_orphaned_broadcast(yt, "bid", "live", mock_logger)
        yt.liveBroadcasts().transition.assert_called_once()
        yt.liveBroadcasts().delete.assert_not_called()

    def test_retire_orphaned_completes_testing(self, mock_logger):
        """A testing broadcast is transitioned to complete."""
        yt = MagicMock()
        stream._retire_orphaned_broadcast(yt, "bid", "testing", mock_logger)
        yt.liveBroadcasts().transition.assert_called_once()
        yt.liveBroadcasts().delete.assert_not_called()

    def test_retire_orphaned_deletes_created(self, mock_logger):
        """A created broadcast is deleted (cannot be completed directly)."""
        yt = MagicMock()
        stream._retire_orphaned_broadcast(yt, "bid", "created", mock_logger)
        yt.liveBroadcasts().delete.assert_called_once_with(id="bid")
        yt.liveBroadcasts().transition.assert_not_called()

    def test_retire_orphaned_deletes_ready(self, mock_logger):
        """A ready broadcast is deleted (cannot be completed directly)."""
        yt = MagicMock()
        stream._retire_orphaned_broadcast(yt, "bid", "ready", mock_logger)
        yt.liveBroadcasts().delete.assert_called_once_with(id="bid")
        yt.liveBroadcasts().transition.assert_not_called()

    # -- cleanup_orphaned_broadcasts -----------------------------------------

    @patch("stream._retire_orphaned_broadcast")
    @patch("stream._api_list_my_broadcasts")
    def test_cleanup_orphaned_broadcasts_retires_orphans(
        self, mock_list, mock_retire, mock_logger
    ):
        """Orphaned broadcasts are passed to _retire_orphaned_broadcast."""
        mock_list.return_value = [
            {"id": "orphan-1", "status": {"lifeCycleStatus": "live"}},
            {"id": "current", "status": {"lifeCycleStatus": "live"}},
        ]
        yt = MagicMock()
        stream.cleanup_orphaned_broadcasts(yt, "current", mock_logger)
        mock_retire.assert_called_once_with(yt, "orphan-1", "live", mock_logger)

    @patch("stream._retire_orphaned_broadcast")
    @patch("stream._api_list_my_broadcasts")
    def test_cleanup_orphaned_broadcasts_filters_lifecycles_client_side(
        self, mock_list, mock_retire, mock_logger
    ):
        """Only live/ready/testing/created lifecycles are acted on; complete/revoked are skipped."""
        mock_list.return_value = [
            {"id": "live-one", "status": {"lifeCycleStatus": "live"}},
            {"id": "ready-one", "status": {"lifeCycleStatus": "ready"}},
            {"id": "testing-one", "status": {"lifeCycleStatus": "testing"}},
            {"id": "created-one", "status": {"lifeCycleStatus": "created"}},
            {"id": "complete-one", "status": {"lifeCycleStatus": "complete"}},
            {"id": "revoked-one", "status": {"lifeCycleStatus": "revoked"}},
        ]
        stream.cleanup_orphaned_broadcasts(MagicMock(), "current", mock_logger)
        retired = {call.args[1] for call in mock_retire.call_args_list}
        assert retired == {"live-one", "ready-one", "testing-one", "created-one"}

    @patch("stream._retire_orphaned_broadcast")
    @patch("stream._api_list_my_broadcasts")
    def test_cleanup_orphaned_broadcasts_skips_current(
        self, mock_list, mock_retire, mock_logger
    ):
        """The current broadcast is never retired."""
        mock_list.return_value = [
            {"id": "current", "status": {"lifeCycleStatus": "live"}},
        ]
        stream.cleanup_orphaned_broadcasts(MagicMock(), "current", mock_logger)
        mock_retire.assert_not_called()

    @patch("stream._retire_orphaned_broadcast")
    @patch("stream._api_list_my_broadcasts")
    def test_cleanup_orphaned_broadcasts_no_orphans(
        self, mock_list, mock_retire, mock_logger
    ):
        """No action when there are no orphaned broadcasts."""
        mock_list.return_value = []
        stream.cleanup_orphaned_broadcasts(MagicMock(), "current", mock_logger)
        mock_retire.assert_not_called()

    @patch("stream._api_list_my_broadcasts")
    def test_cleanup_orphaned_broadcasts_handles_api_error(
        self, mock_list, mock_logger
    ):
        """API errors during listing are logged and do not crash."""
        mock_list.side_effect = Exception("API error")
        stream.cleanup_orphaned_broadcasts(MagicMock(), "current", mock_logger)
        mock_logger.warn.assert_called()

    @patch("stream._retire_orphaned_broadcast")
    @patch("stream._api_list_my_broadcasts")
    def test_cleanup_orphaned_broadcasts_handles_retire_error(
        self, mock_list, mock_retire, mock_logger
    ):
        """Retire errors for individual orphans are logged, not raised."""
        mock_list.return_value = [
            {"id": "orphan-1", "status": {"lifeCycleStatus": "live"}},
        ]
        mock_retire.side_effect = Exception("retire failed")
        stream.cleanup_orphaned_broadcasts(MagicMock(), "current", mock_logger)
        mock_logger.warn.assert_called()

    # -- _complete_broadcast_if_active ----------------------------------------

    @patch("stream._api_transition_broadcast")
    @patch("stream._api_get_broadcast_lifecycle")
    def test_complete_broadcast_if_active_transitions_live(
        self, mock_lifecycle, mock_trans, mock_logger
    ):
        """Transitions a live broadcast to complete."""
        mock_lifecycle.return_value = "live"
        yt = MagicMock()
        stream._complete_broadcast_if_active(yt, "bid", mock_logger)
        mock_trans.assert_called_once_with(yt, "bid", "complete")

    @patch("stream._api_transition_broadcast")
    @patch("stream._api_get_broadcast_lifecycle")
    def test_complete_broadcast_if_active_transitions_all_active_states(
        self, mock_lifecycle, mock_trans, mock_logger
    ):
        """Transitions ready, testing, and created states to complete."""
        yt = MagicMock()
        for status in ("ready", "testing", "created"):
            mock_lifecycle.return_value = status
            mock_trans.reset_mock()
            stream._complete_broadcast_if_active(yt, "bid", mock_logger)
            mock_trans.assert_called_once_with(yt, "bid", "complete")

    @patch("stream._api_transition_broadcast")
    @patch("stream._api_get_broadcast_lifecycle")
    def test_complete_broadcast_if_active_skips_complete(
        self, mock_lifecycle, mock_trans, mock_logger
    ):
        """Does not transition a broadcast that is already complete."""
        mock_lifecycle.return_value = "complete"
        stream._complete_broadcast_if_active(MagicMock(), "bid", mock_logger)
        mock_trans.assert_not_called()

    @patch("stream._api_transition_broadcast")
    def test_complete_broadcast_if_active_skips_empty_id(
        self, mock_trans, mock_logger
    ):
        """Does nothing when broadcast_id is empty."""
        stream._complete_broadcast_if_active(MagicMock(), "", mock_logger)
        mock_trans.assert_not_called()

    # -- _retire_current_broadcast_safely -------------------------------------

    @patch("stream._complete_broadcast_if_active")
    @patch("stream.build_youtube_service")
    @patch("stream.get_valid_credentials")
    def test_retire_current_broadcast_safely_retires_active(
        self, mock_creds, mock_build, mock_retire, mock_logger, sample_config
    ):
        """Calls _complete_broadcast_if_active with the configured broadcast ID."""
        sample_config["youtube"]["broadcastId"] = "bid-123"
        yt = MagicMock()
        mock_build.return_value = yt
        stream._retire_current_broadcast_safely(sample_config, mock_logger)
        mock_retire.assert_called_once_with(yt, "bid-123", mock_logger)

    @patch("stream.get_valid_credentials")
    def test_retire_current_broadcast_safely_handles_error(
        self, mock_creds, mock_logger, sample_config
    ):
        """Auth or API errors are logged and do not crash."""
        mock_creds.side_effect = Exception("auth failed")
        stream._retire_current_broadcast_safely(sample_config, mock_logger)
        mock_logger.warn.assert_called()
