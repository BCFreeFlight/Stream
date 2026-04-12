#!/usr/bin/env python3
"""Proxies an RTSP camera stream to YouTube Live via ffmpeg.

A single-file, self-contained script that:
  - Self-installs Python dependencies on first run
  - Manages YouTube broadcast lifecycle via the Data API v3
  - Proxies an RTSP camera feed to YouTube Live through ffmpeg
  - Retries automatically on failure
  - Self-registers daily cron jobs for start/stop
"""

# ── Dependency Bootstrap ─────────────────────────────────────────────────────

import subprocess
import sys


def _can_import(module_name):
    """Return True if the given module can be imported."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def _ensure_dependencies():
    """Install any missing Python packages via pip."""
    required = [
        ("google.auth", "google-auth"),
        ("google_auth_oauthlib", "google-auth-oauthlib"),
        ("googleapiclient", "google-api-python-client"),
        ("dotenv", "python-dotenv"),
        ("requests", "requests"),
    ]
    missing = [pkg for mod, pkg in required if not _can_import(mod)]
    if missing:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
        import importlib
        importlib.invalidate_caches()


_ensure_dependencies()

# ── Standard Library ─────────────────────────────────────────────────────────

import argparse
import datetime
import json
import os
import signal
import shutil
import time
from collections import namedtuple
from pathlib import Path

# ── Third-Party ──────────────────────────────────────────────────────────────

from dotenv import load_dotenv, set_key
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build as build_service
from googleapiclient.errors import HttpError

# ── Constants & Types ────────────────────────────────────────────────────────

__version__ = "dev"

GITHUB_REPO = "BCFreeFlight/Stream"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

SCRIPT_DIR = Path(__file__).resolve().parent

CRON_MARKER = "# bcfreeflight_stream"

BroadcastContext = namedtuple(
    "BroadcastContext",
    ["youtube", "broadcast_id", "stream_id", "rtmp_url", "stream_key"],
)

# ── Process State (minimal globals for signal handler) ───────────────────────

_config = None
_ffmpeg_process = None
_stop_requested = False


# ── Configuration ────────────────────────────────────────────────────────────


def load_config():
    """Read and return the config.json file from the script directory."""
    with open(SCRIPT_DIR / "config.json", "r") as fh:
        return json.load(fh)


def save_config(config):
    """Write config.json to the script directory."""
    with open(SCRIPT_DIR / "config.json", "w") as fh:
        json.dump(config, fh, indent=2)


def load_env():
    """Load environment variables from the .env file."""
    load_dotenv(SCRIPT_DIR / ".env", override=True)


def save_env_value(key, value):
    """Write or update a single key in the .env file."""
    set_key(str(SCRIPT_DIR / ".env"), key, value)


def load_resources():
    """Load user-facing strings from resources.json."""
    with open(SCRIPT_DIR / "resources.json", "r") as fh:
        return json.load(fh)


# ── Logging ──────────────────────────────────────────────────────────────────


class Logger:
    """Writes timestamped log lines to a daily file and mirrors them to stdout."""

    def __init__(self, log_dir, retention_days):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self._log_file = self.log_dir / f"{datetime.date.today().isoformat()}.log"
        self._fh = open(self._log_file, "a")

    def info(self, message):
        self._write("INFO", message)

    def warn(self, message):
        self._write("WARN", message)

    def error(self, message):
        self._write("ERROR", message)

    def cleanup_old_logs(self):
        """Delete log files older than the configured retention period."""
        cutoff = datetime.date.today() - datetime.timedelta(days=self.retention_days)
        for path in self.log_dir.glob("*.log"):
            file_date = _parse_log_date(path)
            if file_date and file_date < cutoff:
                path.unlink()
                self.info(f"Deleted old log: {path.name}")

    def close(self):
        """Flush and close the log file handle."""
        self._fh.close()

    def _write(self, level, message):
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        line = f"[{timestamp}] [{level}] {message}"
        print(line, flush=True)
        self._fh.write(line + "\n")
        self._fh.flush()


class PrintLogger:
    """Minimal logger that writes to stdout only, for use during --install."""

    def info(self, message):
        print(f"  [INFO] {message}")

    def warn(self, message):
        print(f"  [WARN] {message}")

    def error(self, message):
        print(f"  [ERROR] {message}")


def _parse_log_date(path):
    """Parse an ISO date from a log filename stem, or return None."""
    try:
        return datetime.date.fromisoformat(path.stem)
    except ValueError:
        return None


def create_logger(config):
    """Create a file-based Logger instance from the current configuration."""
    return Logger(SCRIPT_DIR / config["logDir"], config["logRetentionDays"])


# ── Authentication ───────────────────────────────────────────────────────────


def run_oauth_flow(client_id, client_secret):
    """Open the browser-based OAuth 2.0 flow and return credentials."""
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    return flow.run_local_server(port=0)


def _build_credentials_from_env(config):
    """Construct a Credentials object from config and current environment."""
    return Credentials(
        token=os.environ.get("GOOGLE_ACCESS_TOKEN", ""),
        refresh_token=os.environ.get("GOOGLE_REFRESH_TOKEN", ""),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config["google"]["clientId"],
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        scopes=SCOPES,
    )


def _refresh_credentials(creds, logger):
    """Attempt to refresh expired credentials. Returns True on success."""
    try:
        creds.refresh(GoogleAuthRequest())
        save_env_value("GOOGLE_ACCESS_TOKEN", creds.token)
        if creds.refresh_token:
            save_env_value("GOOGLE_REFRESH_TOKEN", creds.refresh_token)
        logger.info("Access token refreshed")
        return True
    except Exception as exc:
        logger.warn(f"Token refresh failed: {exc}")
        return False


def _reauthenticate(config, logger):
    """Run the interactive OAuth flow and persist new tokens."""
    logger.info("Starting interactive OAuth flow")
    client_id = config["google"]["clientId"]
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    creds = run_oauth_flow(client_id, client_secret)
    save_env_value("GOOGLE_ACCESS_TOKEN", creds.token)
    save_env_value("GOOGLE_REFRESH_TOKEN", creds.refresh_token)
    logger.info("OAuth tokens saved")
    return creds


def get_valid_credentials(config, logger):
    """Return valid Google credentials, refreshing or re-authenticating as needed."""
    load_env()

    if not os.environ.get("GOOGLE_REFRESH_TOKEN", ""):
        return _reauthenticate(config, logger)

    creds = _build_credentials_from_env(config)
    if creds.valid:
        logger.info("Using existing valid access token")
        return creds

    if _refresh_credentials(creds, logger):
        return creds

    return _reauthenticate(config, logger)


def build_youtube_service(creds):
    """Build and return a YouTube Data API v3 service object."""
    return build_service("youtube", "v3", credentials=creds)


# ── YouTube API — Low-Level Wrappers ─────────────────────────────────────────
#
# Each function makes exactly one API call and returns the raw response.
# No logging or orchestration — that belongs in the high-level layer.
# ─────────────────────────────────────────────────────────────────────────────


def _api_insert_broadcast(youtube, title, privacy, enable_monitor):
    """Call liveBroadcasts.insert and return the API response."""
    body = {
        "snippet": {
            "title": title,
            "scheduledStartTime": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
        "contentDetails": {
            "monitorStream": {
                "enableMonitorStream": enable_monitor,
            },
            "enableAutoStart": False,
            "enableAutoStop": False,
        },
    }
    return (
        youtube.liveBroadcasts()
        .insert(part="snippet,status,contentDetails", body=body)
        .execute()
    )


def _api_insert_stream(youtube):
    """Call liveStreams.insert and return the API response."""
    body = {
        "snippet": {
            "title": f"Stream {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
        },
        "cdn": {
            "frameRate": "variable",
            "ingestionType": "rtmp",
            "resolution": "variable",
        },
    }
    return youtube.liveStreams().insert(part="snippet,cdn", body=body).execute()


def _api_bind_broadcast(youtube, broadcast_id, stream_id):
    """Call liveBroadcasts.bind and return the API response."""
    return (
        youtube.liveBroadcasts()
        .bind(part="id,contentDetails", id=broadcast_id, streamId=stream_id)
        .execute()
    )


def _api_transition_broadcast(youtube, broadcast_id, status):
    """Call liveBroadcasts.transition and return the API response."""
    return (
        youtube.liveBroadcasts()
        .transition(broadcastStatus=status, id=broadcast_id, part="id,status")
        .execute()
    )


def _api_get_stream_status(youtube, stream_id):
    """Return the current streamStatus string, or None if unavailable."""
    resp = youtube.liveStreams().list(part="status", id=stream_id).execute()
    items = resp.get("items", [])
    return items[0]["status"]["streamStatus"] if items else None


def _api_get_broadcast_lifecycle(youtube, broadcast_id):
    """Return the current lifeCycleStatus string, or None if unavailable."""
    resp = youtube.liveBroadcasts().list(part="status", id=broadcast_id).execute()
    items = resp.get("items", [])
    return items[0]["status"]["lifeCycleStatus"] if items else None


def _api_list_my_streams(youtube):
    """Call liveStreams.list with mine=True and return the items list."""
    resp = youtube.liveStreams().list(part="cdn", mine=True).execute()
    return resp.get("items", [])


def _api_update_broadcast_snippet(youtube, broadcast_id, snippet):
    """Call liveBroadcasts.update to replace the broadcast snippet."""
    return (
        youtube.liveBroadcasts()
        .update(part="snippet", body={"id": broadcast_id, "snippet": snippet})
        .execute()
    )


def _api_update_video_snippet(youtube, video_id, snippet):
    """Call videos.update to replace the video snippet."""
    return (
        youtube.videos()
        .update(part="snippet", body={"id": video_id, "snippet": snippet})
        .execute()
    )


def _api_get_video_snippet(youtube, video_id):
    """Call videos.list and return the snippet, or None."""
    resp = youtube.videos().list(part="snippet", id=video_id).execute()
    items = resp.get("items", [])
    return items[0]["snippet"] if items else None


# ── YouTube API — High-Level Orchestration ───────────────────────────────────
#
# These compose the low-level wrappers with logging, polling, and error
# handling.  Each function represents one meaningful broadcast lifecycle step.
# ─────────────────────────────────────────────────────────────────────────────


def interpolate_broadcast_title(config):
    """Replace the {date} token in the broadcast title template."""
    template = config["youtube"]["broadcastTitle"]
    return template.replace("{date}", datetime.date.today().isoformat())


def create_broadcast(youtube, config, logger):
    """Create a new live broadcast and return its ID."""
    title = interpolate_broadcast_title(config)
    privacy = config["youtube"]["privacy"]
    enable_monitor = config["youtube"]["enableMonitorStream"]

    logger.info(f'Creating broadcast: title="{title}", privacy={privacy}')
    resp = _api_insert_broadcast(youtube, title, privacy, enable_monitor)
    broadcast_id = resp["id"]
    logger.info(f"Broadcast created: {broadcast_id}")
    logger.info(f"Stable stream URL: https://youtube.com/live/{broadcast_id}")
    return broadcast_id


def create_stream_resource(youtube, logger):
    """Create a live-stream resource.

    Returns:
        tuple: (stream_id, rtmp_url, backup_url, stream_key)
    """
    logger.info("Creating live stream resource")
    resp = _api_insert_stream(youtube)
    ingestion = resp["cdn"]["ingestionInfo"]
    stream_id = resp["id"]
    rtmp_url = ingestion["ingestionAddress"]
    backup_url = ingestion.get("backupIngestionAddress", "")
    stream_key = ingestion["streamName"]
    logger.info(f"Stream resource created: {stream_id}")
    return stream_id, rtmp_url, backup_url, stream_key


def bind_stream_to_broadcast(youtube, broadcast_id, stream_id, logger):
    """Bind a live stream to a broadcast."""
    logger.info(f"Binding stream {stream_id} → broadcast {broadcast_id}")
    _api_bind_broadcast(youtube, broadcast_id, stream_id)
    logger.info("Stream bound to broadcast")


def apply_broadcast_category(youtube, broadcast_id, category_id, logger):
    """Set the video category on the broadcast's associated video."""
    try:
        snippet = _api_get_video_snippet(youtube, broadcast_id)
        if not snippet:
            return
        snippet["categoryId"] = category_id
        _api_update_video_snippet(youtube, broadcast_id, snippet)
        logger.info(f"Video category set to {category_id}")
    except HttpError as exc:
        logger.warn(f"Could not set video category: {exc}")


def update_broadcast_title(youtube, broadcast_id, config, logger):
    """Update the broadcast title with today's interpolated date."""
    title = interpolate_broadcast_title(config)
    try:
        resp = youtube.liveBroadcasts().list(
            part="snippet", id=broadcast_id
        ).execute()
        items = resp.get("items", [])
        if not items:
            logger.warn(f"Broadcast {broadcast_id} not found")
            return
        snippet = items[0]["snippet"]
        snippet["title"] = title
        _api_update_broadcast_snippet(youtube, broadcast_id, snippet)
        logger.info(f'Broadcast title updated: "{title}"')
    except HttpError as exc:
        logger.warn(f"Could not update broadcast title: {exc}")


def find_stream_by_key(youtube, stream_key, logger):
    """Search the user's live streams for one whose streamName matches the key."""
    logger.info("Searching for stream resource matching configured key")
    for item in _api_list_my_streams(youtube):
        if item["cdn"]["ingestionInfo"]["streamName"] == stream_key:
            stream_id = item["id"]
            logger.info(f"Found matching stream resource: {stream_id}")
            return stream_id
    logger.warn("No matching stream resource found")
    return None


def wait_for_stream_active(youtube, stream_id, logger):
    """Poll until the stream status becomes 'active'. Returns True on success."""
    logger.info(f"Waiting for stream {stream_id} to become active")
    for _ in range(120):
        status = _api_get_stream_status(youtube, stream_id)
        logger.info(f"Stream status: {status}")
        if status == "active":
            return True
        if _stop_requested:
            return False
        time.sleep(5)
    logger.warn("Timed out waiting for stream to become active")
    return False


def _attempt_testing_transition(youtube, broadcast_id, logger):
    """Transition to the testing phase and wait for confirmation."""
    try:
        logger.info(f"Transitioning broadcast {broadcast_id} → testing")
        _api_transition_broadcast(youtube, broadcast_id, "testing")
        _poll_until_lifecycle_status(youtube, broadcast_id, "testing", logger)
    except HttpError as exc:
        logger.warn(f"Testing transition: {exc}")


def _poll_until_lifecycle_status(youtube, broadcast_id, target, logger):
    """Poll until the broadcast reaches the target lifecycle status."""
    for _ in range(60):
        status = _api_get_broadcast_lifecycle(youtube, broadcast_id)
        logger.info(f"Broadcast lifecycle: {status}")
        if status == target:
            return
        time.sleep(3)


def transition_to_live(youtube, broadcast_id, logger):
    """Move the broadcast from ready → testing → live."""
    _attempt_testing_transition(youtube, broadcast_id, logger)
    logger.info(f"Transitioning broadcast {broadcast_id} → live")
    _api_transition_broadcast(youtube, broadcast_id, "live")
    logger.info("Broadcast is LIVE")


def ensure_broadcast_live(youtube, broadcast_id, logger, res=None):
    """Transition the broadcast to live if it is not already.

    Raises RuntimeError if the broadcast is in an unrecoverable state.
    """
    status = _api_get_broadcast_lifecycle(youtube, broadcast_id)
    logger.info(f"Broadcast lifecycle status: {status}")

    if status == "live":
        logger.info("Broadcast is already live")
        return

    if status in ("ready", "created"):
        transition_to_live(youtube, broadcast_id, logger)
        return

    if status == "testing":
        logger.info(f"Transitioning broadcast {broadcast_id} → live")
        _api_transition_broadcast(youtube, broadcast_id, "live")
        logger.info("Broadcast is LIVE")
        return

    errors = res["errors"] if res else {}
    if status == "complete":
        msg = errors.get("broadcast_complete", "").format(broadcast_id=broadcast_id) \
            if errors else f"Broadcast {broadcast_id} is complete. Run --install."
        raise RuntimeError(msg)

    msg = errors.get("broadcast_unexpected", "").format(
        broadcast_id=broadcast_id, status=status
    ) if errors else f"Broadcast {broadcast_id} in unexpected state: {status}"
    raise RuntimeError(msg)


# ── ffmpeg ───────────────────────────────────────────────────────────────────


def build_ffmpeg_command(config, rtmp_url, stream_key):
    """Construct the ffmpeg command list from configuration values."""
    stream = config["stream"]
    cmd = ["ffmpeg", "-re", "-rtsp_transport", "tcp", "-i", stream["rtspUrl"]]
    cmd.extend(["-vcodec", stream["videoCodec"]])
    cmd.extend(_audio_flags(stream))
    cmd.extend(["-f", "flv", f"{rtmp_url}/{stream_key}"])
    return cmd


def _audio_flags(stream_config):
    """Return ffmpeg audio flags: -an if muted, otherwise -acodec <codec>."""
    if stream_config["mute"]:
        return ["-an"]
    return ["-acodec", stream_config["audioCodec"]]


def select_rtmp_url(config, attempt_number):
    """Select primary or backup RTMP URL based on the retry attempt number.

    Even attempts (0, 2, 4, ...) use the primary URL.
    Odd attempts (1, 3, 5, ...) use the backup URL if configured.
    """
    yt = config["youtube"]
    backup = yt.get("backupStreamUrl", "")
    if backup and attempt_number % 2 == 1:
        return backup
    return yt["streamURL"]


def start_ffmpeg_process(cmd, logger):
    """Launch ffmpeg as a subprocess and return the Popen handle."""
    safe_cmd = cmd[:-1] + ["<REDACTED>"]
    logger.info(f"Launching ffmpeg: {' '.join(safe_cmd)}")
    return subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )


def relay_ffmpeg_output(process, logger):
    """Stream ffmpeg stdout/stderr to the logger line by line."""
    for line in iter(process.stdout.readline, ""):
        logger.info(f"[ffmpeg] {line.rstrip()}")


# ── PID File Management ─────────────────────────────────────────────────────


def _pid_file_path(config):
    """Resolve the absolute PID file path."""
    return SCRIPT_DIR / config["pidFile"]


def write_pid_file(config):
    """Write the current process PID to disk."""
    _pid_file_path(config).write_text(str(os.getpid()))


def read_pid_file(config):
    """Read the PID from the PID file, or return None."""
    path = _pid_file_path(config)
    if not path.exists():
        return None
    try:
        return int(path.read_text().strip())
    except ValueError:
        return None


def cleanup_pid_file(config):
    """Remove the PID file if it exists."""
    path = _pid_file_path(config)
    if path.exists():
        path.unlink()


# ── Stop Sentinel ────────────────────────────────────────────────────────────


def _sentinel_file_path(config):
    """Resolve the absolute stop-sentinel file path."""
    return SCRIPT_DIR / config["stopSentinel"]


def write_stop_sentinel(config):
    """Create the stop sentinel file."""
    _sentinel_file_path(config).touch()


def stop_sentinel_exists(config):
    """Return True if the stop sentinel file is present."""
    return _sentinel_file_path(config).exists()


def cleanup_stop_sentinel(config):
    """Remove the stop sentinel file if it exists."""
    path = _sentinel_file_path(config)
    if path.exists():
        path.unlink()


def is_stop_requested(config):
    """Check whether a stop has been requested via flag or sentinel file."""
    return _stop_requested or stop_sentinel_exists(config)


# ── Process Lifecycle ────────────────────────────────────────────────────────


def _is_process_running(pid):
    """Return True if a process with the given PID is alive."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _wait_for_process_exit(pid, timeout_secs, logger):
    """Block until the process exits or the timeout elapses."""
    for _ in range(timeout_secs):
        if not _is_process_running(pid):
            return
        time.sleep(1)
    logger.warn(f"Process {pid} did not exit within {timeout_secs}s")


def kill_existing_process(config, logger):
    """Terminate an existing stream process if one is running."""
    pid = read_pid_file(config)
    if pid is None:
        return

    if not _is_process_running(pid):
        logger.info(f"Stale PID file (process {pid} not running), removing")
        cleanup_pid_file(config)
        return

    logger.info(f"Killing existing process {pid}")
    os.kill(pid, signal.SIGTERM)
    _wait_for_process_exit(pid, 30, logger)
    cleanup_pid_file(config)
    logger.info(f"Process {pid} terminated")


# ── Signal Handling ──────────────────────────────────────────────────────────


def _signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM: set the stop flag and terminate ffmpeg."""
    global _stop_requested
    _stop_requested = True
    if _config:
        write_stop_sentinel(_config)
    if _ffmpeg_process and _ffmpeg_process.poll() is None:
        _ffmpeg_process.terminate()


def register_signal_handlers():
    """Register graceful-shutdown handlers for SIGINT and SIGTERM."""
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)


# ── Terminal Detection ───────────────────────────────────────────────────────


def detect_terminal():
    """Return the first available terminal emulator from the priority list."""
    candidates = ["gnome-terminal", "xterm", "konsole", "xfce4-terminal"]
    for term in candidates:
        if shutil.which(term):
            return term
    return "xterm"


# ── Crontab Management ──────────────────────────────────────────────────────


def _build_cron_line(schedule, terminal, action):
    """Build a single crontab entry for the given action.

    --start runs inside a visible terminal window (closes when the process exits).
    --stop runs directly without a terminal — it sends SIGTERM and exits quickly.
    This prevents terminal window accumulation over time.
    """
    script_path = Path(__file__).resolve()
    python = sys.executable

    if action == "stop":
        return f"{schedule} {python} {script_path} --stop {CRON_MARKER}"

    title = "BC Free Flight Stream"
    if terminal == "gnome-terminal":
        term_cmd = f'{terminal} --title="{title}" -- {python} {script_path} --start'
    elif terminal == "xfce4-terminal":
        term_cmd = f'{terminal} --title="{title}" -e "{python} {script_path} --start"'
    else:
        term_cmd = f"{terminal} -T '{title}' -e {python} {script_path} --start"

    return f"{schedule} DISPLAY=:0 {term_cmd} {CRON_MARKER}"


def _read_current_crontab():
    """Read the current crontab contents, returning empty string on failure."""
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else ""
    except FileNotFoundError:
        return ""


def _remove_marker_lines(crontab_text):
    """Return all lines that do not contain the cron marker."""
    return [line for line in crontab_text.splitlines() if CRON_MARKER not in line]


def register_cron_entries(config, logger=None):
    """Register start/stop cron entries, replacing any existing ones."""
    terminal = config["terminal"]
    start_line = _build_cron_line(config["cron"]["start"], terminal, "start")
    stop_line = _build_cron_line(config["cron"]["stop"], terminal, "stop")

    lines = _remove_marker_lines(_read_current_crontab())
    lines.extend([start_line, stop_line])

    new_crontab = "\n".join(lines) + "\n"
    subprocess.run(
        ["crontab", "-"], input=new_crontab, check=True, capture_output=True, text=True
    )

    message = "Crontab entries registered"
    if logger:
        logger.info(message)
    else:
        print(message)


def remove_cron_entries():
    """Remove all bcfreeflight_stream cron entries."""
    lines = _remove_marker_lines(_read_current_crontab())
    new_crontab = "\n".join(lines) + "\n" if lines else ""
    subprocess.run(
        ["crontab", "-"], input=new_crontab, check=True, capture_output=True, text=True
    )


# ── Interactive Prompts ──────────────────────────────────────────────────────


def _prompt(label, default=None, validator=None):
    """Prompt the user for input with an optional default and validator.

    Re-prompts until a non-empty value is given (or default is accepted) and
    the validator (if any) returns True.
    """
    suffix = f" [{default}]" if default is not None else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if not value:
            if default is not None:
                return str(default)
            print("  This field is required.")
            continue
        if validator and not validator(value):
            continue
        return value


def _make_validator(check_fn, error_msg):
    """Create a validator function that prints a message on failure."""
    def validator(value):
        if not check_fn(value):
            print(error_msg)
            return False
        return True
    return validator


def _show_guide(lines):
    """Print a multi-line guide from resources.json."""
    for line in lines:
        print(line)


def _smart_prompt(label, current, default=None, guide=None, validator=None):
    """Prompt only if the current value is empty/None. Show guide when prompting.

    If current already has a value, it is silently reused (skipped).
    """
    if current:
        return current
    if guide:
        _show_guide(guide)
    return _prompt(label, default=default, validator=validator)


def _try_load_existing_config():
    """Load existing config.json if present, or return None."""
    path = SCRIPT_DIR / "config.json"
    if not path.exists():
        return None
    try:
        with open(path, "r") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def _get_nested(config, *keys, default=""):
    """Safely traverse nested dict keys, returning default if any key is missing."""
    current = config
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current if current is not None else default


def prompt_all_config_values(res, existing=None):
    """Interactively prompt for configuration values that are not already set.

    Existing values (from a previous install) are silently kept.
    Empty values trigger a prompt, with a setup guide shown where relevant.

    Args:
        res: The loaded resources.json dict.
        existing: Previously saved config dict, or None.

    Returns:
        tuple: (config_dict, client_secret)
    """
    prompts = res["install"]["prompts"]
    defaults = res["install"]["defaults"]
    validation = res["install"]["validation"]
    sections = res["install"]["sections"]
    ex = existing or {}

    rtsp_validator = _make_validator(
        lambda v: v.startswith("rtsp://"), validation["rtsp_url"]
    )
    yes_no_validator = _make_validator(
        lambda v: v.lower() in ("yes", "no"), validation["yes_no"]
    )
    privacy_validator = _make_validator(
        lambda v: v.lower() in ("public", "unlisted", "private"), validation["privacy"]
    )

    # ── Google OAuth ──
    print(sections["google"])
    load_env()
    client_id = _smart_prompt(
        prompts["clientId"],
        _get_nested(ex, "google", "clientId"),
        guide=res["install"]["google_cloud_guide"],
    )
    existing_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    client_secret = _smart_prompt(
        prompts["clientSecret"],
        existing_secret,
    )

    # ── RTSP Source ──
    print(sections["rtsp"])
    rtsp_url = _smart_prompt(
        prompts["rtspUrl"],
        _get_nested(ex, "stream", "rtspUrl"),
        validator=rtsp_validator,
    )
    video_codec = _smart_prompt(
        prompts["videoCodec"],
        _get_nested(ex, "stream", "videoCodec"),
        default=defaults["videoCodec"],
    )
    audio_codec = _smart_prompt(
        prompts["audioCodec"],
        _get_nested(ex, "stream", "audioCodec"),
        default=defaults["audioCodec"],
    )
    existing_mute = _get_nested(ex, "stream", "mute", default=None)
    if existing_mute is not None:
        mute = existing_mute
    else:
        mute_str = _prompt(
            prompts["mute"], default=defaults["mute"], validator=yes_no_validator
        )
        mute = mute_str.lower() == "yes"

    # ── YouTube Broadcast ──
    print(sections["youtube_broadcast"])
    title = _smart_prompt(
        prompts["broadcastTitle"],
        _get_nested(ex, "youtube", "broadcastTitle"),
        default=defaults["broadcastTitle"],
        guide=res["install"]["broadcast_title_guide"],
    )
    privacy = _smart_prompt(
        prompts["privacy"],
        _get_nested(ex, "youtube", "privacy"),
        default=defaults["privacy"],
        validator=privacy_validator,
    )
    category_id = _smart_prompt(
        prompts["categoryId"],
        _get_nested(ex, "youtube", "categoryId"),
        default=defaults["categoryId"],
    )
    broadcast_id = _smart_prompt(
        prompts["broadcastId"],
        _get_nested(ex, "youtube", "broadcastId"),
        default=defaults["broadcastId"],
    )

    # ── YouTube Stream ──
    print(sections["youtube_stream"])
    stream_key = _smart_prompt(
        prompts["streamKey"],
        _get_nested(ex, "youtube", "streamKey"),
        default=defaults["streamKey"],
        guide=res["install"]["youtube_stream_guide"],
    )
    stream_url = _smart_prompt(
        prompts["streamURL"],
        _get_nested(ex, "youtube", "streamURL"),
        default=defaults["streamURL"],
    )
    backup_stream_url = _smart_prompt(
        prompts["backupStreamUrl"],
        _get_nested(ex, "youtube", "backupStreamUrl"),
        default=defaults["backupStreamUrl"],
    )

    # ── Schedule (cron) ──
    print(sections["schedule"])
    cron_setup = _prompt(
        prompts["cronSetup"], default="yes", validator=yes_no_validator
    )
    cron_enabled = cron_setup.lower() == "yes"

    cron_start = ""
    cron_stop = ""
    if cron_enabled:
        _show_guide(res["install"]["cron_guide"])
        cron_start = _smart_prompt(
            prompts["cronStart"],
            _get_nested(ex, "cron", "start"),
            default=defaults["cronStart"],
        )
        cron_stop = _smart_prompt(
            prompts["cronStop"],
            _get_nested(ex, "cron", "stop"),
            default=defaults["cronStop"],
        )

    config = {
        "google": {"clientId": client_id},
        "stream": {
            "rtspUrl": rtsp_url,
            "videoCodec": video_codec,
            "audioCodec": audio_codec,
            "mute": mute,
        },
        "youtube": {
            "broadcastTitle": title,
            "privacy": privacy.lower() if isinstance(privacy, str) else privacy,
            "categoryId": category_id,
            "enableMonitorStream": _get_nested(
                ex, "youtube", "enableMonitorStream", default=False
            ),
            "broadcastId": broadcast_id,
            "streamId": _get_nested(ex, "youtube", "streamId"),
            "streamURL": stream_url,
            "backupStreamUrl": backup_stream_url,
            "streamKey": stream_key,
        },
        "pidFile": _get_nested(ex, "pidFile", default="./stream.pid"),
        "stopSentinel": _get_nested(ex, "stopSentinel", default="./stream.stop"),
        "logDir": _get_nested(ex, "logDir", default="./logs"),
        "logRetentionDays": _get_nested(ex, "logRetentionDays", default=15),
        "retryDelaySecs": _get_nested(ex, "retryDelaySecs", default=5),
        "terminal": _get_nested(ex, "terminal", default="gnome-terminal"),
        "cron": {
            "enabled": cron_enabled,
            "start": cron_start,
            "stop": cron_stop,
        },
    }
    return config, client_secret


# ── --install Command ────────────────────────────────────────────────────────


def _write_config_file(config, res):
    """Save config.json and notify the user."""
    save_config(config)
    print(res["install"]["messages"]["config_written"].format(
        path=SCRIPT_DIR / "config.json"
    ))


def _write_env_file(client_secret, res):
    """Create the .env file with the client secret and empty token placeholders."""
    path = str(SCRIPT_DIR / ".env")
    Path(path).touch()
    set_key(path, "GOOGLE_CLIENT_SECRET", client_secret)
    set_key(path, "GOOGLE_REFRESH_TOKEN", "")
    set_key(path, "GOOGLE_ACCESS_TOKEN", "")
    print(res["install"]["messages"]["secrets_written"].format(path=path))


def _install_ffmpeg_if_missing(res):
    """Install ffmpeg via apt if it is not already on PATH."""
    msgs = res["install"]["messages"]
    if shutil.which("ffmpeg"):
        print(msgs["ffmpeg_installed"])
        return
    print(msgs["ffmpeg_installing"])
    subprocess.check_call(["sudo", "apt", "install", "-y", "ffmpeg"])


def _run_install_oauth(config, client_secret, res):
    """Run the OAuth browser flow and persist the resulting tokens."""
    msgs = res["install"]["messages"]
    print(msgs["oauth_starting"])
    creds = run_oauth_flow(config["google"]["clientId"], client_secret)
    env_path = str(SCRIPT_DIR / ".env")
    set_key(env_path, "GOOGLE_REFRESH_TOKEN", creds.refresh_token)
    set_key(env_path, "GOOGLE_ACCESS_TOKEN", creds.token)
    print(msgs["oauth_saved"])
    return creds


def _setup_youtube_resources(config, creds, res):
    """Create YouTube broadcast and stream resources if not already configured.

    Mutates config in-place with the resulting IDs and URLs.
    """
    youtube = build_youtube_service(creds)
    logger = PrintLogger()
    yt = config["youtube"]
    msgs = res["install"]["messages"]

    if not yt.get("broadcastId"):
        yt["broadcastId"] = create_broadcast(youtube, config, logger)

    if not yt.get("streamId"):
        stream_id = find_stream_by_key(youtube, yt["streamKey"], logger)
        yt["streamId"] = stream_id or ""

    if yt["broadcastId"] and yt.get("streamId"):
        bind_stream_to_broadcast(
            youtube, yt["broadcastId"], yt["streamId"], logger
        )

    if yt["broadcastId"] and yt.get("categoryId"):
        apply_broadcast_category(
            youtube, yt["broadcastId"], yt["categoryId"], logger
        )

    bid = yt["broadcastId"]
    print(msgs["broadcast_id_label"].format(broadcast_id=bid))
    print(msgs["stream_url_label"].format(broadcast_id=bid))


def _print_install_summary(config, res):
    """Print a success summary after installation completes."""
    yt = config["youtube"]
    summary = res["install"]["summary"]
    print(summary["header"])
    print(summary["config"].format(path=SCRIPT_DIR / "config.json"))
    print(summary["secrets"].format(path=SCRIPT_DIR / ".env"))
    print(summary["terminal"].format(terminal=config["terminal"]))
    if config["cron"].get("enabled"):
        print(summary["cron_start"].format(schedule=config["cron"]["start"]))
        print(summary["cron_stop"].format(schedule=config["cron"]["stop"]))
    else:
        print("  Cron:          disabled")
    print(summary["youtube_url"].format(broadcast_id=yt["broadcastId"]))
    print(summary["run_hint"])


def do_install():
    """Interactive first-time setup: prompt, write config, OAuth, cron.

    Loads existing config if present — only prompts for empty/missing values.
    Walks the user through Google Cloud and YouTube setup when needed.
    """
    res = load_resources()
    print(res["install"]["header"] + "\n")

    existing = _try_load_existing_config()
    config, client_secret = prompt_all_config_values(res, existing)

    _write_config_file(config, res)
    _write_env_file(client_secret, res)
    _install_ffmpeg_if_missing(res)
    print(res["install"]["messages"]["deps_verified"])

    creds = _run_install_oauth(config, client_secret, res)

    print(res["install"]["sections"]["youtube_setup"])
    _setup_youtube_resources(config, creds, res)

    terminal = detect_terminal()
    config["terminal"] = terminal
    save_config(config)
    print(res["install"]["messages"]["terminal_detected"].format(terminal=terminal))

    msgs = res["install"]["messages"]
    if config["cron"].get("enabled"):
        register_cron_entries(config)
    else:
        remove_cron_entries()
        print(msgs["cron_skipped"])

    _print_install_summary(config, res)


# ── --start Command ──────────────────────────────────────────────────────────


def _prepare_stream_process(config, logger):
    """Clean up previous state, kill any running process, write PID, prune old logs."""
    cleanup_stop_sentinel(config)
    kill_existing_process(config, logger)
    write_pid_file(config)
    logger.cleanup_old_logs()


def _validate_youtube_config(config, res):
    """Raise RuntimeError if required YouTube settings are missing."""
    yt = config["youtube"]
    missing = []
    if not yt.get("broadcastId"):
        missing.append("broadcastId")
    if not yt.get("streamURL"):
        missing.append("streamURL")
    if not yt.get("streamKey"):
        missing.append("streamKey")
    if missing:
        raise RuntimeError(
            res["errors"]["missing_config"].format(fields=", ".join(missing))
        )


def _connect_to_broadcast(config, logger, attempt_number=0):
    """Authenticate and build a BroadcastContext from the stored config.

    Returns:
        BroadcastContext with youtube service, broadcast ID, and RTMP details.
    """
    creds = get_valid_credentials(config, logger)
    youtube = build_youtube_service(creds)

    yt = config["youtube"]
    broadcast_id = yt["broadcastId"]
    rtmp_url = select_rtmp_url(config, attempt_number)
    stream_key = yt["streamKey"]

    stream_id = yt.get("streamId", "")
    if not stream_id:
        stream_id = find_stream_by_key(youtube, stream_key, logger) or ""

    return BroadcastContext(youtube, broadcast_id, stream_id, rtmp_url, stream_key)


def _stream_until_exit(config, logger, ctx, res=None):
    """Launch ffmpeg, ensure the broadcast is live, then relay output until exit."""
    global _ffmpeg_process

    cmd = build_ffmpeg_command(config, ctx.rtmp_url, ctx.stream_key)
    process = start_ffmpeg_process(cmd, logger)
    _ffmpeg_process = process

    if ctx.stream_id:
        if not wait_for_stream_active(ctx.youtube, ctx.stream_id, logger):
            process.terminate()
            process.wait()
            _ffmpeg_process = None
            if is_stop_requested(config):
                return
            raise RuntimeError("Stream did not become active")
    else:
        logger.info("Stream ID unavailable — waiting for ffmpeg to establish connection")
        time.sleep(15)

    ensure_broadcast_live(ctx.youtube, ctx.broadcast_id, logger, res)
    relay_ffmpeg_output(process, logger)

    process.wait()
    _ffmpeg_process = None
    logger.info(f"ffmpeg exited with code {process.returncode}")


def _cleanup_ffmpeg():
    """Terminate ffmpeg if it is still running."""
    global _ffmpeg_process
    if _ffmpeg_process and _ffmpeg_process.poll() is None:
        _ffmpeg_process.terminate()
        _ffmpeg_process.wait()
    _ffmpeg_process = None


def _wait_before_retry(config, logger):
    """Sleep for the configured delay. Returns False if stop was requested."""
    delay = config["retryDelaySecs"]
    logger.info(f"Retrying in {delay} seconds...")
    time.sleep(delay)
    return not is_stop_requested(config)


def _run_stream_loop(config, logger, res=None):
    """Retry loop: connect to broadcast, stream until exit, retry on failure."""
    attempt = 0

    while True:
        try:
            ctx = _connect_to_broadcast(config, logger, attempt)

            if is_stop_requested(config):
                break

            if attempt == 0:
                update_broadcast_title(ctx.youtube, ctx.broadcast_id, config, logger)

            _stream_until_exit(config, logger, ctx, res)
        except Exception as exc:
            logger.error(f"Streaming error: {exc}")
            _cleanup_ffmpeg()

        if is_stop_requested(config):
            break
        if not _wait_before_retry(config, logger):
            break

        attempt += 1


def _perform_shutdown(config, logger):
    """Clean up PID file and log the shutdown."""
    cleanup_pid_file(config)
    logger.info("Stream stopped")
    logger.close()


def do_start():
    """Start the RTSP-to-YouTube stream with automatic retry on failure."""
    global _config

    config = load_config()
    _config = config
    load_env()

    res = load_resources()
    _validate_youtube_config(config, res)

    logger = create_logger(config)

    _prepare_stream_process(config, logger)
    register_signal_handlers()
    logger.info(f"BC Free Flight Stream {__version__}")
    logger.info(f"Stream process started (PID {os.getpid()})")

    _run_stream_loop(config, logger, res)
    _perform_shutdown(config, logger)


# ── --stop Command ───────────────────────────────────────────────────────────


def _signal_running_process(config, logger):
    """Write the stop sentinel and send SIGTERM to the running stream process."""
    write_stop_sentinel(config)
    logger.info("Stop sentinel written")

    pid = read_pid_file(config)
    if not pid:
        logger.warn("No PID file found")
        return

    logger.info(f"Sending SIGTERM to process {pid}")
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        logger.warn(f"Could not signal process {pid}: {exc}")
        return

    logger.info("Waiting for process to exit...")
    _wait_for_process_exit(pid, 60, logger)
    logger.info(f"Process {pid} exited")


def _cleanup_stop_files(config):
    """Remove PID and sentinel files. Broadcast config is preserved for reuse."""
    cleanup_pid_file(config)
    cleanup_stop_sentinel(config)


def do_stop():
    """Gracefully stop the running stream. The broadcast is left alive for reuse."""
    config = load_config()
    load_env()
    logger = create_logger(config)

    logger.info(f"BC Free Flight Stream {__version__}")
    _signal_running_process(config, logger)
    _cleanup_stop_files(config)

    logger.info(
        f"Clean shutdown at {datetime.datetime.now(datetime.timezone.utc).isoformat()}"
    )
    logger.close()


# ── --update Command ─────────────────────────────────────────────────────────


def _backup_current_files():
    """Create a zip backup of the current script and resources before updating.

    The backup is named stream.<current_version>.bak.zip in the script directory.
    """
    import zipfile

    version_label = __version__.replace("/", "_")
    backup_path = SCRIPT_DIR / f"stream.{version_label}.bak.zip"

    files_to_backup = [
        SCRIPT_DIR / "stream.py",
        SCRIPT_DIR / "resources.json",
    ]

    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in files_to_backup:
            if file_path.exists():
                zf.write(file_path, file_path.name)

    return backup_path


def _get_latest_release_tag():
    """Query the GitHub API for the latest release tag. Returns None on failure."""
    import urllib.request
    import urllib.error

    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            return data.get("tag_name")
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def _download_release_asset(filename):
    """Download a single asset from the latest GitHub release."""
    import urllib.request

    url = f"https://github.com/{GITHUB_REPO}/releases/latest/download/{filename}"
    dest = SCRIPT_DIR / filename
    urllib.request.urlretrieve(url, dest)


def do_update():
    """Download the latest release from GitHub, backing up current files first."""
    res = load_resources()
    msgs = res.get("update", {})

    print(f"Current version: {__version__}")

    latest = _get_latest_release_tag()
    if not latest:
        print(msgs.get("fetch_failed", "Could not fetch latest release from GitHub."))
        return

    print(f"Latest version:  {latest}")

    if latest == __version__:
        print(msgs.get("already_latest", "Already running the latest version."))
        return

    backup_path = _backup_current_files()
    print(msgs.get("backup_created", "Backup created: {path}").format(path=backup_path))

    assets = ["stream.py", "resources.json"]
    for asset in assets:
        print(msgs.get("downloading", "Downloading {file}...").format(file=asset))
        try:
            _download_release_asset(asset)
        except Exception as exc:
            print(msgs.get("download_failed",
                  "Failed to download {file}: {error}").format(file=asset, error=exc))
            print(msgs.get("restore_hint",
                  "Your backup is at {path} if you need to restore.").format(path=backup_path))
            return

    print(msgs.get("success",
          "Updated to {version}. Restart the script to use the new version.").format(
              version=latest))


# ── Entry Point ──────────────────────────────────────────────────────────────


def main():
    """Parse CLI arguments and dispatch to the appropriate command."""
    parser = argparse.ArgumentParser(description="RTSP to YouTube Live stream proxy")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true", help="Interactive first-time setup")
    group.add_argument("--start", action="store_true", help="Start the stream")
    group.add_argument("--stop", action="store_true", help="Stop the stream")
    group.add_argument("--update", action="store_true", help="Update to the latest release")
    args = parser.parse_args()

    if args.install:
        do_install()
    elif args.start:
        do_start()
    elif args.stop:
        do_stop()
    elif args.update:
        do_update()


if __name__ == "__main__":
    main()
