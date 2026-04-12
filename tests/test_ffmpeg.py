"""Tests for ffmpeg command building, RTMP URL selection, and process management."""

import subprocess

from unittest.mock import MagicMock, patch

import stream


# ── _audio_flags ────────────────────────────────────────────────────────────


class TestAudioFlags:
    def test_audio_flags_muted(self, stream):
        result = stream._audio_flags({"mute": True, "audioCodec": "aac"})
        assert result == ["-an"]

    def test_audio_flags_not_muted(self, stream):
        result = stream._audio_flags({"mute": False, "audioCodec": "aac"})
        assert result == ["-acodec", "aac"]

    def test_audio_flags_copy_codec(self, stream):
        result = stream._audio_flags({"mute": False, "audioCodec": "copy"})
        assert result == ["-acodec", "copy"]


# ── build_ffmpeg_command ────────────────────────────────────────────────────


class TestBuildFfmpegCommand:
    def test_build_ffmpeg_command_full(self, stream, sample_config):
        """Muted stream produces -an flag and correct full command."""
        cmd = stream.build_ffmpeg_command(sample_config, "rtmp://url", "key123")
        assert cmd == [
            "ffmpeg", "-re", "-rtsp_transport", "tcp",
            "-i", "rtsp://cam.local/live",
            "-vcodec", "copy",
            "-an",
            "-f", "flv", "rtmp://url/key123",
        ]

    def test_build_ffmpeg_command_with_audio(self, stream, sample_config):
        """Non-muted stream includes -acodec instead of -an."""
        sample_config["stream"]["mute"] = False
        sample_config["stream"]["audioCodec"] = "aac"
        cmd = stream.build_ffmpeg_command(sample_config, "rtmp://url", "key123")
        assert "-acodec" in cmd
        assert "aac" in cmd
        assert "-an" not in cmd


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
        """Each line from ffmpeg stdout is logged with [ffmpeg] prefix."""
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["line1\n", "line2\n", ""]

        stream.relay_ffmpeg_output(mock_process, mock_logger)

        logged_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert "[ffmpeg] line1" in logged_messages
        assert "[ffmpeg] line2" in logged_messages
