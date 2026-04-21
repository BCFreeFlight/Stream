"""Shared pytest fixtures for bcfreeflight_stream tests."""

import copy

import pytest
from unittest.mock import MagicMock

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
import tomli_w


# ── Module Import ────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def stream():
    """Import and return the stream module from src/stream.py."""
    import stream as _stream

    return _stream


# ── Global State Reset ───────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_globals(stream):
    """Reset mutable module-level state after every test."""
    yield
    stream._config = None
    stream._ffmpeg_process = None
    stream._stop_requested = False


# ── Temporary Script Directory ───────────────────────────────────────────────


@pytest.fixture
def tmp_script_dir(monkeypatch, stream, tmp_path):
    """Point stream.SCRIPT_DIR at a temp directory for the duration of the test."""
    monkeypatch.setattr(stream, "SCRIPT_DIR", tmp_path)
    return tmp_path


# ── Sample Data ──────────────────────────────────────────────────────────────


@pytest.fixture
def sample_config():
    """Return a deep copy of a full config dict matching the config.json schema."""
    config = {
        "google": {
            "clientId": "test-id",
        },
        "stream": {
            "rtspUrl": "rtsp://cam.local/live",
            "videoCodec": "copy",
            "audioCodec": "copy",
            "mute": True,
        },
        "youtube": {
            "broadcastTitle": "Test: {date}",
            "privacy": "public",
            "categoryId": "22",
            "enableMonitorStream": False,
            "embeddable": True,
            "broadcastId": "bcast-123",
            "streamURL": "rtmp://a.rtmp.youtube.com/live2",
            "backupStreamUrl": "rtmp://b.rtmp.youtube.com/live2?backup=1",
            "streamKey": "xxxx-yyyy-zzzz",
        },
        "pidFile": "./stream.pid",
        "stopSentinel": "./stream.stop",
        "logDir": "./logs",
        "logRetentionDays": 15,
        "retryDelaySecs": 5,
        "terminal": "gnome-terminal",
        "cron": {
            "enabled": True,
            "start": "30 6 * * *",
            "stop": "25 18 * * *",
            "autoUpdate": False,
            "update": "0 0 * * *",
        },
    }
    return copy.deepcopy(config)


@pytest.fixture(scope="session")
def sample_resources(stream):
    """Read and return the parsed contents of src/resources.toml."""
    import pathlib

    resources_path = pathlib.Path(__file__).resolve().parent.parent / "src" / "resources.toml"
    with open(resources_path, "rb") as fh:
        return tomllib.load(fh)


# ── Mock Objects ─────────────────────────────────────────────────────────────


@pytest.fixture
def mock_logger():
    """Return a MagicMock logger with the expected interface."""
    return MagicMock(spec=["info", "warn", "error", "close", "cleanup_old_logs"])


@pytest.fixture
def mock_youtube():
    """Return a MagicMock configured for YouTube Data API v3 call chains.

    Supports chained calls such as:
        mock_youtube.liveBroadcasts().insert().execute()
        mock_youtube.liveBroadcasts().list().execute()
        mock_youtube.liveBroadcasts().bind().execute()
        mock_youtube.liveBroadcasts().transition().execute()
        mock_youtube.liveBroadcasts().update().execute()
        mock_youtube.liveStreams().insert().execute()
        mock_youtube.liveStreams().list().execute()
        mock_youtube.videos().list().execute()
        mock_youtube.videos().update().execute()
    """
    yt = MagicMock()

    # liveBroadcasts chains
    broadcasts = MagicMock()
    broadcasts.insert.return_value.execute.return_value = {}
    broadcasts.list.return_value.execute.return_value = {"items": []}
    broadcasts.bind.return_value.execute.return_value = {}
    broadcasts.transition.return_value.execute.return_value = {}
    broadcasts.update.return_value.execute.return_value = {}
    broadcasts.delete.return_value.execute.return_value = {}
    yt.liveBroadcasts.return_value = broadcasts

    # liveStreams chains
    streams = MagicMock()
    streams.insert.return_value.execute.return_value = {}
    streams.list.return_value.execute.return_value = {"items": []}
    yt.liveStreams.return_value = streams

    # videos chains
    videos = MagicMock()
    videos.list.return_value.execute.return_value = {"items": []}
    videos.update.return_value.execute.return_value = {}
    yt.videos.return_value = videos

    return yt


# ── On-Disk Config / Env ─────────────────────────────────────────────────────


@pytest.fixture
def config_on_disk(tmp_script_dir, sample_config):
    """Write sample_config as config.toml in the temp script directory."""
    path = tmp_script_dir / "config.toml"
    with open(path, "wb") as fh:
        tomli_w.dump(sample_config, fh)
    return path


@pytest.fixture
def env_on_disk(tmp_script_dir):
    """Write a sample .env file in the temp script directory."""
    path = tmp_script_dir / ".env"
    path.write_text(
        "GOOGLE_CLIENT_SECRET=test-secret\n"
        "GOOGLE_REFRESH_TOKEN=test-refresh\n"
        "GOOGLE_ACCESS_TOKEN=test-access\n"
    )
    return path
