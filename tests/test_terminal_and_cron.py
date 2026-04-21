"""Tests for terminal detection and crontab management."""

import stream
from unittest.mock import MagicMock, patch


# ── Terminal Detection ──────────────────────────────────────────────────────


class TestDetectTerminal:
    def test_detect_terminal_gnome(self):
        """When gnome-terminal is available, it is returned."""
        def fake_which(name):
            if name == "gnome-terminal":
                return "/usr/bin/gnome-terminal"
            return None

        with patch("stream.shutil.which", side_effect=fake_which):
            assert stream.detect_terminal() == "gnome-terminal"

    def test_detect_terminal_xterm_only(self):
        """When only xterm is available, xterm is returned."""
        def fake_which(name):
            if name == "xterm":
                return "/usr/bin/xterm"
            return None

        with patch("stream.shutil.which", side_effect=fake_which):
            assert stream.detect_terminal() == "xterm"

    def test_detect_terminal_none(self):
        """When no terminal is found, xterm is returned as fallback."""
        with patch("stream.shutil.which", return_value=None):
            assert stream.detect_terminal() == "xterm"

    def test_detect_terminal_priority(self):
        """When gnome-terminal and konsole are both available, gnome-terminal wins (first in list)."""
        def fake_which(name):
            if name in ("gnome-terminal", "konsole"):
                return f"/usr/bin/{name}"
            return None

        with patch("stream.shutil.which", side_effect=fake_which):
            assert stream.detect_terminal() == "gnome-terminal"


# ── Cron Line Building ─────────────────────────────────────────────────────


class TestBuildCronLine:
    def test_build_cron_line_stop(self):
        """A stop cron line has no terminal wrapper and includes --stop and CRON_MARKER."""
        line = stream._build_cron_line("25 18 * * *", "gnome-terminal", "stop")
        assert "--stop" in line
        assert stream.CRON_MARKER in line
        assert line.endswith(stream.CRON_MARKER)
        assert "gnome-terminal" not in line

    def test_build_cron_line_start_gnome(self):
        """A gnome-terminal start line uses --title= format and sets DISPLAY=:0."""
        line = stream._build_cron_line("30 6 * * *", "gnome-terminal", "start")
        assert "gnome-terminal --title=" in line
        assert "DISPLAY=:0" in line

    def test_build_cron_line_start_xfce4(self):
        """An xfce4-terminal start line uses -e \" format."""
        line = stream._build_cron_line("30 6 * * *", "xfce4-terminal", "start")
        assert '-e "' in line

    def test_build_cron_line_start_xterm(self):
        """An xterm start line uses -T ' format."""
        line = stream._build_cron_line("30 6 * * *", "xterm", "start")
        assert "-T '" in line

    def test_build_cron_line_schedule(self):
        """The schedule expression appears at the start of the cron line."""
        schedule = "30 6 1-31 4-10 *"
        line = stream._build_cron_line(schedule, "gnome-terminal", "start")
        assert line.startswith(schedule)

    def test_build_cron_line_recover(self):
        """A recover cron line uses @reboot, invokes --recover, and has no terminal wrapper."""
        line = stream._build_cron_line(None, "gnome-terminal", "recover")
        assert line.startswith("@reboot ")
        assert "--recover" in line
        assert line.endswith(stream.CRON_MARKER)
        assert "gnome-terminal" not in line
        assert "DISPLAY=:0" not in line

    def test_build_cron_line_update(self):
        """An update cron line uses the given schedule, invokes --update, and has no terminal wrapper."""
        line = stream._build_cron_line("0 0 * * *", "gnome-terminal", "update")
        assert line.startswith("0 0 * * *")
        assert "--update" in line
        assert line.endswith(stream.CRON_MARKER)
        assert "gnome-terminal" not in line
        assert "DISPLAY=:0" not in line


# ── Cron Management Helpers ─────────────────────────────────────────────────


class TestRemoveMarkerLines:
    def test_remove_marker_lines_removes(self):
        """Lines containing the marker are removed, others kept."""
        text = f"line1\nline2 {stream.CRON_MARKER}\nline3"
        result = stream._remove_marker_lines(text)
        assert len(result) == 2
        assert "line1" in result
        assert "line3" in result

    def test_remove_marker_lines_empty(self):
        """An empty string produces an empty list."""
        result = stream._remove_marker_lines("")
        assert result == []

    def test_remove_marker_lines_no_markers(self):
        """When no lines contain the marker, all are kept."""
        text = "line1\nline2\nline3"
        result = stream._remove_marker_lines(text)
        assert len(result) == 3


class TestReadCurrentCrontab:
    def test_read_current_crontab_success(self):
        """When crontab -l succeeds, its stdout is returned."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "line1\nline2"

        with patch("stream.subprocess.run", return_value=mock_result):
            result = stream._read_current_crontab()
            assert result == "line1\nline2"

    def test_read_current_crontab_no_crontab(self):
        """When crontab -l returns non-zero, an empty string is returned."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("stream.subprocess.run", return_value=mock_result):
            result = stream._read_current_crontab()
            assert result == ""

    def test_read_current_crontab_missing_binary(self):
        """When crontab binary is missing (FileNotFoundError), empty string is returned."""
        with patch("stream.subprocess.run", side_effect=FileNotFoundError):
            result = stream._read_current_crontab()
            assert result == ""


# ── register / remove cron entries ─────────────────────────────────────────


class TestRegisterCronEntries:
    def test_register_cron_entries_writes(self, sample_config):
        """register_cron_entries writes a crontab with start, stop, and recover lines."""
        with patch("stream._read_current_crontab", return_value=""), \
             patch("stream.subprocess.run") as mock_run:
            stream.register_cron_entries(sample_config)

            mock_run.assert_called_once()
            written = mock_run.call_args.kwargs.get("input") or mock_run.call_args[1].get("input", "")
            assert "--start" in written
            assert "--stop" in written
            assert "--recover" in written
            assert "@reboot" in written
            assert stream.CRON_MARKER in written

    def test_register_cron_entries_replaces_old(self, sample_config):
        """Old marker lines are removed before writing new ones."""
        old_crontab = f"keep-this\nold entry {stream.CRON_MARKER}\n"

        with patch("stream._read_current_crontab", return_value=old_crontab), \
             patch("stream.subprocess.run") as mock_run:
            stream.register_cron_entries(sample_config)

            written = mock_run.call_args.kwargs.get("input") or mock_run.call_args[1].get("input", "")
            assert "keep-this" in written
            assert "old entry" not in written
            # Three new entries: start, stop, recover
            assert written.count(stream.CRON_MARKER) == 3

    def test_register_cron_entries_with_logger(self, sample_config, mock_logger):
        """When a logger is passed, logger.info is called."""
        with patch("stream._read_current_crontab", return_value=""), \
             patch("stream.subprocess.run"):
            stream.register_cron_entries(sample_config, logger=mock_logger)

            mock_logger.info.assert_called()

    def test_register_cron_entries_without_logger(self, sample_config, capsys):
        """When no logger is passed, output goes to print (stdout)."""
        with patch("stream._read_current_crontab", return_value=""), \
             patch("stream.subprocess.run"):
            stream.register_cron_entries(sample_config)

            captured = capsys.readouterr()
            assert "Crontab entries registered" in captured.out


    def test_register_cron_entries_with_auto_update(self, sample_config):
        """When autoUpdate is true, a --update cron line is included."""
        sample_config["cron"]["autoUpdate"] = True
        sample_config["cron"]["update"] = "0 0 * * *"

        with patch("stream._read_current_crontab", return_value=""), \
             patch("stream.subprocess.run") as mock_run:
            stream.register_cron_entries(sample_config)

            written = mock_run.call_args.kwargs.get("input") or mock_run.call_args[1].get("input", "")
            assert "--update" in written
            assert written.count(stream.CRON_MARKER) == 4

    def test_register_cron_entries_without_auto_update(self, sample_config):
        """When autoUpdate is false, no --update cron line is included."""
        sample_config["cron"]["autoUpdate"] = False

        with patch("stream._read_current_crontab", return_value=""), \
             patch("stream.subprocess.run") as mock_run:
            stream.register_cron_entries(sample_config)

            written = mock_run.call_args.kwargs.get("input") or mock_run.call_args[1].get("input", "")
            assert "--update" not in written
            assert written.count(stream.CRON_MARKER) == 3

    def test_register_cron_entries_auto_update_missing_schedule(self, sample_config):
        """When autoUpdate is true but update schedule is empty, no update line is added."""
        sample_config["cron"]["autoUpdate"] = True
        sample_config["cron"]["update"] = ""

        with patch("stream._read_current_crontab", return_value=""), \
             patch("stream.subprocess.run") as mock_run:
            stream.register_cron_entries(sample_config)

            written = mock_run.call_args.kwargs.get("input") or mock_run.call_args[1].get("input", "")
            assert "--update" not in written


class TestRemoveCronEntries:
    def test_remove_cron_entries(self):
        """remove_cron_entries strips all marker lines from the crontab."""
        existing = f"keep-line\nmarked {stream.CRON_MARKER}\nalso-keep"

        with patch("stream._read_current_crontab", return_value=existing), \
             patch("stream.subprocess.run") as mock_run:
            stream.remove_cron_entries()

            written = mock_run.call_args.kwargs.get("input") or mock_run.call_args[1].get("input", "")
            assert "keep-line" in written
            assert "also-keep" in written
            assert stream.CRON_MARKER not in written
