# stream.py — Build Prompt

Build a Python script called `stream.py` that proxies an RTSP stream to YouTube Live using ffmpeg. The script self-installs all required Python dependencies via `pip` and installs `ffmpeg` via `apt` if missing. All user-facing strings (prompts, instructions, messages) are externalized to `resources.json`.

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
    ├── resources.json
    ├── config.example.json
    └── example.env
```

All code lives inside `/src`. The root contains documentation and the `.github` workflows directory. Runtime files (`config.json`, `.env`, `*.pid`, `*.stop`, `logs/`) are generated locally by `--install` and never committed.

---

## Key Design Decisions

### Persistent Broadcast (Stable URL)

The YouTube broadcast is created **once** during `--install` and **reused** on every `--start`/`--stop` cycle. The broadcast is never transitioned to "complete" during `--stop`, so the URL remains stable and can be embedded in a webpage.

### String Externalization

All non-logging user-facing strings (prompts, instructions, validation messages, setup guides) live in `src/resources.json`. The script loads this file at startup. This keeps content separate from logic and makes it easy to update text without modifying code.

### Code Quality

All code follows SOLID principles with a focus on clean code and single responsibility methods. Functions are short, well-named, and human-readable.

---

## README.md

Write a `README.md` for public consumption at the repository root. It must cover:

- **What it is** — a brief description of the tool and its purpose, noting the stable broadcast URL
- **Requirements** — link to `REQUIREMENTS.md`
- **Installation** — step-by-step: download the release, run `--install`, what to expect
- **Google Cloud setup** — how to create a project, enable the YouTube Data API v3, create OAuth 2.0 credentials, and obtain the client ID and secret
- **Configuration reference** — every `config.json` key documented with type, default, and description
- **`.env` reference** — every key documented, noting which are written automatically and which must be provided
- **Usage** — `--start`, `--stop`, `--install` with examples
- **Crontab** — explain that `--install` registers the cron entries automatically and what schedule they use
- **Logs** — where they live, format, retention policy
- **Releases / updating** — link to the GitHub releases page; instruct users to re-run the install curl command to update
- **License**

---

## REQUIREMENTS.md

Document all dependencies: Python version, system dependencies, Python packages with purposes, external services, and runtime files.

---

## GitHub Actions — release.yml

Create a GitHub Actions workflow at `.github/workflows/release.yml`:

### Triggers
- On every push to `main`
- On manual dispatch via `workflow_dispatch`

### Auto-increment versioning
- Read the latest existing release tag (e.g. `v1.0.4`), increment patch by 1
- If no releases exist, start at `v1.0.0`
- Version is determined dynamically — never hardcoded

### Release artifacts
- `src/stream.py` attached as `stream.py`
- `src/resources.json` attached as `resources.json`
- Tag, title, and auto-generated changelog from commits since previous tag

### Required secret
- `GITHUB_TOKEN` only — no additional secrets

---

## CLI Interface

The script accepts exactly three switches:

- `--install` — first-time setup: guides user through Google Cloud setup if needed, prompts for all configuration, writes `config.json` and `.env`, installs deps, runs OAuth flow, creates YouTube broadcast/stream, registers cron
- `--start` — resumes streaming to the existing YouTube broadcast
- `--stop` — gracefully stops the stream (broadcast stays alive for reuse)

---

## resources.json

All non-logging user-facing strings live in `src/resources.json`. This includes:

- Install prompts (labels, defaults, validation messages)
- Google Cloud setup walkthrough instructions
- Success/error messages shown to the user
- Section headers and summaries

The script loads this file once at startup via `json.load()`. Logging messages (timestamps, levels, ffmpeg output) remain in the code — they are operational, not user-facing content.

---

## --install Interactive Flow

### Google Cloud Setup Walkthrough

When the user runs `--install` and does not yet have a `clientId` or `clientSecret`, the script should walk them through the Google Cloud setup:

1. Display step-by-step instructions (from `resources.json`) explaining how to:
   - Go to the Google Cloud Console
   - Create a project
   - Enable the YouTube Data API v3
   - Create OAuth 2.0 credentials (Desktop app type)
   - Copy the client ID and secret
2. After each instructional block, pause and prompt the user to continue or paste the value
3. All instructional text comes from `resources.json`

### Configuration Prompts

Prompt for every value in `config.json` and `.env` in a logical order:

1. `google.clientId` — with Google Cloud setup guide if empty
2. `GOOGLE_CLIENT_SECRET` — with Google Cloud setup guide if empty
3. `stream.rtspUrl` — full RTSP URL of the incoming stream
4. `stream.videoCodec` — default `copy`
5. `stream.audioCodec` — default `copy`
6. `stream.mute` — yes/no, default `no`
7. `youtube.broadcastTitle` — default `Coopers Launch: {date}`
8. `youtube.privacy` — public/unlisted/private, default `public`
9. `youtube.categoryId` — default `22`
10. `youtube.broadcastId` — existing broadcast ID, or empty to auto-create
11. `youtube.streamURL` — RTMP URL, or empty to auto-create
12. `youtube.backupStreamUrl` — backup RTMP URL (optional)
13. `youtube.streamKey` — stream key, or empty to auto-create
14. `cron.start` — default `30 6 1-31 4-10 *`
15. `cron.stop` — default `25 18 1-31 4-10 *`

### After Collecting Values

1. Write `config.json` with all non-secret values
2. Write `.env` with all secret values
3. Install `ffmpeg` if not on PATH
4. Run OAuth 2.0 browser flow
5. Create YouTube broadcast and stream via API (if not provided by user)
6. Bind stream to broadcast, apply category
7. Save broadcast/stream details to `config.json`
8. Detect terminal emulator, register cron entries
9. Print success summary including the stable YouTube URL

---

## config.json

All non-secret configuration. Every key must be read and used by the script.

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
    "broadcastTitle": "Coopers Launch: {date}",
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

---

## .env

```
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=       # written automatically after OAuth flow
GOOGLE_ACCESS_TOKEN=        # written and refreshed automatically at runtime
```

---

## --start Behavior

1. Validate that `broadcastId`, `streamURL`, and `streamKey` exist in config
2. Clean up any `stream.stop` sentinel file
3. Kill existing process if `stream.pid` points to a running process
4. Write PID, delete old logs
5. Authenticate (refresh token or re-auth if needed)
6. Update broadcast title with today's date
7. Launch ffmpeg pointing at `streamURL`/`streamKey`
8. Wait for stream to become active, then ensure broadcast is live (transition if needed)
9. Relay ffmpeg output to log and stdout
10. On signal (SIGINT/SIGTERM): write sentinel, kill ffmpeg, clean up, exit
11. On unexpected ffmpeg exit: retry with alternating primary/backup RTMP URLs

---

## --stop Behavior

1. Write the `stream.stop` sentinel file
2. Send `SIGTERM` to the running process
3. Wait for process exit
4. Clean up `stream.pid` and `stream.stop`
5. Log clean shutdown — the broadcast is NOT transitioned to "complete"

---

## Crontab

- **Start cron:** opens a terminal window titled "BC Free Flight Stream" and runs `--start`
- **Stop cron:** runs `--stop` directly (no terminal window)

This prevents terminal window accumulation — only one window exists at a time. When `--stop` fires, the process exits and the terminal closes. The next `--start` opens a fresh window.

---

## Constraints

- All user-facing strings (prompts, instructions, messages) live in `resources.json`, not in code
- All configuration comes from `config.json` or `.env` — no hardcoded values
- Self-installs missing Python packages at the top of the script
- SOLID principles: clean code, single responsibility methods, maximum readability
- Compatible with Linux Mint / Ubuntu-based systems
- Python 3.8+
