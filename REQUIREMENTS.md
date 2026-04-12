# Requirements

## System

- **OS:** Linux Mint / Ubuntu-based distribution
- **Python:** 3.8 or later
- **ffmpeg:** Installed via `apt install -y ffmpeg` (handled automatically by `--install`)

## Python Packages

All Python packages are self-installed by `stream.py` on first run. No `requirements.txt` is used — dependency declarations live only inside the script.

| Package | Purpose |
|---------|---------|
| `google-auth` | Google OAuth 2.0 credential management and token refresh |
| `google-auth-oauthlib` | Browser-based OAuth 2.0 flow for initial authorization |
| `google-api-python-client` | YouTube Data API v3 client for broadcast/stream management |
| `python-dotenv` | Loads secrets from `.env` file into environment variables |
| `requests` | HTTP transport used internally by `google-auth` |

## External Services

- **Google Cloud** project with the **YouTube Data API v3** enabled
- OAuth 2.0 credentials (Desktop app type) from the Google Cloud Console
- An RTSP-capable camera accessible from the host machine

## Runtime Files

These files are generated locally beside `stream.py` and must never be committed:

| File | Created by | Purpose |
|------|-----------|---------|
| `config.json` | `--install` | All non-secret configuration |
| `.env` | `--install` | Secrets and auto-refreshed tokens |
| `stream.pid` | `--start` | PID of the running stream process |
| `stream.stop` | `--stop` / signal handler | Sentinel that suppresses retries |
| `logs/YYYY-MM-DD.log` | `--start` | Daily log file |
| `backup/stream.*.bak.zip` | `--update` | Versioned backups for roll-back |
