"""Tests for do_reinstall orchestration and --reinstall dispatch."""

from unittest.mock import patch

import stream


class TestConfirmReinstall:
    def test_yes_confirms(self):
        """Typing 'yes' returns True."""
        with patch("builtins.input", return_value="yes"):
            assert stream._confirm_reinstall() is True

    def test_yes_case_insensitive(self):
        """Uppercase 'YES' is accepted."""
        with patch("builtins.input", return_value="YES"):
            assert stream._confirm_reinstall() is True

    def test_no_rejects(self):
        """Typing 'no' returns False."""
        with patch("builtins.input", return_value="no"):
            assert stream._confirm_reinstall() is False

    def test_empty_rejects(self):
        """An empty response returns False (safe default)."""
        with patch("builtins.input", return_value=""):
            assert stream._confirm_reinstall() is False


class TestDeleteConfigFiles:
    def test_deletes_both_files(self, tmp_script_dir):
        """config.toml and .env are removed when present."""
        config_path = tmp_script_dir / "config.toml"
        env_path = tmp_script_dir / ".env"
        config_path.write_text("x")
        env_path.write_text("y")

        stream._delete_config_files()

        assert not config_path.exists()
        assert not env_path.exists()

    def test_missing_files_is_not_an_error(self, tmp_script_dir):
        """If neither file exists, the call is a no-op (no exception)."""
        stream._delete_config_files()  # should not raise


class TestDoReinstall:
    def test_cancel_skips_everything(self, tmp_script_dir, capsys):
        """Declining the confirmation prompt skips uninstall, delete, and install."""
        with patch("stream._confirm_reinstall", return_value=False), \
             patch("stream.do_uninstall") as mock_uninstall, \
             patch("stream.do_install") as mock_install, \
             patch("stream._delete_config_files") as mock_delete:
            stream.do_reinstall()

        mock_uninstall.assert_not_called()
        mock_install.assert_not_called()
        mock_delete.assert_not_called()
        assert "cancelled" in capsys.readouterr().out.lower()

    def test_full_flow_when_config_exists(self, tmp_script_dir, capsys):
        """With confirmation and an existing config, chain is uninstall → delete → install."""
        (tmp_script_dir / "config.toml").write_text("x")

        call_order = []
        with patch("stream._confirm_reinstall", return_value=True), \
             patch("stream.do_uninstall", side_effect=lambda: call_order.append("uninstall")), \
             patch("stream._delete_config_files", side_effect=lambda: call_order.append("delete")), \
             patch("stream.do_install", side_effect=lambda: call_order.append("install")):
            stream.do_reinstall()

        assert call_order == ["uninstall", "delete", "install"]

    def test_skips_uninstall_when_no_config_exists(self, tmp_script_dir):
        """Without an existing config.toml, uninstall is skipped but install still runs."""
        # tmp_script_dir is empty — no config.toml present.
        with patch("stream._confirm_reinstall", return_value=True), \
             patch("stream.do_uninstall") as mock_uninstall, \
             patch("stream._delete_config_files"), \
             patch("stream.do_install") as mock_install:
            stream.do_reinstall()

        mock_uninstall.assert_not_called()
        mock_install.assert_called_once()

    def test_preserves_logs_and_backups(self, tmp_script_dir):
        """logs/ and backup/ directories are untouched by reinstall."""
        (tmp_script_dir / "config.toml").write_text("x")
        logs_dir = tmp_script_dir / "logs"
        backup_dir = tmp_script_dir / "backup"
        logs_dir.mkdir()
        backup_dir.mkdir()
        (logs_dir / "2026-04-01.log").write_text("old log")
        (backup_dir / "stream.v0.1.0.bak.zip").write_text("old backup")

        with patch("stream._confirm_reinstall", return_value=True), \
             patch("stream.do_uninstall"), \
             patch("stream.do_install"):
            stream.do_reinstall()

        assert (logs_dir / "2026-04-01.log").exists()
        assert (backup_dir / "stream.v0.1.0.bak.zip").exists()
