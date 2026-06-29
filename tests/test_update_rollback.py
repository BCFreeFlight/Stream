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
             patch("stream._migrate_config"):
            stream.do_update()

        captured = capsys.readouterr()
        assert "already" in captured.out.lower()

    def test_do_update_fetch_failed(self, capsys, sample_resources):
        """When fetching the latest tag fails, prints an error."""
        with patch.object(stream, "__version__", "v0.1.4"), \
             patch("stream._get_latest_release_tag", return_value=None), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._migrate_config"):
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
             patch("stream._migrate_config"):
            stream.do_update()

        mock_backup.assert_called_once()
        download_calls = [call[0][0] for call in mock_download.call_args_list]
        assert "stream.py" in download_calls
        assert "resources.toml" in download_calls

    def test_do_update_calls_migration(self, sample_resources):
        """do_update calls _migrate_config before downloading."""
        with patch.object(stream, "__version__", "v0.1.4"), \
             patch("stream._get_latest_release_tag", return_value="v0.1.4"), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._migrate_config") as mock_migrate:
            stream.do_update()

        mock_migrate.assert_called_once()

    def test_do_update_registers_cron_on_success(self, tmp_script_dir, sample_config, sample_resources):
        """After a successful download, do_update re-registers cron entries when cron is enabled."""
        (tmp_script_dir / "stream.py").write_text("# old")
        (tmp_script_dir / "resources.toml").write_text("")

        with patch.object(stream, "__version__", "v0.1.4"), \
             patch("stream._get_latest_release_tag", return_value="v0.1.5"), \
             patch("stream._backup_current_files", return_value=tmp_script_dir / "backup" / "stream.v0.1.4.bak.zip"), \
             patch("stream._download_release_asset"), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._migrate_config"), \
             patch("stream.load_config", return_value=sample_config) as mock_load_config, \
             patch("stream.register_cron_entries") as mock_register:
            stream.do_update()

        mock_load_config.assert_called_once()
        mock_register.assert_called_once_with(sample_config)

    def test_do_update_passes_custom_cron_schedule(self, tmp_script_dir, sample_config, sample_resources):
        """do_update passes the user's custom cron schedule to register_cron_entries."""
        sample_config["cron"]["start"] = "0 8 * * *"
        sample_config["cron"]["stop"] = "0 20 * * *"
        (tmp_script_dir / "stream.py").write_text("# old")
        (tmp_script_dir / "resources.toml").write_text("")

        with patch.object(stream, "__version__", "v0.1.4"), \
             patch("stream._get_latest_release_tag", return_value="v0.1.5"), \
             patch("stream._backup_current_files", return_value=tmp_script_dir / "backup" / "x.zip"), \
             patch("stream._download_release_asset"), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._migrate_config"), \
             patch("stream.load_config", return_value=sample_config), \
             patch("stream.register_cron_entries") as mock_register:
            stream.do_update()

        called_config = mock_register.call_args[0][0]
        assert called_config["cron"]["start"] == "0 8 * * *"
        assert called_config["cron"]["stop"] == "0 20 * * *"

    def test_do_update_skips_cron_when_disabled(self, tmp_script_dir, sample_config, sample_resources):
        """do_update does not call register_cron_entries when cron.enabled is False."""
        (tmp_script_dir / "stream.py").write_text("# old")
        (tmp_script_dir / "resources.toml").write_text("")
        sample_config["cron"]["enabled"] = False

        with patch.object(stream, "__version__", "v0.1.4"), \
             patch("stream._get_latest_release_tag", return_value="v0.1.5"), \
             patch("stream._backup_current_files", return_value=tmp_script_dir / "backup" / "stream.v0.1.4.bak.zip"), \
             patch("stream._download_release_asset"), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._migrate_config"), \
             patch("stream.load_config", return_value=sample_config), \
             patch("stream.register_cron_entries") as mock_register:
            stream.do_update()

        mock_register.assert_not_called()

    def test_do_update_no_cron_when_already_latest(self, sample_config, sample_resources):
        """do_update does not call register_cron_entries when already on the latest version."""
        with patch.object(stream, "__version__", "v0.1.5"), \
             patch("stream._get_latest_release_tag", return_value="v0.1.5"), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._migrate_config"), \
             patch("stream.load_config", return_value=sample_config), \
             patch("stream.register_cron_entries") as mock_register:
            stream.do_update()

        mock_register.assert_not_called()

    def test_do_update_no_cron_when_download_fails(self, tmp_script_dir, sample_config, sample_resources):
        """do_update does not call register_cron_entries if a download fails."""
        (tmp_script_dir / "stream.py").write_text("# old")
        (tmp_script_dir / "resources.toml").write_text("")

        with patch.object(stream, "__version__", "v0.1.4"), \
             patch("stream._get_latest_release_tag", return_value="v0.1.5"), \
             patch("stream._backup_current_files", return_value=tmp_script_dir / "backup" / "stream.v0.1.4.bak.zip"), \
             patch("stream._download_release_asset", side_effect=Exception("network error")), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._migrate_config"), \
             patch("stream.load_config", return_value=sample_config), \
             patch("stream.register_cron_entries") as mock_register:
            stream.do_update()

        mock_register.assert_not_called()

    def test_do_update_survives_load_config_failure(self, tmp_script_dir, sample_resources):
        """do_update completes successfully even if load_config raises (e.g. no config.toml)."""
        (tmp_script_dir / "stream.py").write_text("# old")
        (tmp_script_dir / "resources.toml").write_text("")

        with patch.object(stream, "__version__", "v0.1.4"), \
             patch("stream._get_latest_release_tag", return_value="v0.1.5"), \
             patch("stream._backup_current_files", return_value=tmp_script_dir / "backup" / "stream.v0.1.4.bak.zip"), \
             patch("stream._download_release_asset"), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._migrate_config"), \
             patch("stream.load_config", side_effect=FileNotFoundError("no config.toml")), \
             patch("stream.register_cron_entries") as mock_register:
            stream.do_update()  # must not raise

        mock_register.assert_not_called()

    def test_do_update_survives_register_cron_failure(self, tmp_script_dir, sample_config, sample_resources):
        """do_update completes successfully even if register_cron_entries raises."""
        (tmp_script_dir / "stream.py").write_text("# old")
        (tmp_script_dir / "resources.toml").write_text("")

        with patch.object(stream, "__version__", "v0.1.4"), \
             patch("stream._get_latest_release_tag", return_value="v0.1.5"), \
             patch("stream._backup_current_files", return_value=tmp_script_dir / "backup" / "stream.v0.1.4.bak.zip"), \
             patch("stream._download_release_asset"), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._migrate_config"), \
             patch("stream.load_config", return_value=sample_config), \
             patch("stream.register_cron_entries", side_effect=Exception("crontab failed")):
            stream.do_update()  # must not raise


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

    def test_do_rollback_cancelled(self, tmp_script_dir, capsys, sample_resources):
        """When _prompt_backup_selection returns None (user chose 'q'), prints cancelled message and restores nothing."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()

        # Create a backup so the directory isn't empty (otherwise it takes the 'no backups' path)
        backup_zip = backup_dir / "stream.v0.1.5.bak.zip"
        with zipfile.ZipFile(backup_zip, "w") as zf:
            zf.writestr("stream.py", "# backup content")

        with patch.object(stream, "_prompt_backup_selection", return_value=None), \
             patch("stream.load_resources", return_value=sample_resources):
            stream.do_rollback()

        captured = capsys.readouterr()
        assert "cancelled" in captured.out.lower()
        # No files should have been restored — stream.py should not exist (we never wrote one)
        assert not (tmp_script_dir / "stream.py").exists()


# ── Version comparison helpers ───────────────────────────────────────────────


class TestParseVersion:
    def test_parse_standard_tag(self):
        """'v1.0.20' parses to (1, 0, 20)."""
        assert stream._parse_version("v1.0.20") == (1, 0, 20)

    def test_parse_no_prefix(self):
        """'1.2.3' (no v) parses to (1, 2, 3)."""
        assert stream._parse_version("1.2.3") == (1, 2, 3)

    def test_parse_dev_returns_zeros(self):
        """Non-numeric tag returns (0, 0, 0)."""
        assert stream._parse_version("dev") == (0, 0, 0)

    def test_parse_empty_returns_zeros(self):
        """Empty string returns (0, 0, 0)."""
        assert stream._parse_version("") == (0, 0, 0)

    def test_parse_none_returns_zeros(self):
        """None returns (0, 0, 0)."""
        assert stream._parse_version(None) == (0, 0, 0)


class TestVersionGt:
    def test_newer_is_gt(self):
        """v1.0.21 > v1.0.20."""
        assert stream._version_gt("v1.0.21", "v1.0.20")

    def test_equal_is_not_gt(self):
        """v1.0.20 is not > v1.0.20."""
        assert not stream._version_gt("v1.0.20", "v1.0.20")

    def test_older_is_not_gt(self):
        """v1.0.19 is not > v1.0.20."""
        assert not stream._version_gt("v1.0.19", "v1.0.20")

    def test_minor_version_bump(self):
        """v1.1.0 > v1.0.99."""
        assert stream._version_gt("v1.1.0", "v1.0.99")

    def test_major_version_bump(self):
        """v2.0.0 > v1.9.9."""
        assert stream._version_gt("v2.0.0", "v1.9.9")


# ── _prompt_backup_selection — interactive input handling ─────────────────────


class TestPromptBackupSelection:
    def test_prompt_returns_none_on_quit(self, tmp_script_dir):
        """User enters 'q' → function returns None."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()

        backup_zip = backup_dir / "stream.v0.1.5.bak.zip"
        with zipfile.ZipFile(backup_zip, "w") as zf:
            zf.writestr("stream.py", "# dummy")

        res = {"rollback": {}}
        with patch("builtins.input", return_value="q"):
            result = stream._prompt_backup_selection([backup_zip], res)

        assert result is None

    def test_prompt_returns_valid_index(self, tmp_script_dir):
        """User enters a valid 1-based index → returns the matching backup Path."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()

        zip1 = backup_dir / "stream.v0.1.5.bak.zip"
        zip2 = backup_dir / "stream.v0.1.6.bak.zip"
        for z in (zip1, zip2):
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("stream.py", "# dummy")

        res = {"rollback": {}}
        with patch("builtins.input", return_value="2"):
            result = stream._prompt_backup_selection([zip1, zip2], res)

        assert result == zip2

    def test_prompt_reprompts_on_non_numeric(self, tmp_script_dir):
        """User enters a non-numeric string → prints error, re-prompts with valid input."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()

        zip1 = backup_dir / "stream.v0.1.5.bak.zip"
        with zipfile.ZipFile(zip1, "w") as zf:
            zf.writestr("stream.py", "# dummy")

        res = {"rollback": {}}
        with patch("builtins.input", side_effect=["abc", "1"]):
            result = stream._prompt_backup_selection([zip1], res)

        assert result == zip1

    def test_prompt_reprompts_on_out_of_range(self, tmp_script_dir):
        """User enters an out-of-range number → prints error, re-prompts with valid input."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()

        zip1 = backup_dir / "stream.v0.1.5.bak.zip"
        with zipfile.ZipFile(zip1, "w") as zf:
            zf.writestr("stream.py", "# dummy")

        res = {"rollback": {}}
        with patch("builtins.input", side_effect=["99", "1"]):
            result = stream._prompt_backup_selection([zip1], res)

        assert result == zip1


class TestDoUpdateSkippedVersion:

    def test_no_skip_check_when_skipped_version_empty(
            self, tmp_script_dir, sample_config, sample_resources):
        """do_update proceeds normally when skippedVersion is empty string."""
        sample_config.setdefault("update", {})["skippedVersion"] = ""
        (tmp_script_dir / "stream.py").write_text("# old")
        (tmp_script_dir / "resources.toml").write_text("")

        with patch.object(stream, "__version__", "v0.1.4"), \
             patch("stream._get_latest_release_tag", return_value="v0.1.5"), \
             patch("stream._backup_current_files", return_value=tmp_script_dir / "backup" / "x.zip"), \
             patch("stream._download_release_asset") as mock_dl, \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream._migrate_config"), \
             patch("stream.load_config", return_value=sample_config), \
             patch("stream.save_config"), \
             patch("stream.register_cron_entries"):
            stream.do_update()

        assert mock_dl.call_count == 2


# ── do_rollback — skipped version marker ────────────────────────────────────


class TestDoRollbackSkippedVersion:
    def _make_backup(self, backup_dir, version, config_data=None):
        backup_zip = backup_dir / f"stream.{version}.bak.zip"
        with zipfile.ZipFile(backup_zip, "w") as zf:
            zf.writestr("stream.py", f"# {version} content")
            if config_data is not None:
                zf.writestr("config.toml", tomli_w.dumps(config_data))
        return backup_zip

    def test_rollback_sets_skipped_version(
            self, tmp_script_dir, sample_config, sample_resources):
        """do_rollback writes the rolled-back-from version into update.skippedVersion."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()
        self._make_backup(backup_dir, "v0.1.4", sample_config)

        (tmp_script_dir / "config.toml").write_bytes(tomli_w.dumps(sample_config).encode())

        with patch.object(stream, "__version__", "v0.1.5"), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream.save_config") as mock_save:
            stream.do_rollback("v0.1.4")

        saved = mock_save.call_args[0][0]
        assert saved.get("update", {}).get("skippedVersion") == "v0.1.5"

    def test_rollback_prints_skip_message(
            self, tmp_script_dir, capsys, sample_config, sample_resources):
        """do_rollback prints a message indicating which version will be skipped."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()
        self._make_backup(backup_dir, "v0.1.4", sample_config)

        (tmp_script_dir / "config.toml").write_bytes(tomli_w.dumps(sample_config).encode())

        with patch.object(stream, "__version__", "v0.1.5"), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream.save_config"):
            stream.do_rollback("v0.1.4")

        captured = capsys.readouterr()
        assert "v0.1.5" in captured.out

    def test_rollback_does_not_set_skipped_version_for_dev(
            self, tmp_script_dir, sample_config, sample_resources):
        """do_rollback does not write skippedVersion when rolling back from 'dev' build."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()
        self._make_backup(backup_dir, "v0.1.4", sample_config)

        (tmp_script_dir / "config.toml").write_bytes(tomli_w.dumps(sample_config).encode())

        with patch.object(stream, "__version__", "dev"), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream.save_config") as mock_save:
            stream.do_rollback("v0.1.4")

        mock_save.assert_not_called()

    def test_rollback_survives_save_config_failure(
            self, tmp_script_dir, capsys, sample_config, sample_resources):
        """do_rollback completes successfully even if save_config raises after restore."""
        backup_dir = tmp_script_dir / "backup"
        backup_dir.mkdir()
        self._make_backup(backup_dir, "v0.1.4", sample_config)

        (tmp_script_dir / "config.toml").write_bytes(tomli_w.dumps(sample_config).encode())

        with patch.object(stream, "__version__", "v0.1.5"), \
             patch("stream.load_resources", return_value=sample_resources), \
             patch("stream.save_config", side_effect=OSError("disk full")):
            stream.do_rollback("v0.1.4")  # must not raise

        assert (tmp_script_dir / "stream.py").read_text() == "# v0.1.4 content"
