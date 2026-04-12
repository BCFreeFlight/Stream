# CLAUDE.md

This file describes the project structure, conventions, and rules for AI-assisted development on this repository. Read this file in full before making any changes.

---

## Project Overview

This repository contains a single Python script (`src/stream.py`) that proxies an RTSP camera stream to YouTube Live via ffmpeg. It reuses a **persistent** YouTube broadcast (stable URL for embedding), handles authentication via Google OAuth 2.0, retries automatically on failure, and self-registers as a daily cron job.

---

## Code Quality

All code must follow **SOLID principles** with a focus on clean code and single responsibility methods:

- Each function does exactly one thing and has a descriptive name
- Functions are short and human-readable
- Dependencies are passed as parameters, not created internally
- Prefer composition of small, focused functions over monolithic ones
- No unnecessary abstractions — but no half-finished implementations either

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
    ├── config.example.json
    └── example.env
```

**Rules:**
- All code lives in `/src`. Do not create subdirectories or additional source files.
- `stream.py` must remain a single self-contained file. Do not split it into modules.
- Do not commit `config.json`, `.env`, `stream.pid`, `stream.stop`, or anything under `logs/`. These are runtime-generated and must never appear in version control.
- Do not add a `.gitignore` unless it is explicitly requested — if one is added, it must ignore `src/config.json`, `src/.env`, `src/*.pid`, `src/*.stop`, and `src/logs/`.

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
| `config.json` | `--install` | All non-secret configuration |
| `.env` | `--install` | All secrets and auto-refreshed tokens |
| `stream.pid` | `--start` | PID of the running stream process |
| `stream.stop` | `--stop` or SIGINT/SIGTERM | Sentinel file that suppresses retries |
| `logs/YYYY-MM-DD.log` | `--start` | Daily log file |

---

## Configuration Contract

Every config key must be **used** by the script. Do not add dead config fields. When adding a new key, ensure the script reads and acts on it.

### config.json — non-secret values only

```json
{
  "google": {
    "clientId": ""
  },
  "stream": {
    "rtspUrl": "",
    "videoCodec": "copy",
    "audioCodec": "copy",
    "mute": false
  },
  "youtube": {
    "broadcastTitle": "My Location: {date}",
    "privacy": "public",
    "categoryId": "22",
    "enableMonitorStream": false,
    "broadcastId": "",
    "streamId": "",
    "streamURL": "",
    "backupStreamUrl": "",
    "streamKey": ""
  },
  "pidFile": "./stream.pid",
  "stopSentinel": "./stream.stop",
  "logDir": "./logs",
  "logRetentionDays": 15,
  "retryDelaySecs": 5,
  "terminal": "gnome-terminal",
  "cron": {
    "start": "30 6 1-31 4-10 *",
    "stop": "25 18 1-31 4-10 *"
  }
}
```

### .env — secrets only

```
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=
GOOGLE_ACCESS_TOKEN=
```

**Rules:**
- Every runtime value must come from `config.json` or `.env`. No hardcoded strings, paths, URLs, or defaults may exist inside `stream.py`.
- `config.json` keys must never contain secrets. `.env` keys must never contain non-secret config.
- When adding a new configurable value, determine whether it is a secret first. If secret, it goes in `.env`. If not, it goes in `config.json`.
- `{date}` in `broadcastTitle` is the only supported interpolation token. Do not add others without updating this document.
- When adding or removing config keys, update: this document, `README.md`, `REQUIREMENTS.md`, `config.example.json`, and `example.env` (as applicable).

---

## CLI Interface

The script exposes exactly three switches. Do not add, rename, or remove switches without updating this document and `README.md`.

| Switch | Behavior |
|--------|----------|
| `--install` | Interactive setup: prompts for config, writes files, installs deps, runs OAuth, creates YouTube resources, registers cron |
| `--start` | Resumes streaming to the existing YouTube broadcast. Runs in the foreground, blocking the terminal. |
| `--stop` | Writes the stop sentinel, signals the running process, waits for graceful shutdown. The broadcast is **not** completed — it stays alive for reuse. |

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

The broadcast and stream are created **once** during `--install` and **reused** on every `--start`/`--stop` cycle. This ensures a stable YouTube URL that can be embedded in a webpage.

### During `--install`:
1. `liveBroadcasts.insert` — create broadcast (with `enableAutoStop: false` to prevent auto-completion)
2. `liveStreams.insert` — create stream resource
3. `liveBroadcasts.bind` — bind stream to broadcast
4. Save `broadcastId`, `streamId`, `streamURL`, `backupStreamUrl`, `streamKey` to `config.json`
5. Apply `categoryId` to the broadcast's associated video

### During `--start`:
1. Read `broadcastId`, `streamURL`, `streamKey` from config
2. Update the broadcast title with today's date via `liveBroadcasts.update`
3. Launch ffmpeg pointing at the RTMP URL
4. Wait for stream to become active
5. If broadcast is not already live: `liveBroadcasts.transition` → `testing` → `live`
6. If broadcast is already live: skip transition, just stream

### During `--stop`:
1. Stop the ffmpeg process
2. The broadcast is **not** transitioned to `complete` — it remains alive
3. The URL stays stable for the next `--start`

### Retry behavior:
- On retry, the script reconnects to the **same** broadcast — it does not create a new one
- Retries alternate between the primary `streamURL` and `backupStreamUrl` (if configured)
- If a broadcast reaches `complete` state (e.g., YouTube auto-completed it), `--start` will error and instruct the user to run `--install` to create a new broadcast

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

- Log directory: value of `logDir` in `config.json`
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

`--install` self-registers two crontab entries using the expressions in `config.json` under `cron.start` and `cron.stop`. The default schedule runs April 1 through October 31:

- **Start:** `30 6 1-31 4-10 *` (6:30am daily) — opens a terminal window titled "BC Free Flight Stream"
- **Stop:** `25 18 1-31 4-10 *` (6:25pm daily) — runs directly without a terminal window

The start cron opens a single terminal window. When the stop cron fires, the stream process exits and the terminal window closes. This prevents terminal window accumulation over time — only one window exists at a time.

`--install` must not create duplicate crontab entries if run more than once.

---

## GitHub Actions

The release workflow lives at `.github/workflows/release.yml`.

**Triggers:**
- Push to `main`
- Manual `workflow_dispatch`

**Versioning:**
- Reads the latest release tag from the GitHub API
- Increments the patch version (e.g. `v1.0.4` → `v1.0.5`)
- Starts at `v1.0.0` if no releases exist
- Version is always determined dynamically — never hardcoded

**Release artifact:**
- `src/stream.py` only, attached as `stream.py` (no path prefix)
- Changelog body: commits since the previous tag, or "Initial release"
- Uses `GITHUB_TOKEN` exclusively — no additional secrets

---

## What Not To Do

- Do not split `stream.py` into multiple files
- Do not add a `requirements.txt` or `setup.py`
- Do not hardcode any value that belongs in `config.json` or `.env`
- Do not log or print secrets, tokens, or stream keys
- Do not add a `--update` flag or any self-update mechanism
- Do not commit runtime files (`config.json`, `.env`, `*.pid`, `*.stop`, `logs/`)
- Do not add new CLI switches without updating this document and `README.md`
- Do not add new config keys without updating the config contract in this document, `README.md`, `REQUIREMENTS.md`, and example files
- Do not install ffmpeg or system packages during `--start` or `--stop`
- Do not transition the broadcast to `complete` during `--stop` — the URL must remain stable
- Do not create new YouTube broadcasts on `--start` — always reuse the existing one from config
- Do not add dead config fields — every key must be read and used by the script
