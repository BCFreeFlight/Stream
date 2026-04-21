"""Tests for update, backup, and rollback functionality."""

import json
import zipfile
from pathlib import Path
from urllib.error import URLError

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
import tomli_w

import stream
from unittest.mock import MagicMock, patch


# ── Backup ──────────────────────────────────────────────────────────────────


class TestBackup:
    def test_backup_creates_zip(self, tmp_script_dir, sample_resources):
        """_backup_current_files() creates a zip file in the backup/ subdirectory."""
        (tmp_script_dir / "stream.py").write_text("# stream")
        with open(tmp_script_dir / "resources.toml", "wb") as fh:
            tomli_w.dump(sample_resources, fh)

        backup_path = stream._backup_current_files()

        assert backup_path.exists()
        assert backup_path.suffix == ".zip"
        assert backup_path.parent == tmp_script_dir / "backup"

    def test_backup_zip_contains_files(self, tmp_script_dir, sample_resources):
        """The backup zip contains both stream.py and resources.toml."""
        (tmp_script_dir / "stream.py").write_text("# stream")
        with open(tmp_script_dir / "resources.toml", "wb") as fh:
            tomli_w.dump(sample_resources, fh)

        backup_path = stream._backup_current_files()

        with zipfile.ZipFile(backup_path, "r") as zf:
            names = zf.namelist()
            assert "stream.py" in names
            assert "resources.toml" in names

    def test_backup_version_in_filename(self, tmp_script_dir, sample_resources):
        """The backup filename contains the current __version__."""
        (tmp_script_dir / "stream.py").write_text("# stream")
        with open(tmp_script_dir / "resources.toml", "wb") as fh:
            tomli_w.dump(sample_resources, fh)

        with patch.object(stream, "__version__", "v0.1.5"):
            backup_path = stream._backup_current_files()

        assert "v0.1.5" in backup_path.name

    def test_backup_sanitizes_slashes(self, tmp_script_dir, sample_resources):
        """Slashes in __version__ are replaced with underscores in the filename."""
        (tmp_script_dir / "stream.py").write_text("# stream")
        with open(tmp_script_dir / "resources.toml", "wb") as fh:
            tomli_w.dump(sample_resources, fh)

        with patch.object(stream, "__version__", "feat/test"):
            backup_path = stream._backup_current_files()

        assert "feat_test" in backup_path.name
        assert "/" not in backup_path.name


# ── Update — get latest release tag ────────────────────────────────────────


class TestGetLatestReleaseTag:
    def test_get_latest_release_tag_success(self):
        """Returns the tag_name from the GitHub API response."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"tag_name": "v0.1.5"}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = stream._get_latest_release_tag()

        assert result == "v0.1.5"

    def test_get_latest_release_tag_network_error(self):
        """Returns None when a URLError occurs."""
        with patch("urllib.request.urlopen", side_effect=URLError("network down")):
            result = stream._get_latest_release_tag()

        assert result is None

    def test_get_latest_release_tag_bad_json(self):
        """Returns None when the response is not valid JSON."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"not json at all"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = stream._get_latest_release_tag()

        assert result is None


# ── Update — download release asset ────────────────────────────────────────


class TestDownloadReleaseAsset:
    def test_download_release_asset(self, tmp_script_dir):
        """_download_release_asset calls urlretrieve with the correct URL and destination."""
        with patch("urllib.request.urlretrieve") as mock_retrieve:
            stream._download_release_asset("stream.py")

            mock_retrieve.assert_called_once()
            url_arg = mock_retrieve.call_args[0][0]
            dest_arg = mock_retrieve.call_args[0][1]

            assert "stream.py" in url_arg
            assert stream.GITHUB_REPO in url_arg
            assert dest_arg == tmp_script_dir / "stream.py"


# ── do_update ───────────────────────────────────────────────────────────────


class TestDoUpdate:
    def test_do_update_already_latest(self, capsys, sample_resources):
        """When the current version matches the latest, prints 'already' message."""
        with patch.object(stream, "__version__", "v0.1.5"), \
             patch("stream._get_latest_release_tag", return_value="v0.1.5"), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._apply_auto_update_config_defaults"):
            stream.do_update()

        captured = capsys.readouterr()
        assert "already" in captured.out.lower()

    def test_do_update_fetch_failed(self, capsys, sample_resources):
        """When fetching the latest tag fails, prints an error."""
        with patch.object(stream, "__version__", "v0.1.4"), \
             patch("stream._get_latest_release_tag", return_value=None), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._apply_auto_update_config_defaults"):
            stream.do_update()

        captured = capsys.readouterr()
        # Should indicate something went wrong fetching
        assert captured.out.strip() != ""

    def test_do_update_success(self, tmp_script_dir, sample_resources):
        """When a newer version exists, backup and download are called."""
        (tmp_script_dir / "stream.py").write_text("# old")
        (tmp_script_dir / "resources.toml").write_text("")

        with patch.object(stream, "__version__", "v0.1.4"), \
             patch("stream._get_latest_release_tag", return_value="v0.1.5"), \
             patch("stream._backup_current_files", return_value=tmp_script_dir / "backup" / "stream.v0.1.4.bak.zip") as mock_backup, \
             patch("stream._download_release_asset") as mock_download, \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._apply_auto_update_config_defaults"):
            stream.do_update()

        mock_backup.assert_called_once()
        download_calls = [call[0][0] for call in mock_download.call_args_list]
        assert "stream.py" in download_calls
        assert "resources.toml" in download_calls

    def test_do_update_calls_migration(self, sample_resources):
        """do_update calls _apply_auto_update_config_defaults before downloading."""
        with patch.object(stream, "__version__", "v0.1.4"), \
             patch("stream._get_latest_release_tag", return_value="v0.1.4"), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._apply_auto_update_config_defaults") as mock_migrate:
            stream.do_update()

        mock_migrate.assert_called_once()


# ── Auto-update config migration ────────────────────────────────────────────


class TestApplyAutoUpdateConfigDefaults:
    def test_no_op_when_config_missing(self, tmp_script_dir):
        """When config.toml does not exist, the function returns without error."""
        stream._apply_auto_update_config_defaults()
        assert not (tmp_script_dir / "config.toml").exists()

    def test_no_op_when_keys_already_present(self, tmp_script_dir, sample_config):
        """When both autoUpdate and update are already in the config, nothing changes."""
        sample_config["cron"]["autoUpdate"] = True
        sample_config["cron"]["update"] = "30 3 * * *"
        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "wb") as fh:
            tomli_w.dump(sample_config, fh)

        stream._apply_auto_update_config_defaults()

        with open(config_path, "rb") as fh:
            result = tomllib.load(fh)
        assert result["cron"]["autoUpdate"] is True
        assert result["cron"]["update"] == "30 3 * * *"

    def test_adds_both_keys_when_missing(self, tmp_script_dir, sample_config):
        """When neither autoUpdate nor update is present, both are added with defaults."""
        del sample_config["cron"]["autoUpdate"]
        del sample_config["cron"]["update"]
        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "wb") as fh:
            tomli_w.dump(sample_config, fh)

        stream._apply_auto_update_config_defaults()

        with open(config_path, "rb") as fh:
            result = tomllib.load(fh)
        assert result["cron"]["autoUpdate"] is False
        assert result["cron"]["update"] == "0 0 * * *"

    def test_adds_missing_auto_update_only(self, tmp_script_dir, sample_config):
        """When only autoUpdate is missing, it is added; update is left unchanged."""
        del sample_config["cron"]["autoUpdate"]
        sample_config["cron"]["update"] = "15 3 * * *"
        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "wb") as fh:
            tomli_w.dump(sample_config, fh)

        stream._apply_auto_update_config_defaults()

        with open(config_path, "rb") as fh:
            result = tomllib.load(fh)
        assert result["cron"]["autoUpdate"] is False
        assert result["cron"]["update"] == "15 3 * * *"

    def test_adds_missing_update_schedule_only(self, tmp_script_dir, sample_config):
        """When only update is missing, it is added; autoUpdate is left unchanged."""
        sample_config["cron"]["autoUpdate"] = True
        del sample_config["cron"]["update"]
        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "wb") as fh:
            tomli_w.dump(sample_config, fh)

        stream._apply_auto_update_config_defaults()

        with open(config_path, "rb") as fh:
            result = tomllib.load(fh)
        assert result["cron"]["autoUpdate"] is True
        assert result["cron"]["update"] == "0 0 * * *"

    def test_prints_message_when_migrating(self, tmp_script_dir, sample_config, capsys):
        """A message is printed when new keys are written."""
        del sample_config["cron"]["autoUpdate"]
        del sample_config["cron"]["update"]
        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "wb") as fh:
            tomli_w.dump(sample_config, fh)

        stream._apply_auto_update_config_defaults()

        captured = capsys.readouterr()
        assert "auto-update" in captured.out.lower()

    def test_no_print_when_no_migration_needed(self, tmp_script_dir, sample_config, capsys):
        """No message is printed when both keys are already present."""
        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "wb") as fh:
            tomli_w.dump(sample_config, fh)

        stream._apply_auto_update_config_defaults()

        captured = capsys.readouterr()
        assert captured.out == ""


# ── Rollback — extract version ──────────────────────────────────────────────


class TestExtractVersion:
    def test_extract_version(self):
        """Extracts 'v0.1.5' from a backup filename."""
        result = stream._extract_version_from_backup(Path("stream.v0.1.5.bak.zip"))
        assert result == "v0.1.5"

    def test_extract_version_dev(self):
        """Extracts 'dev' from a backup filename."""
        result = stream._extract_version_from_backup(Path("stream.dev.bak.zip"))
        assert result == "dev"


# ── Rollback — list available backups ───────────────────────────────────────


class TestListAvailableBackups:
    def test_list_available_backups_sorted(self, tmp_script_dir):
        """Backups are returned newest-first (reverse sorted)."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()

        names = ["stream.v0.1.3.bak.zip", "stream.v0.1.5.bak.zip", "stream.v0.1.4.bak.zip"]
        for name in names:
            path = backup_dir / name
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("stream.py", "# dummy")

        result = stream._list_available_backups()
        result_names = [p.name for p in result]
        assert result_names == sorted(names, reverse=True)

    def test_list_available_backups_empty(self, tmp_script_dir):
        """When no backup zips exist, an empty list is returned."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()

        result = stream._list_available_backups()
        assert result == []


# ── Rollback — find backup by version ───────────────────────────────────────


class TestFindBackupByVersion:
    def test_find_backup_by_version_found(self, tmp_script_dir):
        """Finds the backup zip matching the requested version."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()

        target = backup_dir / "stream.v0.1.5.bak.zip"
        with zipfile.ZipFile(target, "w") as zf:
            zf.writestr("stream.py", "# v0.1.5")

        result = stream._find_backup_by_version("v0.1.5")
        assert result is not None
        assert result.name == "stream.v0.1.5.bak.zip"

    def test_find_backup_by_version_not_found(self, tmp_script_dir):
        """Returns None when no backup matches the version."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()

        result = stream._find_backup_by_version("v9.9.9")
        assert result is None


# ── Rollback — restore from backup ─────────────────────────────────────────


class TestRestoreFromBackup:
    def test_restore_from_backup(self, tmp_script_dir):
        """Extracting a backup zip places files into SCRIPT_DIR."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()

        resources_bytes = tomli_w.dumps({"restored": True}).encode()
        backup_zip = backup_dir / "stream.v0.1.5.bak.zip"
        with zipfile.ZipFile(backup_zip, "w") as zf:
            zf.writestr("stream.py", "# restored content")
            zf.writestr("resources.toml", resources_bytes)

        stream._restore_from_backup(backup_zip)

        restored_script = tmp_script_dir / "stream.py"
        restored_resources = tmp_script_dir / "resources.toml"

        assert restored_script.exists()
        assert restored_script.read_text() == "# restored content"
        assert restored_resources.exists()
        with open(restored_resources, "rb") as fh:
            assert tomllib.load(fh) == {"restored": True}


# ── do_rollback ─────────────────────────────────────────────────────────────


class TestDoRollback:
    def test_do_rollback_no_backups(self, tmp_script_dir, capsys, sample_resources):
        """When the backup directory is empty, prints 'No backups' message."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()

        with patch("stream.load_resources", return_value=sample_resources):
            stream.do_rollback()

        captured = capsys.readouterr()
        assert "no backup" in captured.out.lower() or "No backup" in captured.out

    def test_do_rollback_with_version(self, tmp_script_dir, capsys, sample_resources):
        """Providing a version restores files from the matching backup."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()

        backup_zip = backup_dir / "stream.v0.1.5.bak.zip"
        with zipfile.ZipFile(backup_zip, "w") as zf:
            zf.writestr("stream.py", "# v0.1.5 content")
            zf.writestr("resources.toml", tomli_w.dumps({"version": "v0.1.5"}))

        with patch("stream.load_resources", return_value=sample_resources):
            stream.do_rollback("v0.1.5")

        assert (tmp_script_dir / "stream.py").read_text() == "# v0.1.5 content"

    def test_do_rollback_version_not_found(self, tmp_script_dir, capsys, sample_resources):
        """When the requested version has no backup, prints an error."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()

        # Create a different version backup so the directory isn't empty
        other_zip = backup_dir / "stream.v0.1.0.bak.zip"
        with zipfile.ZipFile(other_zip, "w") as zf:
            zf.writestr("stream.py", "# old")

        with patch("stream.load_resources", return_value=sample_resources):
            stream.do_rollback("v9.9.9")

        captured = capsys.readouterr()
        assert "v9.9.9" in captured.out or "not found" in captured.out.lower() or "No backup" in captured.out
