# BC Free Flight Stream

A self-contained Python script that proxies an RTSP camera stream to YouTube Live via ffmpeg. It manages the YouTube broadcast lifecycle, handles OAuth 2.0 authentication, retries automatically on failure, and self-registers daily cron jobs for unattended operation.

The broadcast URL is **stable** — once created during `--install`, the same YouTube URL is reused every time the stream starts and stops. This makes it safe to embed in a webpage.

## Requirements

See [REQUIREMENTS.md](REQUIREMENTS.md) for the full list. In brief:

- Python 3.8+
- Linux Mint / Ubuntu-based system
- A Google Cloud project with the YouTube Data API v3 enabled
- An RTSP-capable camera

## Quick Install

Open a terminal, `cd` to the directory where you want the script to live, and run:

```bash
curl -fLO https://github.com/BCFreeFlight/Stream/releases/latest/download/stream.py && python3 stream.py --install
```

This downloads the latest release and launches the interactive setup wizard. Any companion files (like `resources.toml`) are downloaded automatically on first run.

## Installation (step by step)

1. Download the latest release:

   ```bash
   curl -fLO https://github.com/BCFreeFlight/Stream/releases/latest/download/stream.py
   ```

2. Run the interactive setup:

   ```bash
   python3 stream.py --install
   ```

   This will:
   - Prompt for all configuration values
   - Install `ffmpeg` if not already present
   - Install required Python packages
   - Open a browser for Google OAuth 2.0 authorization
   - Create a YouTube broadcast and stream (or use ones you provide)
   - Write `config.toml` and `.env` beside the script
   - Detect your terminal emulator and register cron jobs
   - Print the stable YouTube URL for your stream

## Google Cloud Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services > Library**
4. Search for **YouTube Data API v3** and click **Enable**
5. Navigate to **APIs & Services > Credentials**
6. Click **Create Credentials > OAuth client ID**
7. Select **Desktop app** as the application type
8. Copy the **Client ID** and **Client Secret** — you will need these during `--install`

## Configuration Reference

### config.toml

All non-secret configuration. Created by `--install` beside the script. See [`config.example.toml`](src/config.example.toml) for the template.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `google.clientId` | string | *(prompted)* | Google OAuth 2.0 client ID |
| `stream.rtspUrl` | string | *(prompted)* | Full RTSP URL of the camera stream |
| `stream.videoCodec` | string | `copy` | ffmpeg video codec |
| `stream.audioCodec` | string | `copy` | ffmpeg audio codec |
| `stream.mute` | boolean | `false` | If `true`, audio is stripped (`-an`) |
| `youtube.broadcastTitle` | string | `My Location: {date}` | Title template; `{date}` resolves to the current ISO date |
| `youtube.privacy` | string | `public` | Broadcast privacy: `public`, `unlisted`, or `private` |
| `youtube.categoryId` | string | `22` | YouTube category ID (22 = People & Blogs) |
| `youtube.enableMonitorStream` | boolean | `false` | Enable the YouTube monitor stream |
| `youtube.broadcastId` | string | *(auto-created or prompted)* | Persistent YouTube broadcast ID |
| `youtube.streamId` | string | *(auto-populated)* | YouTube stream resource ID |
| `youtube.streamURL` | string | *(auto-created or prompted)* | RTMP ingest URL |
| `youtube.backupStreamUrl` | string | *(auto-created or prompted)* | Backup RTMP ingest URL (used on retry) |
| `youtube.streamKey` | string | *(auto-created or prompted)* | Stream key for the RTMP URL |
| `pidFile` | string | `./stream.pid` | PID file path |
| `stopSentinel` | string | `./stream.stop` | Stop sentinel file path |
| `logDir` | string | `./logs` | Log directory |
| `logRetentionDays` | integer | `15` | Days to keep log files |
| `retryDelaySecs` | integer | `5` | Seconds between retries |
| `terminal` | string | *(auto-detected)* | Terminal emulator for cron |
| `cron.start` | string | `30 6 1-31 4-10 *` | Cron expression for daily start |
| `cron.stop` | string | `25 18 1-31 4-10 *` | Cron expression for daily stop |

### .env

Secrets live in `.env`, created by `--install`. See [`example.env`](src/example.env). Never share or commit this file.

| Key | Written by | Description |
|-----|-----------|-------------|
| `GOOGLE_CLIENT_SECRET` | `--install` prompt | OAuth 2.0 client secret |
| `GOOGLE_REFRESH_TOKEN` | `--install` OAuth flow | Refresh token (auto-written) |
| `GOOGLE_ACCESS_TOKEN` | Runtime | Access token (auto-refreshed) |

## Usage

### Start the stream

```bash
python3 stream.py --start
```

Resumes streaming to the existing YouTube broadcast. Updates the broadcast title with today's date. If ffmpeg exits unexpectedly, it retries automatically — alternating between the primary and backup RTMP URLs.

### Stop the stream

```bash
python3 stream.py --stop
```

Stops the ffmpeg process gracefully and transitions the broadcast to `complete`, archiving it as a VOD on the channel. The next `--start` will create a fresh broadcast automatically.

### Re-run setup

```bash
python3 stream.py --install
```

Re-running `--install` overwrites configuration and creates new YouTube resources if needed.

### Update to the latest version

```bash
python3 stream.py --update
```

Backs up the current `stream.py` and `resources.toml` into a versioned zip in the `backup/` directory (e.g., `backup/stream.v0.1.3.bak.zip`), then downloads and replaces both files from the latest GitHub release.

### Roll back to a previous version

Roll back to a specific version:

```bash
python3 stream.py --roll-back v0.1.2
```

Or run it without a version to choose interactively from available backups:

```bash
python3 stream.py --roll-back
```

```
Available backups:
  1. v0.1.3  (12 KB)
  2. v0.1.2  (11 KB)
  3. v0.1.1  (11 KB)

Enter number to restore (or 'q' to cancel):
```

Backups are created automatically by `--update` and stored in the `backup/` directory beside the script.

## Crontab

`--install` registers two cron entries (default: April through October):

| Job | Default Schedule | Behavior |
|-----|-----------------|----------|
| Start | `30 6 1-31 4-10 *` (6:30 AM) | Opens a terminal window and starts streaming |
| Stop | `25 18 1-31 4-10 *` (6:25 PM) | Runs directly (no terminal) to stop the stream |

The start job opens a single terminal window titled "BC Free Flight Stream". When the stop job runs, the stream process exits and the terminal window closes. This prevents terminal window accumulation over time.

Running `--install` again updates entries without creating duplicates.

## Logs

- **Location:** `logs/` directory beside the script
- **Format:** `[ISO-8601-timestamp] [LEVEL] message`
- **Levels:** `INFO`, `WARN`, `ERROR`
- **Retention:** Files older than `logRetentionDays` (default 15) are deleted on each `--start`
- All output is mirrored to the terminal in real time

## Releases / Updating

Releases are published automatically on every push to `main`. To update:

```bash
python3 stream.py --update
```

Or manually:

```bash
curl -fLO https://github.com/BCFreeFlight/Stream/releases/latest/download/stream.py
```

See the [Releases page](https://github.com/BCFreeFlight/Stream/releases) for changelogs.

## License

MIT
