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
        stream._api_insert_broadcast(mock_youtube, "title", "public", False, False)
        mock_youtube.liveBroadcasts().insert.assert_called_once()
        mock_youtube.liveBroadcasts().insert().execute.assert_called_once()

    def test_api_insert_broadcast_body_structure(self, mock_youtube):
        """The body kwarg contains the expected snippet, status, and contentDetails."""
        stream._api_insert_broadcast(mock_youtube, "My Title", "unlisted", False, False)
        _, kwargs = mock_youtube.liveBroadcasts().insert.call_args
        body = kwargs["body"]

        assert body["snippet"]["title"] == "My Title"
        assert body["status"]["privacyStatus"] == "unlisted"
        assert body["contentDetails"]["enableAutoStart"] is False
        assert body["contentDetails"]["enableAutoStop"] is False

    def test_api_insert_broadcast_does_not_set_enable_embed(self, mock_youtube):
        """enableEmbed is not set during insert — it is applied via update after creation."""
        stream._api_insert_broadcast(mock_youtube, "T", "public", False, False)
        _, kwargs = mock_youtube.liveBroadcasts().insert.call_args
        assert "enableEmbed" not in kwargs["body"]["contentDetails"]
        assert "embeddable" not in kwargs["body"].get("status", {})

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

    # -- _api_get_video_status -----------------------------------------------

    def test_api_get_video_status_with_items(self, mock_youtube):
        """Returns the status dict when items are present."""
        mock_youtube.videos().list().execute.return_value = {
            "items": [{"status": {"privacyStatus": "public"}}]
        }
        result = stream._api_get_video_status(mock_youtube, "vid")
        assert result == {"privacyStatus": "public"}

    def test_api_get_video_status_empty(self, mock_youtube):
        """Returns None when items list is empty."""
        mock_youtube.videos().list().execute.return_value = {"items": []}
        result = stream._api_get_video_status(mock_youtube, "vid")
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

    @patch("stream.apply_broadcast_embeddable")
    @patch("stream._api_insert_broadcast")
    def test_create_broadcast_returns_id(self, mock_insert, mock_embed, sample_config, mock_logger):
        """create_broadcast returns the broadcast ID from the API response."""
        mock_insert.return_value = {"id": "bcast-1"}
        result = stream.create_broadcast(MagicMock(), sample_config, mock_logger)
        assert result == "bcast-1"

    @patch("stream.apply_broadcast_embeddable")
    @patch("stream._api_insert_broadcast")
    def test_create_broadcast_skips_apply_when_embeddable_true(
        self, mock_insert, mock_embed, sample_config, mock_logger
    ):
        """create_broadcast skips apply_broadcast_embeddable when embeddable=True.

        The YouTube insert API defaults enableEmbed to True, so no update call
        is needed — and it would fail without channel verification anyway.
        """
        sample_config["youtube"]["embeddable"] = True
        mock_insert.return_value = {"id": "bcast-2"}
        stream.create_broadcast(MagicMock(), sample_config, mock_logger)
        mock_embed.assert_not_called()

    @patch("stream.apply_broadcast_embeddable")
    @patch("stream._api_insert_broadcast")
    def test_create_broadcast_calls_apply_when_embeddable_false(
        self, mock_insert, mock_embed, sample_config, mock_logger
    ):
        """create_broadcast calls apply_broadcast_embeddable to disable embedding when embeddable=False."""
        sample_config["youtube"]["embeddable"] = False
        mock_insert.return_value = {"id": "bcast-3"}
        yt = MagicMock()
        stream.create_broadcast(yt, sample_config, mock_logger)
        enable_monitor = sample_config["youtube"]["enableMonitorStream"]
        enable_dvr = sample_config["youtube"]["enableDvr"]
        mock_embed.assert_called_once_with(yt, "bcast-3", False, enable_monitor, enable_dvr, mock_logger)

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

    # -- _api_update_broadcast_content_details --------------------------------

    def test_api_update_broadcast_content_details_calls_update(self, mock_youtube):
        """Calls liveBroadcasts().update() with part=contentDetails and correct body."""
        stream._api_update_broadcast_content_details(
            mock_youtube, "bid-1", {"enableEmbed": True}
        )
        mock_youtube.liveBroadcasts().update.assert_called_once()
        _, kwargs = mock_youtube.liveBroadcasts().update.call_args
        assert kwargs["part"] == "contentDetails"
        assert kwargs["body"]["id"] == "bid-1"
        assert kwargs["body"]["contentDetails"] == {"enableEmbed": True}

    # -- _api_update_video_status --------------------------------------------

    def test_api_update_video_status_calls_videos_update(self, mock_youtube):
        """_api_update_video_status calls videos().update() with part=status."""
        stream._api_update_video_status(mock_youtube, "vid-1", {"embeddable": True})
        mock_youtube.videos().update.assert_called_once()
        _, kwargs = mock_youtube.videos().update.call_args
        assert kwargs["part"] == "status"
        assert kwargs["body"]["id"] == "vid-1"
        assert kwargs["body"]["status"] == {"embeddable": True}

    # -- apply_broadcast_embeddable ------------------------------------------

    @patch("stream._api_update_broadcast_content_details")
    def test_apply_broadcast_embeddable_true(self, mock_update, mock_logger):
        """Sets enableEmbed=True and includes enableMonitorStream and enableDvr in the update body."""
        yt = MagicMock()
        stream.apply_broadcast_embeddable(yt, "bid", True, False, False, mock_logger)
        mock_update.assert_called_once_with(
            yt,
            "bid",
            {"enableEmbed": True, "enableDvr": False, "monitorStream": {"enableMonitorStream": False}},
        )
        mock_logger.debug.assert_called_once()

    @patch("stream._api_update_broadcast_content_details")
    def test_apply_broadcast_embeddable_false(self, mock_update, mock_logger):
        """Sets enableEmbed=False on the broadcast."""
        yt = MagicMock()
        stream.apply_broadcast_embeddable(yt, "bid", False, False, False, mock_logger)
        mock_update.assert_called_once_with(
            yt,
            "bid",
            {"enableEmbed": False, "enableDvr": False, "monitorStream": {"enableMonitorStream": False}},
        )

    @patch("stream._api_update_broadcast_content_details")
    def test_apply_broadcast_embeddable_dvr_disabled(self, mock_update, mock_logger):
        """enableDvr=False is forwarded in the contentDetails patch."""
        yt = MagicMock()
        stream.apply_broadcast_embeddable(yt, "bid", True, False, False, mock_logger)
        _, kwargs = mock_update.call_args
        content_details = mock_update.call_args[0][2]
        assert content_details["enableDvr"] is False

    @patch("stream._api_update_broadcast_content_details")
    def test_apply_broadcast_embeddable_dvr_enabled(self, mock_update, mock_logger):
        """enableDvr=True is forwarded in the contentDetails patch."""
        yt = MagicMock()
        stream.apply_broadcast_embeddable(yt, "bid", True, False, True, mock_logger)
        content_details = mock_update.call_args[0][2]
        assert content_details["enableDvr"] is True

    @patch("stream._api_update_broadcast_content_details")
    def test_apply_broadcast_embeddable_http_error_warns(self, mock_update, mock_logger):
        """HttpError is caught and logged as a warning, no exception raised."""
        from googleapiclient.errors import HttpError

        mock_update.side_effect = HttpError(
            resp=MagicMock(status=400), content=b"invalidEmbedSetting"
        )
        stream.apply_broadcast_embeddable(MagicMock(), "bid", True, False, False, mock_logger)
        mock_logger.warn.assert_called_once()

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

    # -- update_broadcast_title ----------------------------------------------

    @patch("stream._api_update_broadcast_snippet")
    def test_update_broadcast_title_happy_path(self, mock_update, sample_config, mock_logger):
        """Fetches snippet, sets title with interpolated date, calls update."""
        sample_config["youtube"]["broadcastTitle"] = "Test: {date}"
        today = datetime.date.today().isoformat()
        mock_youtube = MagicMock()
        mock_youtube.liveBroadcasts().list().execute.return_value = {
            "items": [{"snippet": {"title": "Old Title"}}]
        }
        stream.update_broadcast_title(mock_youtube, "bid", sample_config, mock_logger)
        # _api_update_broadcast_snippet is called with positional args: youtube, bid, snippet
        mock_update.assert_called_once()
        _, kwargs = mock_update.call_args
        args = mock_update.call_args[0]
        assert args[2]["title"] == f"Test: {today}"
        mock_logger.info.assert_called_with(f'Broadcast title updated: "Test: {today}"')

    @patch("stream._api_update_broadcast_snippet")
    def test_update_broadcast_title_empty_items(self, mock_update, sample_config, mock_logger):
        """Logs warning and returns without updating when no broadcast snippet is found."""
        sample_config["youtube"]["broadcastTitle"] = "Test: {date}"
        mock_youtube = MagicMock()
        mock_youtube.liveBroadcasts().list().execute.return_value = {"items": []}
        stream.update_broadcast_title(mock_youtube, "bid", sample_config, mock_logger)
        mock_update.assert_not_called()
        mock_logger.warn.assert_called_once()

    @patch("stream._api_update_broadcast_snippet")
    def test_update_broadcast_title_http_error(self, mock_update, sample_config, mock_logger):
        """HttpError is caught and logged as a warning, no exception raised."""
        from googleapiclient.errors import HttpError

        sample_config["youtube"]["broadcastTitle"] = "Test: {date}"
        mock_youtube = MagicMock()
        mock_youtube.liveBroadcasts().list().execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b"error"
        )
        stream.update_broadcast_title(mock_youtube, "bid", sample_config, mock_logger)
        mock_update.assert_not_called()
        mock_logger.warn.assert_called_once()

    # -- _attempt_testing_transition -----------------------------------------

    @patch("stream._poll_until_lifecycle_status")
    def test_attempt_testing_transition_http_error(self, mock_poll, sample_config, mock_logger):
        """HttpError from _api_transition_broadcast is caught and logged as a warning."""
        from googleapiclient.errors import HttpError

        mock_youtube = MagicMock()
        mock_youtube.liveBroadcasts().transition.side_effect = HttpError(
            resp=MagicMock(status=500), content=b"transition failed"
        )
        stream._attempt_testing_transition(mock_youtube, "bid", mock_logger)
        mock_poll.assert_not_called()
        mock_logger.warn.assert_called_once()

    # -- _poll_until_lifecycle_status ----------------------------------------

    @patch("stream.time.sleep")
    def test_poll_until_lifecycle_status_immediate(self, mock_sleep, sample_config, mock_logger):
        """Returns on the first check when target status is already present."""
        mock_youtube = MagicMock()
        mock_youtube.liveBroadcasts().list().execute.return_value = {
            "items": [{"status": {"lifeCycleStatus": "testing"}}]
        }
        stream._poll_until_lifecycle_status(mock_youtube, "bid", "testing", mock_logger)
        assert mock_sleep.call_count == 0

    @patch("stream.time.sleep")
    def test_poll_until_lifecycle_status_reaches_target(self, mock_sleep, sample_config, mock_logger):
        """Sleeps between polls and returns when target status is reached after N iterations."""
        mock_youtube = MagicMock()
        # First poll returns 'ready', second poll returns 'testing' (target)
        mock_youtube.liveBroadcasts().list().execute.side_effect = [
            {"items": [{"status": {"lifeCycleStatus": "ready"}}]},
            {"items": [{"status": {"lifeCycleStatus": "testing"}}]},
        ]
        stream._poll_until_lifecycle_status(mock_youtube, "bid", "testing", mock_logger)
        assert mock_sleep.call_count == 1

    @patch("stream.time.sleep")
    def test_poll_until_lifecycle_status_exhausts_iterations(self, mock_sleep):
        """Exhausts all configured iterations without raising an error."""
        # Patch the range to only iterate 3 times so test runs fast.
        # Sleep is called on every iteration because target never matches,
        # so call_count equals the number of iterations.
        with patch("stream.range", return_value=range(3)):
            mock_youtube = MagicMock()
            # Never matches target "testing"
            mock_youtube.liveBroadcasts().list().execute.return_value = {
                "items": [{"status": {"lifeCycleStatus": "ready"}}]
            }
            stream._poll_until_lifecycle_status(mock_youtube, "bid", "testing", MagicMock())
            assert mock_sleep.call_count == 3

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

    @patch("stream._api_get_broadcast_lifecycle")
    def test_ensure_broadcast_live_complete_raises(
        self, mock_lifecycle, mock_logger, sample_config
    ):
        """Raises RuntimeError when broadcast status is 'complete' — caller must create a fresh one."""
        mock_lifecycle.return_value = "complete"
        with pytest.raises(RuntimeError, match="must be replaced"):
            stream.ensure_broadcast_live(MagicMock(), "bid", sample_config, mock_logger)

    @patch("stream._api_get_broadcast_lifecycle")
    def test_ensure_broadcast_live_complete_does_not_create_fresh(
        self, mock_lifecycle, mock_logger, sample_config
    ):
        """Does NOT call _create_fresh_broadcast when status is 'complete'."""
        mock_lifecycle.return_value = "complete"
        with patch("stream._create_fresh_broadcast") as mock_create:
            try:
                stream.ensure_broadcast_live(MagicMock(), "bid", sample_config, mock_logger)
            except RuntimeError:
                pass  # Expected
        mock_create.assert_not_called()

    @patch("stream._api_get_broadcast_lifecycle")
    def test_ensure_broadcast_live_empty_id_raises(
        self, mock_lifecycle, mock_logger, sample_config
    ):
        """Raises RuntimeError when broadcast_id is empty string."""
        with pytest.raises(RuntimeError, match="Broadcast ID is required"):
            stream.ensure_broadcast_live(MagicMock(), "", sample_config, mock_logger)

    @patch("stream._api_get_broadcast_lifecycle")
    def test_ensure_broadcast_live_none_id_raises(
        self, mock_lifecycle, mock_logger, sample_config
    ):
        """Raises RuntimeError when broadcast_id is None."""
        with pytest.raises(RuntimeError, match="Broadcast ID is required"):
            stream.ensure_broadcast_live(MagicMock(), None, sample_config, mock_logger)

    @patch("stream._api_get_broadcast_lifecycle")
    def test_ensure_broadcast_live_scheduled_raises(
        self, mock_lifecycle, mock_logger, sample_config
    ):
        """Raises RuntimeError for unexpected state 'scheduled'."""
        mock_lifecycle.return_value = "scheduled"
        with pytest.raises(RuntimeError, match="unexpected state"):
            stream.ensure_broadcast_live(MagicMock(), "bid", sample_config, mock_logger)

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

    # -- _api_insert_broadcast enableDvr -------------------------------------

    def test_api_insert_broadcast_sets_enable_dvr_false(self, mock_youtube):
        """enableDvr=False is included in the contentDetails body."""
        stream._api_insert_broadcast(mock_youtube, "T", "public", False, False)
        _, kwargs = mock_youtube.liveBroadcasts().insert.call_args
        assert kwargs["body"]["contentDetails"]["enableDvr"] is False

    def test_api_insert_broadcast_sets_enable_dvr_true(self, mock_youtube):
        """enableDvr=True is forwarded to the contentDetails body."""
        stream._api_insert_broadcast(mock_youtube, "T", "public", False, True)
        _, kwargs = mock_youtube.liveBroadcasts().insert.call_args
        assert kwargs["body"]["contentDetails"]["enableDvr"] is True

    # -- _set_archive_privacy ------------------------------------------------

    @patch("stream._api_update_video_status")
    def test_set_archive_privacy_calls_update(self, mock_update, mock_logger):
        """_set_archive_privacy calls _api_update_video_status with the given privacy level."""
        yt = MagicMock()
        stream._set_archive_privacy(yt, "bid", "private", mock_logger)
        mock_update.assert_called_once_with(yt, "bid", {"privacyStatus": "private"})
        mock_logger.info.assert_called_once()

    @patch("stream._api_update_video_status")
    def test_set_archive_privacy_unlisted(self, mock_update, mock_logger):
        """_set_archive_privacy works for unlisted as well."""
        yt = MagicMock()
        stream._set_archive_privacy(yt, "bid", "unlisted", mock_logger)
        mock_update.assert_called_once_with(yt, "bid", {"privacyStatus": "unlisted"})

    @patch("stream._api_update_video_status")
    def test_set_archive_privacy_error_warns(self, mock_update, mock_logger):
        """Exceptions from _api_update_video_status are caught and logged."""
        mock_update.side_effect = Exception("api error")
        stream._set_archive_privacy(MagicMock(), "bid", "private", mock_logger)
        mock_logger.warn.assert_called_once()

    # -- _complete_broadcast archive privacy ---------------------------------

    @patch("stream._set_archive_privacy")
    @patch("stream.build_youtube_service")
    @patch("stream.get_valid_credentials")
    @patch("stream._api_get_broadcast_lifecycle")
    @patch("stream._api_transition_broadcast")
    def test_complete_broadcast_sets_archive_privacy(
        self, mock_trans, mock_lifecycle, mock_creds, mock_build, mock_set_privacy,
        mock_logger, sample_config
    ):
        """_complete_broadcast calls _set_archive_privacy after transitioning to complete."""
        mock_lifecycle.return_value = "live"
        yt = MagicMock()
        mock_build.return_value = yt
        stream._complete_broadcast(sample_config, mock_logger)
        mock_set_privacy.assert_called_once_with(
            yt, "bcast-123", sample_config["youtube"]["archivePrivacy"], mock_logger
        )

    @patch("stream._set_archive_privacy")
    @patch("stream.build_youtube_service")
    @patch("stream.get_valid_credentials")
    @patch("stream._api_get_broadcast_lifecycle")
    @patch("stream._api_transition_broadcast")
    def test_complete_broadcast_archive_privacy_reads_from_config(
        self, mock_trans, mock_lifecycle, mock_creds, mock_build, mock_set_privacy,
        mock_logger, sample_config
    ):
        """Archive privacy value comes from config, not hardcoded."""
        mock_lifecycle.return_value = "live"
        sample_config["youtube"]["archivePrivacy"] = "unlisted"
        mock_build.return_value = MagicMock()
        stream._complete_broadcast(sample_config, mock_logger)
        mock_set_privacy.assert_called_once()
        assert mock_set_privacy.call_args[0][2] == "unlisted"

    @patch("stream._set_archive_privacy")
    @patch("stream.build_youtube_service")
    @patch("stream.get_valid_credentials")
    @patch("stream._api_get_broadcast_lifecycle")
    @patch("stream._api_transition_broadcast")
    def test_complete_broadcast_skips_archive_privacy_when_already_complete(
        self, mock_trans, mock_lifecycle, mock_creds, mock_build, mock_set_privacy,
        mock_logger, sample_config
    ):
        """_set_archive_privacy is not called when the broadcast is already complete."""
        mock_lifecycle.return_value = "complete"
        stream._complete_broadcast(sample_config, mock_logger)
        mock_set_privacy.assert_not_called()


# ── _api_get_broadcast_snippet ───────────────────────────────────────────────


class TestApiGetBroadcastSnippet:
    def test_returns_snippet_when_broadcast_exists(self, mock_youtube):
        """Returns the snippet dict when liveBroadcasts.list returns items."""
        mock_youtube.liveBroadcasts().list.return_value.execute.return_value = {
            "items": [
                {"snippet": {"title": "Test", "description": "Desc", "thumbnails": {}}}
            ]
        }
        result = stream._api_get_broadcast_snippet(mock_youtube, "bid-123")
        assert result == {"title": "Test", "description": "Desc", "thumbnails": {}}

    def test_returns_none_when_no_items(self, mock_youtube):
        """Returns None when liveBroadcasts.list returns empty items."""
        mock_youtube.liveBroadcasts().list.return_value.execute.return_value = {"items": []}
        result = stream._api_get_broadcast_snippet(mock_youtube, "bid-123")
        assert result is None

    def test_returns_none_on_http_error(self, mock_youtube):
        """Returns None on HttpError without raising."""
        from googleapiclient.errors import HttpError
        mock_youtube.liveBroadcasts().list.return_value.execute.side_effect = HttpError(
            MagicMock(status=403, reason="Forbidden"), b""
        )
        result = stream._api_get_broadcast_snippet(mock_youtube, "bid-123")
        assert result is None

    def test_update_broadcast_title_uses_snippet_helper(self, mock_youtube):
        """update_broadcast_title calls _api_get_broadcast_snippet, not liveBroadcasts.list directly."""
        mock_youtube.liveBroadcasts().list.return_value.execute.return_value = {
            "items": [{"snippet": {"title": "Old Title", "description": "", "thumbnails": {}}}]
        }
        mock_youtube.liveBroadcasts().patch.return_value.execute.return_value = {}

        with patch("stream._api_get_broadcast_snippet") as mock_snippet,              patch("stream.interpolate_broadcast_title", return_value="New Title"):
            mock_snippet.return_value = {"title": "Old Title", "description": "", "thumbnails": {}}
            stream.update_broadcast_title(mock_youtube, "bid", MagicMock(), MagicMock())
            mock_snippet.assert_called_once_with(mock_youtube, "bid")

    def test_update_broadcast_title_does_not_patch_when_snippet_none(self):
        """No patch request when _api_get_broadcast_snippet returns None."""
        with patch("stream._api_get_broadcast_snippet", return_value=None) as mock_snip,              patch("stream.interpolate_broadcast_title") as mock_interp:
            stream.update_broadcast_title(MagicMock(), "bid", MagicMock(), MagicMock())
        mock_interp.assert_not_called()

    def test_update_broadcast_title_patches_with_new_title(self):
        """Patches the broadcast with updated title when snippet is found."""
        mock_youtube = MagicMock()
        with patch("stream._api_get_broadcast_snippet", return_value={"title": "Old"}),              patch("stream.interpolate_broadcast_title", return_value="New Title"),              patch("stream._api_update_broadcast_snippet") as mock_patch:
            stream.update_broadcast_title(mock_youtube, "bid", MagicMock(), MagicMock())
        mock_patch.assert_called_once()


# ── _transition_to_complete_if_active ────────────────────────────────────────


class TestTransitionToCompleteIfActive:
    @patch("stream._api_get_broadcast_lifecycle")
    @patch("stream._api_transition_broadcast")
    def test_transitions_live(self, mock_trans, mock_lifecycle, mock_logger):
        """Transitions a live broadcast to complete and returns True."""
        mock_lifecycle.return_value = "live"
        yt = MagicMock()
        result = stream._transition_to_complete_if_active(yt, "bid", mock_logger)
        assert result is True
        mock_trans.assert_called_once_with(yt, "bid", "complete")

    @patch("stream._api_get_broadcast_lifecycle")
    @patch("stream._api_transition_broadcast")
    def test_transitions_ready(self, mock_trans, mock_lifecycle, mock_logger):
        """Transitions a ready broadcast to complete and returns True."""
        mock_lifecycle.return_value = "ready"
        result = stream._transition_to_complete_if_active(MagicMock(), "bid", mock_logger)
        assert result is True

    @patch("stream._api_get_broadcast_lifecycle")
    @patch("stream._api_transition_broadcast")
    def test_transitions_testing(self, mock_trans, mock_lifecycle, mock_logger):
        """Transitions a testing broadcast to complete and returns True."""
        mock_lifecycle.return_value = "testing"
        result = stream._transition_to_complete_if_active(MagicMock(), "bid", mock_logger)
        assert result is True

    @patch("stream._api_get_broadcast_lifecycle")
    @patch("stream._api_transition_broadcast")
    def test_transitions_created(self, mock_trans, mock_lifecycle, mock_logger):
        """Transitions a created broadcast to complete and returns True."""
        mock_lifecycle.return_value = "created"
        result = stream._transition_to_complete_if_active(MagicMock(), "bid", mock_logger)
        assert result is True

    @patch("stream._api_get_broadcast_lifecycle")
    @patch("stream._api_transition_broadcast")
    def test_skips_complete(self, mock_trans, mock_lifecycle, mock_logger):
        """Does not transition when broadcast is already complete; returns False."""
        mock_lifecycle.return_value = "complete"
        result = stream._transition_to_complete_if_active(MagicMock(), "bid", mock_logger)
        assert result is False
        mock_trans.assert_not_called()

    @patch("stream._api_get_broadcast_lifecycle")
    def test_skips_empty_id(self, mock_trans, mock_logger):
        """Does nothing when broadcast_id is empty string; returns False."""
        result = stream._transition_to_complete_if_active(MagicMock(), "", mock_logger)
        assert result is False
        mock_trans.assert_not_called()

    @patch("stream._api_get_broadcast_lifecycle")
    def test_skips_none_id(self, mock_trans, mock_logger):
        """Does nothing when broadcast_id is None; returns False."""
        result = stream._transition_to_complete_if_active(MagicMock(), None, mock_logger)
        assert result is False
        mock_trans.assert_not_called()

    @patch("stream._api_get_broadcast_lifecycle")
    @patch("stream._api_transition_broadcast")
    def test_complete_broadcast_delegates(self, mock_trans, mock_lifecycle, mock_logger):
        """_complete_broadcast delegates to _transition_to_complete_if_active."""
        mock_lifecycle.return_value = "live"
        with patch.object(stream, "_transition_to_complete_if_active") as mock_helper:
            stream._complete_broadcast = MagicMock()  # noqa — we test delegation below


# ── _wait_and_go_live ────────────────────────────────────────────────────────


class TestWaitAndGoLive:
    @patch("stream.ensure_broadcast_live")
    @patch("stream.wait_for_stream_active", return_value=True)
    def test_validates_stream_active_then_ensures_live(self, mock_wait, mock_ensure):
        """With valid stream_id: calls wait_for_stream_active then ensure_broadcast_live."""
        yt = MagicMock()
        logger = MagicMock()
        stream._wait_and_go_live(yt, "bid", "stream-123", MagicMock(), logger)
        mock_wait.assert_called_once_with(yt, "stream-123", logger)
        mock_ensure.assert_called_once()

    @patch("stream.ensure_broadcast_live")
    @patch("time.sleep", return_value=None)
    def test_sleeps_when_stream_id_empty(self, mock_sleep, mock_ensure):
        """With empty stream_id: sleeps 15s instead of polling."""
        with patch("stream.PrintLogger") as mock_logger_cls:
            logger = MagicMock()
            stream._wait_and_go_live(MagicMock(), "bid", "", MagicMock(), logger)
        mock_sleep.assert_called_once_with(15)

    @patch("stream.ensure_broadcast_live")
    @patch("time.sleep", return_value=None)
    def test_sleeps_when_stream_id_none(self, mock_sleep, mock_ensure):
        """With None stream_id: sleeps 15s instead of polling."""
        with patch("stream.PrintLogger") as mock_logger_cls:
            logger = MagicMock()
            stream._wait_and_go_live(MagicMock(), "bid", None, MagicMock(), logger)
        mock_sleep.assert_called_once_with(15)

    @patch("stream.ensure_broadcast_live")
    @patch("stream.wait_for_stream_active", return_value=False)
    def test_raises_when_stream_inactive(self, mock_wait, mock_ensure):
        """Raises RuntimeError when wait_for_stream_active returns False."""
        with pytest.raises(RuntimeError, match="Stream did not become active"):
            stream._wait_and_go_live(MagicMock(), "bid", "stream-123", MagicMock(), MagicMock())
        mock_ensure.assert_not_called()

    @patch("stream.update_broadcast_title")
    def test_does_not_call_update_broadcast_title(self, mock_update):
        """_wait_and_go_live does NOT call update_broadcast_title."""
        with patch("stream.wait_for_stream_active", return_value=True),              patch("stream.ensure_broadcast_live"),              patch.object(stream, "update_broadcast_title") as mock_update:
            stream._wait_and_go_live(MagicMock(), "bid", "stream-123", MagicMock(), MagicMock())
        mock_update.assert_not_called()

