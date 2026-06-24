---
title: AGENTS.md
description: Navigation map and quick-reference index for all project documentation, guides, YouTube API references, and Architecture Decision Records in the BC Free Flight Stream project.
category: overview
tags: [documentation, architecture, youtube, ffmpeg, cron]
---

# AGENTS.md

Single-file Python script that proxies an RTSP camera to YouTube Live via ffmpeg.
Self-installs dependencies, manages OAuth, creates and rotates YouTube broadcasts daily,
and self-registers cron jobs for automatic start/stop/recovery.

All code lives in `src/stream.py`. Do not split it.

---

## Documentation map

| What | Where |
|------|-------|
| Project rules, config contract, CLI reference | [`CLAUDE.md`](CLAUDE.md) |
| User-facing quick start | [`README.md`](README.md) |
| System and dependency requirements | [`REQUIREMENTS.md`](REQUIREMENTS.md) |
| All docs index | [`docs/README.md`](docs/README.md) |

### Guides

| Topic | File |
|-------|------|
| Architecture & data flow | [`docs/architecture.md`](docs/architecture.md) |
| Installation / uninstall / reinstall | [`docs/installation.md`](docs/installation.md) |
| Configuration keys | [`docs/configuration.md`](docs/configuration.md) |
| CLI switches | [`docs/cli-reference.md`](docs/cli-reference.md) |
| Google OAuth flow | [`docs/authentication.md`](docs/authentication.md) |
| Broadcast lifecycle (project view) | [`docs/broadcast-lifecycle.md`](docs/broadcast-lifecycle.md) |
| ffmpeg command, mute, retry loop | [`docs/streaming.md`](docs/streaming.md) |
| PID file, stop sentinel, signals | [`docs/process-management.md`](docs/process-management.md) |
| Crontab, `--recover` | [`docs/scheduling.md`](docs/scheduling.md) |
| `--update`, `--roll-back`, backups | [`docs/updates-and-rollback.md`](docs/updates-and-rollback.md) |
| Log format, levels, retention | [`docs/logging.md`](docs/logging.md) |
| Testing, repo rules, release | [`docs/development.md`](docs/development.md) |
| Troubleshooting | [`docs/troubleshooting.md`](docs/troubleshooting.md) |

### YouTube Live API reference

| Topic | File |
|-------|------|
| Overview, quick reference | [`docs/youtube/README.md`](docs/youtube/README.md) |
| OAuth, scopes, quota | [`docs/youtube/authentication.md`](docs/youtube/authentication.md) |
| `liveBroadcasts` — all methods | [`docs/youtube/broadcasts.md`](docs/youtube/broadcasts.md) |
| `liveStreams` — ingest, health | [`docs/youtube/streams.md`](docs/youtube/streams.md) |
| `videos` — embeddable, category, archive | [`docs/youtube/videos.md`](docs/youtube/videos.md) |
| Gotchas and known quirks | [`docs/youtube/gotchas.md`](docs/youtube/gotchas.md) |

### Architecture Decision Records

All ADRs live in [`docs/adr/`](docs/adr/README.md).

| # | Decision |
|---|----------|
| 0001 | Single-file script distribution |
| 0002 | Self-installing dependencies |
| 0003 | Self-download release assets |
| 0004 | TOML over JSON for config |
| 0005 | Config/secrets split (toml vs .env) |
| 0006 | Declarative config migration |
| 0007 | Fresh broadcast on every `--start` |
| 0008 | Complete broadcast on `--stop` |
| 0009 | Stable channel embed URL |
| 0010 | Embeddable: dual broadcast + video flags |
| 0011 | Silent audio track when muted |
| 0012 | Resolve stream ID from key at runtime |
| 0013 | Primary/backup RTMP alternation on retry |
| 0014 | PID file + stop sentinel pattern |
| 0015 | Cron self-registration |
| 0016 | `@reboot` crash recovery |
| 0017 | Optional auto-update |
| 0018 | Skipped-version marker |
| 0019 | Title update after `ensure_broadcast_live` |
| 0020 | Two-tier YouTube API layering |
| 0021 | Externalized user-facing strings |
| 0022 | Force account selection on OAuth |
| 0023 | Dynamic patch versioning |
| 0024 | Idempotent install |
