"""Tests for config/env/resources loading and _get_nested."""

import json
import os

import stream


# ── load_config ──────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_load_config_reads_json(self, tmp_script_dir, sample_config):
        """Writing config.json then calling load_config returns the same dict."""
        config_path = tmp_script_dir / "config.json"
        with open(config_path, "w") as fh:
            json.dump(sample_config, fh)

        result = stream.load_config()
        assert result == sample_config

    def test_load_config_missing_file_raises(self, tmp_script_dir):
        """load_config raises FileNotFoundError when config.json does not exist."""
        import pytest

        with pytest.raises(FileNotFoundError):
            stream.load_config()


# ── save_config ──────────────────────────────────────────────────────────────


class TestSaveConfig:
    def test_save_config_writes_json(self, tmp_script_dir, sample_config):
        """save_config writes a valid JSON file that can be read back."""
        stream.save_config(sample_config)

        config_path = tmp_script_dir / "config.json"
        with open(config_path, "r") as fh:
            result = json.load(fh)

        assert result == sample_config

    def test_save_config_overwrites(self, tmp_script_dir, sample_config):
        """Calling save_config twice keeps only the second value."""
        stream.save_config(sample_config)

        sample_config["google"]["clientId"] = "overwritten-id"
        stream.save_config(sample_config)

        config_path = tmp_script_dir / "config.json"
        with open(config_path, "r") as fh:
            result = json.load(fh)

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


class TestLoadResources:
    def test_load_resources_reads_json(self, tmp_script_dir):
        """load_resources reads and parses resources.json from SCRIPT_DIR."""
        resources_data = {"install": {"header": "test"}, "errors": {}}
        resources_path = tmp_script_dir / "resources.json"
        with open(resources_path, "w") as fh:
            json.dump(resources_data, fh)

        result = stream.load_resources()
        assert result == resources_data

    def test_load_resources_missing_raises(self, tmp_script_dir):
        """load_resources raises FileNotFoundError when resources.json is absent."""
        import pytest

        with pytest.raises(FileNotFoundError):
            stream.load_resources()


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
    def test_try_load_existing_config_present(self, tmp_script_dir, sample_config):
        """Returns the parsed dict when config.json exists and is valid."""
        config_path = tmp_script_dir / "config.json"
        with open(config_path, "w") as fh:
            json.dump(sample_config, fh)

        result = stream._try_load_existing_config()
        assert result == sample_config

    def test_try_load_existing_config_missing(self, tmp_script_dir):
        """Returns None when config.json does not exist."""
        result = stream._try_load_existing_config()
        assert result is None

    def test_try_load_existing_config_corrupt(self, tmp_script_dir):
        """Returns None when config.json contains invalid JSON."""
        config_path = tmp_script_dir / "config.json"
        config_path.write_text("{not valid json!!!")

        result = stream._try_load_existing_config()
        assert result is None
