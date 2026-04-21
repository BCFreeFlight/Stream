"""Tests for config/env/resources loading, _get_nested, and asset auto-download."""

import json
import os
from unittest.mock import patch, MagicMock

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
import tomli_w

import stream


# ── load_config ──────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_load_config_reads_toml(self, tmp_script_dir, sample_config):
        """Writing config.toml then calling load_config returns the same dict."""
        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "wb") as fh:
            tomli_w.dump(sample_config, fh)

        result = stream.load_config()
        assert result == sample_config

    def test_load_config_missing_file_raises(self, tmp_script_dir):
        """load_config raises FileNotFoundError when config.toml does not exist."""
        import pytest

        with pytest.raises(FileNotFoundError):
            stream.load_config()


# ── save_config ──────────────────────────────────────────────────────────────


class TestSaveConfig:
    def test_save_config_writes_toml(self, tmp_script_dir, sample_config):
        """save_config writes a valid TOML file that can be read back."""
        stream.save_config(sample_config)

        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "rb") as fh:
            result = tomllib.load(fh)

        assert result == sample_config

    def test_save_config_includes_comments(self, tmp_script_dir, sample_config):
        """save_config writes TOML with inline comments."""
        stream.save_config(sample_config)

        config_path = tmp_script_dir / "config.toml"
        content = config_path.read_text()

        assert "# Path to the PID file" in content
        assert "# Google OAuth 2.0 credentials" in content

    def test_save_config_overwrites(self, tmp_script_dir, sample_config):
        """Calling save_config twice keeps only the second value."""
        stream.save_config(sample_config)

        sample_config["google"]["clientId"] = "overwritten-id"
        stream.save_config(sample_config)

        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "rb") as fh:
            result = tomllib.load(fh)

        assert result["google"]["clientId"] == "overwritten-id"


# ── load_env / save_env_value ────────────────────────────────────────────────


class TestEnv:
    def test_load_env_sets_environ(self, tmp_script_dir, env_on_disk):
        """load_env populates os.environ from the .env file."""
        stream.load_env()

        assert os.environ.get("GOOGLE_CLIENT_SECRET") == "test-secret"
        assert os.environ.get("GOOGLE_REFRESH_TOKEN") == "test-refresh"
        assert os.environ.get("GOOGLE_ACCESS_TOKEN") == "test-access"

    def test_save_env_value_creates_key(self, tmp_script_dir):
        """save_env_value creates a new key in the .env file."""
        env_path = tmp_script_dir / ".env"
        env_path.write_text("")

        stream.save_env_value("NEW_KEY", "new-value")

        content = env_path.read_text()
        assert "NEW_KEY" in content
        assert "new-value" in content

    def test_save_env_value_updates_key(self, tmp_script_dir):
        """save_env_value updates an existing key in the .env file."""
        env_path = tmp_script_dir / ".env"
        env_path.write_text("MY_KEY=old-value\n")

        stream.save_env_value("MY_KEY", "updated-value")

        content = env_path.read_text()
        assert "updated-value" in content
        assert "old-value" not in content


# ── load_resources ───────────────────────────────────────────────────────────


class TestReleaseAssetUrl:
    def test_release_asset_url_dev(self):
        """Dev builds use the 'latest' download URL."""
        with patch.object(stream, "__version__", "dev"):
            url = stream._release_asset_url("resources.toml")

        assert "/releases/latest/download/resources.toml" in url
        assert stream.GITHUB_REPO in url

    def test_release_asset_url_tagged(self):
        """Tagged releases use the version-specific download URL."""
        with patch.object(stream, "__version__", "v0.1.5"):
            url = stream._release_asset_url("resources.toml")

        assert "/releases/download/v0.1.5/resources.toml" in url
        assert stream.GITHUB_REPO in url


class TestEnsureReleaseAsset:
    def test_returns_existing_file(self, tmp_script_dir):
        """When the file already exists, returns its path without downloading."""
        path = tmp_script_dir / "resources.toml"
        path.write_text('{"existing": true}')

        with patch("urllib.request.urlretrieve") as mock_retrieve:
            result = stream._ensure_release_asset("resources.toml")

        mock_retrieve.assert_not_called()
        assert result == path

    def test_downloads_missing_file(self, tmp_script_dir):
        """When the file is missing, downloads it from the release URL."""
        def fake_download(url, dest):
            dest.write_text('{"downloaded": true}') if hasattr(dest, 'write_text') else open(dest, 'w').close()

        with patch("urllib.request.urlretrieve") as mock_retrieve:
            mock_retrieve.side_effect = lambda url, dest: open(dest, 'w').close()
            result = stream._ensure_release_asset("resources.toml")

        mock_retrieve.assert_called_once()
        url_arg = mock_retrieve.call_args[0][0]
        assert "resources.toml" in url_arg
        assert result == tmp_script_dir / "resources.toml"

    def test_downloads_from_version_url(self, tmp_script_dir):
        """Downloaded URL matches the current __version__."""
        with patch.object(stream, "__version__", "v0.2.0"), \
             patch("urllib.request.urlretrieve") as mock_retrieve:
            mock_retrieve.side_effect = lambda url, dest: open(dest, 'w').close()
            stream._ensure_release_asset("resources.toml")

        url_arg = mock_retrieve.call_args[0][0]
        assert "/releases/download/v0.2.0/resources.toml" in url_arg


class TestLoadResources:
    def test_load_resources_reads_toml(self, tmp_script_dir):
        """load_resources reads and parses resources.toml from SCRIPT_DIR."""
        resources_data = {"install": {"header": "test"}, "errors": {}}
        resources_path = tmp_script_dir / "resources.toml"
        with open(resources_path, "wb") as fh:
            tomli_w.dump(resources_data, fh)

        result = stream.load_resources()
        assert result == resources_data

    def test_load_resources_downloads_when_missing(self, tmp_script_dir, sample_resources):
        """load_resources auto-downloads resources.toml when it is absent."""
        def fake_download(url, dest):
            with open(dest, "wb") as fh:
                tomli_w.dump(sample_resources, fh)

        with patch("urllib.request.urlretrieve", side_effect=fake_download):
            result = stream.load_resources()

        assert result == sample_resources


# ── _get_nested ──────────────────────────────────────────────────────────────


class TestGetNested:
    def test_get_nested_simple_path(self):
        """Traversing a two-level path returns the leaf value."""
        data = {"a": {"b": "val"}}
        assert stream._get_nested(data, "a", "b") == "val"

    def test_get_nested_missing_key(self):
        """A missing key returns the empty-string default."""
        data = {"a": {"b": "val"}}
        assert stream._get_nested(data, "a", "missing") == ""

    def test_get_nested_custom_default(self):
        """A missing key with default='X' returns 'X'."""
        data = {"a": {"b": "val"}}
        assert stream._get_nested(data, "a", "missing", default="X") == "X"

    def test_get_nested_non_dict_intermediate(self):
        """If an intermediate value is not a dict, return the default."""
        data = {"a": "not-a-dict"}
        assert stream._get_nested(data, "a", "b") == ""

    def test_get_nested_none_value(self):
        """If the leaf value is None, return the default instead."""
        data = {"a": {"b": None}}
        assert stream._get_nested(data, "a", "b") == ""


# ── _try_load_existing_config ────────────────────────────────────────────────


class TestTryLoadExistingConfig:
    def test_try_load_existing_config_toml(self, tmp_script_dir, sample_config):
        """Returns the parsed dict when config.toml exists and is valid."""
        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "wb") as fh:
            tomli_w.dump(sample_config, fh)

        result = stream._try_load_existing_config()
        assert result == sample_config

    def test_try_load_existing_config_json_fallback(self, tmp_script_dir, sample_config):
        """Falls back to config.json when config.toml is absent (migration)."""
        config_path = tmp_script_dir / "config.json"
        with open(config_path, "w") as fh:
            json.dump(sample_config, fh)

        result = stream._try_load_existing_config()
        assert result == sample_config

    def test_try_load_existing_config_missing(self, tmp_script_dir):
        """Returns None when neither config file exists."""
        result = stream._try_load_existing_config()
        assert result is None

    def test_try_load_existing_config_corrupt(self, tmp_script_dir):
        """Returns None when config.toml contains invalid TOML."""
        config_path = tmp_script_dir / "config.toml"
        config_path.write_text("[not valid toml!!!")

        result = stream._try_load_existing_config()
        assert result is None


# ── _deep_merge_defaults ─────────────────────────────────────────────────────


class TestDeepMergeDefaults:
    def test_fills_in_missing_top_level_key(self):
        """A key present in defaults but absent from config is added."""
        defaults = {"a": 1, "b": 2}
        config = {"a": 99}
        result = stream._deep_merge_defaults(defaults, config)
        assert result == {"a": 99, "b": 2}

    def test_preserves_existing_user_values(self):
        """Values already set by the user are never overwritten."""
        defaults = {"key": "default-value"}
        config = {"key": "user-value"}
        result = stream._deep_merge_defaults(defaults, config)
        assert result["key"] == "user-value"

    def test_fills_in_missing_nested_key(self):
        """A key missing from a nested section is filled in from defaults."""
        defaults = {"section": {"a": 1, "b": 2}}
        config = {"section": {"a": 99}}
        result = stream._deep_merge_defaults(defaults, config)
        assert result["section"]["b"] == 2
        assert result["section"]["a"] == 99

    def test_preserves_extra_user_keys_not_in_defaults(self):
        """Keys the user added that are not in defaults are kept unchanged."""
        defaults = {"a": 1}
        config = {"a": 1, "extra": "user-added"}
        result = stream._deep_merge_defaults(defaults, config)
        assert result["extra"] == "user-added"

    def test_does_not_mutate_inputs(self):
        """Neither defaults nor config are modified in place."""
        import copy
        defaults = {"a": 1, "nested": {"x": 10}}
        config = {"nested": {"y": 20}}
        defaults_copy = copy.deepcopy(defaults)
        config_copy = copy.deepcopy(config)
        stream._deep_merge_defaults(defaults, config)
        assert defaults == defaults_copy
        assert config == config_copy

    def test_empty_config_returns_all_defaults(self):
        """An empty config dict is filled entirely from defaults."""
        defaults = {"a": 1, "b": {"c": 2}}
        result = stream._deep_merge_defaults(defaults, {})
        assert result == defaults

    def test_empty_defaults_returns_config_unchanged(self):
        """Empty defaults leaves config untouched."""
        config = {"a": 99}
        result = stream._deep_merge_defaults({}, config)
        assert result == config


# ── _migrate_config ──────────────────────────────────────────────────────────


class TestMigrateConfig:
    def test_no_op_when_config_missing(self, tmp_script_dir):
        """Does nothing and does not raise when config.toml does not exist."""
        stream._migrate_config()  # should not raise

    def test_no_op_when_config_corrupt(self, tmp_script_dir):
        """Does nothing and does not raise when config.toml is unparseable."""
        (tmp_script_dir / "config.toml").write_text("[not valid toml!!!")
        stream._migrate_config()  # should not raise

    def test_no_op_when_config_already_complete(self, tmp_script_dir, sample_config, capsys):
        """Does not rewrite config.toml when no keys are missing."""
        original_mtime = None
        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "wb") as fh:
            tomli_w.dump(sample_config, fh)
        original_mtime = config_path.stat().st_mtime

        stream._migrate_config()

        assert config_path.stat().st_mtime == original_mtime
        assert "migrated" not in capsys.readouterr().out

    def test_adds_missing_top_level_key(self, tmp_script_dir, sample_config, capsys):
        """Writes back config.toml with the missing key filled in from defaults."""
        del sample_config["retryDelaySecs"]
        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "wb") as fh:
            tomli_w.dump(sample_config, fh)

        stream._migrate_config()

        result = stream.load_config()
        assert result["retryDelaySecs"] == stream.CONFIG_DEFAULTS["retryDelaySecs"]
        assert "migrated" in capsys.readouterr().out

    def test_adds_missing_nested_key(self, tmp_script_dir, sample_config, capsys):
        """Fills in a missing key inside a nested section."""
        del sample_config["youtube"]["backupStreamUrl"]
        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "wb") as fh:
            tomli_w.dump(sample_config, fh)

        stream._migrate_config()

        result = stream.load_config()
        assert result["youtube"]["backupStreamUrl"] == stream.CONFIG_DEFAULTS["youtube"]["backupStreamUrl"]
        assert "migrated" in capsys.readouterr().out

    def test_preserves_user_values_when_migrating(self, tmp_script_dir, sample_config):
        """Existing user values are never overwritten during migration."""
        del sample_config["retryDelaySecs"]
        sample_config["youtube"]["broadcastId"] = "my-real-broadcast-id"
        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "wb") as fh:
            tomli_w.dump(sample_config, fh)

        stream._migrate_config()

        result = stream.load_config()
        assert result["youtube"]["broadcastId"] == "my-real-broadcast-id"

    def test_supersedes_apply_auto_update_config_defaults(self, tmp_script_dir, sample_config):
        """Config missing autoUpdate/update cron keys is migrated correctly."""
        del sample_config["cron"]["autoUpdate"]
        del sample_config["cron"]["update"]
        config_path = tmp_script_dir / "config.toml"
        with open(config_path, "wb") as fh:
            tomli_w.dump(sample_config, fh)

        stream._migrate_config()

        result = stream.load_config()
        assert result["cron"]["autoUpdate"] is False
        assert result["cron"]["update"] == "0 0 * * *"
