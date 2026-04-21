# CLAUDE.md

This file describes the project structure, conventions, and rules for AI-assisted development on this repository. Read this file in full before making any changes.

---

## Project Overview

This repository contains a single Python script (`src/stream.py`) that proxies an RTSP camera stream to YouTube Live via ffmpeg. It creates a fresh YouTube broadcast on every `--start` (retiring the previous one), uses a **stable channel embed URL** that always resolves to the current live broadcast, handles authentication via Google OAuth 2.0, retries automatically on failure, and self-registers as a daily cron job.

---

## Code Quality

All code must follow **SOLID principles** with a focus on clean code and single responsibility methods:

- Each function does exactly one thing and has a descriptive name
- Functions are short and human-readable
- Dependencies are passed as parameters, not created internally
- Prefer composition of small, focused functions over monolithic ones
- No unnecessary abstractions — but no half-finished implementations either

---

## Testing

Every code change must include corresponding unit tests:

- Tests live in the `tests/` directory, organized by functional area (e.g., `test_configuration.py`, `test_ffmpeg.py`)
- Use `pytest` with fixtures defined in `tests/conftest.py`
- Mock external dependencies (network calls, file system, subprocesses) — never make real API calls in tests
- Test both the happy path and edge cases (missing files, network errors, invalid input)
- Run the full test suite (`python3 -m pytest tests/`) before considering a change complete
- New functions added to `stream.py` must have test coverage
- If modifying existing behavior, update or add tests to reflect the change

---

## Repository Structure

```
/
├── CLAUDE.md
├── PROMPT.md
├── README.md
├── REQUIREMENTS.md
├── .github/
│   └── workflows/
│       └── release.yml
└── src/
    ├── stream.py
    ├── config.example.toml
    ├── resources.toml
    └── example.env
```

**Rules:**
- All code lives in `/src`. Do not create subdirectories or additional source files.
- `stream.py` must remain a single self-contained file. Do not split it into modules.
- Do not commit `config.toml`, `.env`, `stream.pid`, `stream.stop`, or anything under `logs/`. These are runtime-generated and must never appear in version control.
- Do not add a `.gitignore` unless it is explicitly requested — if one is added, it must ignore `src/config.toml`, `src/.env`, `src/*.pid`, `src/*.stop`, `src/logs/`, and `src/backup/`.

---

## The One File Rule

`stream.py` is intentionally a single file. This is a hard constraint, not a style preference. The reasons are:

- It is distributed as a standalone download from GitHub Releases
- Users run it directly without any packaging or install step beyond `--install`
- It must be portable to any Ubuntu/Linux Mint machine by copying one file

**Never** refactor `stream.py` into multiple files, helper modules, or packages. If a change would naturally belong in a separate module, inline it instead.

---

## Runtime Files

The following files are created at runtime beside `stream.py` inside `/src`. They are never committed:

| File | Created by | Purpose |
|------|-----------|---------|
| `config.toml` | `--install` | All non-secret configuration |
| `.env` | `--install` | All secrets and auto-refreshed tokens |
| `stream.pid` | `--start` | PID of the running stream process |
| `stream.stop` | `--stop` or SIGINT/SIGTERM | Sentinel file that suppresses retries |
| `logs/YYYY-MM-DD.log` | `--start` | Daily log file |

---

## Configuration Contract

Every config key must be **used** by the script. Do not add dead config fields. When adding a new key, ensure the script reads and acts on it.

### config.toml — non-secret values only

```toml
pidFile = "./stream.pid"
stopSentinel = "./stream.stop"
logDir = "./logs"
logRetentionDays = 15
retryDelaySecs = 5
terminal = "gnome-terminal"

[google]
clientId = ""

[stream]
rtspUrl = ""
videoCodec = "copy"
audioCodec = "copy"
mute = false

[youtube]
broadcastTitle = "My Location: {date}"
privacy = "public"
categoryId = "22"
enableMonitorStream = false
embeddable = true
broadcastId = ""
streamURL = ""
backupStreamUrl = ""
streamKey = ""

[cron]
enabled = true # if false, cron jobs are not registered during --install
start = "30 6 1-31 4-10 *"
stop = "25 18 1-31 4-10 *"
autoUpdate = false # default to false to avoid breaking changes without user consent
update = "0 0 * * *" # schedule for checking for updates (e.g. "0 0 * * *" for daily at midnight - default)
```

### .env — secrets only

```
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=
GOOGLE_ACCESS_TOKEN=
```

**Rules:**
- Every runtime value must come from `config.toml` or `.env`. No hardcoded strings, paths, URLs, or defaults may exist inside `stream.py`.
- `config.toml` keys must never contain secrets. `.env` keys must never contain non-secret config.
- When adding a new configurable value, determine whether it is a secret first. If secret, it goes in `.env`. If not, it goes in `config.toml`.
- `{date}` in `broadcastTitle` is the only supported interpolation token. Do not add others without updating this document.
- When adding or removing config keys, update: this document, `README.md`, `REQUIREMENTS.md`, `config.example.toml`, and `example.env` (as applicable).

---

## CLI Interface

The script exposes exactly three switches. Do not add, rename, or remove switches without updating this document and `README.md`.

| Switch | Behavior |
|--------|----------|
| `--install` | Idempotent setup: loads existing config and only prompts for values that are empty or missing. Installs deps, runs OAuth if needed, creates YouTube resources if not already configured, and registers cron entries without duplicating them. |
| `--uninstall` | Stops any running stream, archives the broadcast, and removes all cron entries (start/stop/@reboot recover). `config.toml` and `.env` are **preserved** so the user can re-install later without re-entering credentials. |
| `--reinstall` | Destructive clean-slate setup. Prompts for `yes` confirmation, then chains `--uninstall` → delete `config.toml` + `.env` → `--install`. `logs/` and `backup/` are preserved. |
| `--start` | Retires any active broadcast, creates a fresh one, and starts streaming. Runs in the foreground, blocking the terminal. |
| `--stop` | Writes the stop sentinel, signals the running process, waits for graceful shutdown, and transitions the broadcast to `complete` so it is archived as a VOD. |
| `--recover` | Crash-recovery. If the current time falls inside the daily `cron.start`/`cron.stop` window (and no stream is already running), delegates to `--start`. Otherwise exits cleanly. Registered as an `@reboot` cron entry by `--install`. |
| `--update` | Backs up current files to a versioned zip in `backup/`, downloads the latest release from GitHub, and replaces `stream.py` and `resources.toml`. |
| `--roll-back [VERSION]` | Restores `stream.py` and `resources.toml` from a backup. Without a version, lists available backups interactively. |

---

## Dependency Management

`stream.py` self-installs its own Python dependencies. The mechanism is:

1. At the top of the script, before any third-party imports, attempt to import each dependency
2. If any import fails, call `subprocess.check_call([sys.executable, "-m", "pip", "install", ...])` for the missing packages
3. Re-import after installation so the rest of the script can use them in the same process

Required Python packages:
- `google-auth`
- `google-auth-oauthlib`
- `google-api-python-client`
- `python-dotenv`
- `requests`
- `tomli` (Python < 3.11 only; 3.11+ uses the built-in `tomllib`)
- `tomli-w`
- `croniter` (evaluates cron expressions for `--recover` window checks)

`ffmpeg` is a system dependency installed via `apt install -y ffmpeg` during `--install` if not already on PATH. It is never installed during `--start` or `--stop`.

**Rules:**
- Never add a `requirements.txt` or `setup.py`. Dependency declarations live only inside `stream.py`.
- Never pin versions unless a specific version constraint is required to fix a known bug. Document the reason in a comment if pinning.
- Do not add new third-party dependencies without updating the dependency list in this document and `REQUIREMENTS.md`.

---

## Authentication Flow

- OAuth 2.0 credentials (client ID + secret) come from Google Cloud Console
- The initial browser-based OAuth flow runs during `--install` and writes `GOOGLE_REFRESH_TOKEN` and `GOOGLE_ACCESS_TOKEN` to `.env`
- On `--start`, the script uses the refresh token to obtain a fresh access token and updates `GOOGLE_ACCESS_TOKEN` in `.env`
- If the refresh token is expired or revoked, the script opens the browser OAuth flow interactively to re-authenticate
- Secrets are never logged, printed, or included in ffmpeg command strings that appear in logs

Required OAuth scopes:
- `https://www.googleapis.com/auth/youtube`
- `https://www.googleapis.com/auth/youtube.force-ssl`

---

## YouTube Broadcast Lifecycle

The stream resource (RTMP URL and stream key) is created **once** during `--install` and reused permanently. A **new broadcast is always created** on every `--start` — any previously active broadcast is retired first. The embedded stream URL uses the **channel-based format** (`/embed/live_stream?channel=...`) which always shows whatever broadcast is currently live — it is not tied to any specific broadcast ID.

### During `--install`:
1. `liveBroadcasts.insert` — create broadcast (with `enableAutoStop: false` to prevent auto-completion)
2. `liveStreams.insert` — create stream resource
3. `liveBroadcasts.bind` — bind stream to broadcast
4. Save `broadcastId`, `streamURL`, `backupStreamUrl`, `streamKey` to `config.toml`; `streamId` is resolved from the key at runtime and never persisted
5. Apply `categoryId` to the broadcast's associated video

### During `--start`:
1. Read `broadcastId`, `streamURL`, `streamKey` from config
2. Clean up orphaned broadcasts — query `liveBroadcasts.list`; transition `live`/`testing` to `complete`, delete `created`/`ready`
3. Retire the current broadcast — if the configured broadcast is in any active state (`live`, `testing`, `ready`, `created`), transition it to `complete`
4. Update the broadcast title with today's date via `liveBroadcasts.update` (first attempt only)
5. Launch ffmpeg pointing at the RTMP URL
6. Wait for stream to become active
7. Ensure broadcast is live — check the current lifecycle state:
   - `complete`: create a new broadcast, bind the existing stream, update `broadcastId` in `config.toml`, then transition to `live`
   - `ready` or `created`: transition `ready` → `testing` → `live`
   - `testing`: transition directly to `live`
   - `live`: no-op

### During `--stop`:
1. Stop the ffmpeg process
2. Transition the broadcast to `complete` — this archives the stream as a VOD on the channel

### Retry behavior:
- On retry, the script reconnects to the **same** broadcast created at startup — it does not create a new one
- Retries alternate between the primary `streamURL` and `backupStreamUrl` (if configured)

---

## Process Management

- `stream.pid` stores the PID of the running `--start` process
- `stream.stop` is a sentinel file whose presence signals the retry loop to stop retrying
- If `--start` is called while a `stream.pid` exists and the process is alive, the old process is killed before the new one starts
- `SIGINT` and `SIGTERM` are both treated as graceful stop signals, identical to `--stop`
- The retry loop checks for `stream.stop` before every retry attempt. If present, it exits cleanly without retrying.
- `stream.pid` and `stream.stop` are always cleaned up on exit, whether clean or via signal

---

## Retry Behavior

If ffmpeg exits for any reason other than the stop sentinel being present:

1. Log the exit code and reason
2. Wait `retryDelaySecs` seconds (from config)
3. Check for `stream.stop` — if present, exit
4. Re-authenticate if needed
5. Reconnect to the existing YouTube broadcast (alternate primary/backup RTMP URL)
6. Re-launch ffmpeg
7. Repeat indefinitely

The retry loop does not have a maximum retry count. It runs until `--stop` is called or the process receives a signal.

---

## Logging

- Log directory: value of `logDir` in `config.toml`
- One file per day: `YYYY-MM-DD.log`
- All log output is also mirrored to stdout in real time
- Log line format: `[2026-04-12T06:30:00+00:00] [LEVEL] message`
- Valid levels: `INFO`, `WARN`, `ERROR`
- ffmpeg output is logged at `INFO` with prefix `[ffmpeg]`
- YouTube API calls are logged with endpoint name, non-secret parameters, and response status
- Secrets are never written to logs under any circumstances
- Log files older than `logRetentionDays` days are deleted at `--start`

---

## Crontab

`--install` self-registers three crontab entries using the expressions in `config.toml` under `cron.start` and `cron.stop`. The default schedule runs April 1 through October 31:

- **Start:** `30 6 1-31 4-10 *` (6:30am daily) — opens a terminal window titled "BC Free Flight Stream"
- **Stop:** `25 18 1-31 4-10 *` (6:25pm daily) — runs directly without a terminal window
- **Recover:** `@reboot` — runs `--recover` headless at boot so the stream resumes automatically after a power loss or reboot that falls inside the daily window
- **Update** *(optional)*: `0 0 * * *` (midnight daily, default) — runs `--update` headless; only registered when `cron.autoUpdate = true`

The `autoUpdate` flag defaults to `false` to prevent unattended updates without user consent. When enabled during `--install`, the update cron is registered alongside the other three.

The start cron opens a single terminal window. When the stop cron fires, the stream process exits and the terminal window closes. This prevents terminal window accumulation over time — only one window exists at a time.

`--install` must not create duplicate crontab entries if run more than once.

When `--start` or `--update` is run, `_migrate_config()` deep-merges `CONFIG_DEFAULTS` against the existing `config.toml` and writes back any keys that are absent. This is the general migration mechanism — adding a new config key to `CONFIG_DEFAULTS` is sufficient to backfill it on all existing installs without a separate migration function.

---

## GitHub Actions

The release workflow lives at `.github/workflows/release.yml`.

**Triggers:**
- Manual `workflow_dispatch` only — releases are not created automatically on merge

**Versioning:**
- Reads the latest release tag from the GitHub API
- Increments the patch version (e.g. `v1.0.4` → `v1.0.5`)
- Starts at `v1.0.0` if no releases exist
- Version is always determined dynamically — never hardcoded

**Release artifacts:**
- `src/stream.py` attached as `stream.py` (no path prefix)
- `src/resources.toml` attached as `resources.toml` (no path prefix)
- Changelog body: commits since the previous tag, or "Initial release"
- Uses `GITHUB_TOKEN` exclusively — no additional secrets

---

## What Not To Do

- Do not split `stream.py` into multiple files
- Do not add a `requirements.txt` or `setup.py`
- Do not hardcode any value that belongs in `config.toml` or `.env`
- Do not log or print secrets, tokens, or stream keys
- Do not commit runtime files (`config.toml`, `.env`, `*.pid`, `*.stop`, `logs/`)
- Do not add new CLI switches without updating this document and `README.md`
- Do not add new config keys without updating the config contract in this document, `README.md`, `REQUIREMENTS.md`, and example files
- Do not install ffmpeg or system packages during `--start` or `--stop`
- Do not add dead config fields — every key must be read and used by the script
