"""Tests for ffmpeg command building, RTMP URL selection, and process management."""

import subprocess

from unittest.mock import MagicMock, patch

import stream


# ── encode_rtsp_credentials ─────────────────────────────────────────────────


class TestEncodeRtspCredentials:
    def test_encodes_dollar_sign_in_password(self, stream):
        url = "rtsp://admin:Cloudbase$$1@10.10.10.6:554/h264Preview_01_main"
        result = stream.encode_rtsp_credentials(url)
        assert result == "rtsp://admin:Cloudbase%24%241@10.10.10.6:554/h264Preview_01_main"

    def test_encodes_multiple_reserved_chars_in_password(self, stream):
        url = "rtsp://user:p$w&x=y@cam.local/stream"
        result = stream.encode_rtsp_credentials(url)
        assert result == "rtsp://user:p%24w%26x%3Dy@cam.local/stream"

    def test_is_idempotent_on_already_encoded_input(self, stream):
        url = "rtsp://admin:Cloudbase%24%241@10.10.10.6:554/h264Preview_01_main"
        first = stream.encode_rtsp_credentials(url)
        second = stream.encode_rtsp_credentials(first)
        assert first == url
        assert second == url

    def test_returns_url_unchanged_when_no_userinfo(self, stream):
        url = "rtsp://cam.local:554/stream"
        assert stream.encode_rtsp_credentials(url) == url

    def test_encodes_userinfo_without_password(self, stream):
        url = "rtsp://ad$min@cam.local/stream"
        result = stream.encode_rtsp_credentials(url)
        assert result == "rtsp://ad%24min@cam.local/stream"

    def test_preserves_path_and_query(self, stream):
        url = "rtsp://u:p$w@cam.local:554/path/to/stream?param=value"
        result = stream.encode_rtsp_credentials(url)
        assert result == "rtsp://u:p%24w@cam.local:554/path/to/stream?param=value"


# ── _audio_flags ────────────────────────────────────────────────────────────


class TestAudioFlags:
    def test_audio_flags_muted_injects_silent_aac(self, stream):
        """Muted streams transcode the silent source to AAC — not -an."""
        result = stream._audio_flags({"mute": True, "audioCodec": "aac"})
        assert result == ["-c:a", "aac", "-b:a", "128k", "-shortest"]

    def test_audio_flags_not_muted(self, stream):
        result = stream._audio_flags({"mute": False, "audioCodec": "aac"})
        assert result == ["-acodec", "aac"]

    def test_audio_flags_copy_codec(self, stream):
        result = stream._audio_flags({"mute": False, "audioCodec": "copy"})
        assert result == ["-acodec", "copy"]


# ── _silent_audio_input_flags ───────────────────────────────────────────────


class TestSilentAudioInputFlags:
    def test_muted_adds_lavfi_anullsrc_input(self, stream):
        result = stream._silent_audio_input_flags({"mute": True})
        assert result == [
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        ]

    def test_not_muted_adds_nothing(self, stream):
        assert stream._silent_audio_input_flags({"mute": False}) == []


# ── _stream_map_flags ────────────────────────────────────────────────────────


class TestStreamMapFlags:
    def test_muted_maps_camera_video_and_silent_audio(self, stream):
        result = stream._stream_map_flags({"mute": True})
        assert result == ["-map", "0:v:0", "-map", "1:a:0"]

    def test_not_muted_uses_default_mapping(self, stream):
        assert stream._stream_map_flags({"mute": False}) == []


# ── build_ffmpeg_command ────────────────────────────────────────────────────


class TestBuildFfmpegCommand:
    def test_build_ffmpeg_command_muted_injects_silent_aac(self, stream, sample_config):
        """Muted stream adds a second lavfi input and maps both streams."""
        cmd = stream.build_ffmpeg_command(sample_config, "rtmp://url", "key123")
        assert cmd == [
            "ffmpeg", "-re", "-rtsp_transport", "tcp",
            "-i", "rtsp://cam.local/live",
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-map", "0:v:0", "-map", "1:a:0",
            "-vcodec", "copy",
            "-c:a", "aac", "-b:a", "128k", "-shortest",
            "-f", "flv", "rtmp://url/key123",
        ]

    def test_build_ffmpeg_command_with_audio(self, stream, sample_config):
        """Non-muted stream uses a single input, no lavfi, no stream mapping."""
        sample_config["stream"]["mute"] = False
        sample_config["stream"]["audioCodec"] = "aac"
        cmd = stream.build_ffmpeg_command(sample_config, "rtmp://url", "key123")
        assert "-acodec" in cmd
        assert "aac" in cmd
        assert "-an" not in cmd
        assert "lavfi" not in cmd
        assert "-map" not in cmd

    def test_build_ffmpeg_command_muted_has_lavfi_input_before_output(
        self, stream, sample_config
    ):
        """The silent input must appear before the output URL for ffmpeg to parse it."""
        cmd = stream.build_ffmpeg_command(sample_config, "rtmp://url", "key123")
        lavfi_idx = cmd.index("lavfi")
        flv_idx = cmd.index("flv")
        assert lavfi_idx < flv_idx


# ── select_rtmp_url ─────────────────────────────────────────────────────────


class TestSelectRtmpUrl:
    def test_select_rtmp_url_even_attempt(self, stream, sample_config):
        """Attempt 0 (even) returns the primary stream URL."""
        result = stream.select_rtmp_url(sample_config, 0)
        assert result == sample_config["youtube"]["streamURL"]

    def test_select_rtmp_url_odd_attempt_with_backup(self, stream, sample_config):
        """Attempt 1 (odd) with backup configured returns the backup URL."""
        result = stream.select_rtmp_url(sample_config, 1)
        assert result == sample_config["youtube"]["backupStreamUrl"]

    def test_select_rtmp_url_odd_no_backup(self, stream, sample_config):
        """Attempt 1 (odd) with empty backup falls back to primary."""
        sample_config["youtube"]["backupStreamUrl"] = ""
        result = stream.select_rtmp_url(sample_config, 1)
        assert result == sample_config["youtube"]["streamURL"]

    def test_select_rtmp_url_even_with_backup(self, stream, sample_config):
        """Attempt 2 (even) still returns primary even when backup exists."""
        result = stream.select_rtmp_url(sample_config, 2)
        assert result == sample_config["youtube"]["streamURL"]


# ── start_ffmpeg_process ────────────────────────────────────────────────────


class TestStartFfmpegProcess:
    @patch("stream.subprocess.Popen")
    def test_start_ffmpeg_process_redacts_key(self, mock_popen, stream, mock_logger):
        """The stream key is replaced with <REDACTED> in the log message."""
        cmd = ["ffmpeg", "-re", "-f", "flv", "rtmp://url/secret-key"]
        stream.start_ffmpeg_process(cmd, mock_logger)

        logged_message = mock_logger.info.call_args[0][0]
        assert "<REDACTED>" in logged_message
        assert "secret-key" not in logged_message

    @patch("stream.subprocess.Popen")
    def test_start_ffmpeg_process_popen_args(self, mock_popen, stream, mock_logger):
        """Popen is called with the expected pipe/text/bufsize arguments."""
        cmd = ["ffmpeg", "-re", "-f", "flv", "rtmp://url/key"]
        stream.start_ffmpeg_process(cmd, mock_logger)

        mock_popen.assert_called_once_with(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )


# ── relay_ffmpeg_output ─────────────────────────────────────────────────────


class TestRelayFfmpegOutput:
    def test_relay_ffmpeg_output_logs_lines(self, stream, mock_logger):
        """Normal ffmpeg lines are logged at debug level with [ffmpeg] prefix."""
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["line1\n", "line2\n", ""]

        thread = stream.relay_ffmpeg_output(mock_process, mock_logger)
        thread.join(timeout=2)

        logged_messages = [call[0][0] for call in mock_logger.debug.call_args_list]
        assert "[ffmpeg] line1" in logged_messages
        assert "[ffmpeg] line2" in logged_messages

    def test_relay_ffmpeg_output_warning_line_goes_to_warn(self, stream, mock_logger):
        """ffmpeg lines containing 'warning' are routed to logger.warn()."""
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = [
            "  WARNING: library configuration mismatch\n",
            "",
        ]

        thread = stream.relay_ffmpeg_output(mock_process, mock_logger)
        thread.join(timeout=2)

        warn_messages = [call[0][0] for call in mock_logger.warn.call_args_list]
        assert any("WARNING" in m for m in warn_messages)
        debug_messages = [call[0][0] for call in mock_logger.debug.call_args_list]
        assert not any("WARNING" in m for m in debug_messages)

    def test_relay_ffmpeg_output_warning_case_insensitive(self, stream, mock_logger):
        """Warning detection is case-insensitive (e.g. 'warning:' lowercase)."""
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["warning: something\n", ""]

        thread = stream.relay_ffmpeg_output(mock_process, mock_logger)
        thread.join(timeout=2)

        warn_messages = [call[0][0] for call in mock_logger.warn.call_args_list]
        assert any("warning" in m.lower() for m in warn_messages)

    def test_relay_ffmpeg_output_returns_daemon_thread(self, stream, mock_logger):
        """Relay runs in a background daemon thread so it cannot block shutdown."""
        import threading

        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = [""]

        thread = stream.relay_ffmpeg_output(mock_process, mock_logger)
        thread.join(timeout=2)

        assert isinstance(thread, threading.Thread)
        assert thread.daemon is True

    def test_relay_ffmpeg_output_does_not_block_caller(self, stream, mock_logger):
        """Caller should return immediately even if ffmpeg keeps producing output."""
        import queue

        produced = queue.Queue()
        produced.put("early-line\n")

        mock_process = MagicMock()

        def readline():
            try:
                return produced.get(timeout=5)
            except queue.Empty:
                return ""

        mock_process.stdout.readline.side_effect = readline

        thread = stream.relay_ffmpeg_output(mock_process, mock_logger)
        # If the relay blocked the caller, we'd never reach this assertion.
        assert thread.is_alive() or thread.ident is not None
        produced.put("")  # signal EOF so the daemon can exit
        thread.join(timeout=3)

        logged = [call[0][0] for call in mock_logger.debug.call_args_list]
        assert "[ffmpeg] early-line" in logged
