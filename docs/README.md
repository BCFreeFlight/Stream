# Documentation

Reference documentation for **BC Free Flight Stream** — a single-file Python script that proxies an RTSP camera to YouTube Live via ffmpeg.

## Guides

| Doc | Covers |
|-----|--------|
| [Architecture](architecture.md) | High-level design, layers, data flow, file layout |
| [Installation](installation.md) | `--install`, `--uninstall`, `--reinstall`, idempotency |
| [Configuration](configuration.md) | Every `config.toml` and `.env` key |
| [CLI Reference](cli-reference.md) | All command-line switches |
| [Authentication](authentication.md) | Google OAuth 2.0 flow and token lifecycle |
| [Broadcast Lifecycle](broadcast-lifecycle.md) | YouTube broadcast/stream state machine |
| [Streaming & ffmpeg](streaming.md) | ffmpeg command, mute, RTSP encoding, retry loop |
| [Process Management](process-management.md) | PID file, stop sentinel, signals |
| [Scheduling](scheduling.md) | Crontab registration and `--recover` |
| [Updates & Rollback](updates-and-rollback.md) | `--update`, `--roll-back`, backups, skipped versions |
| [Logging](logging.md) | Log format, levels, retention |
| [Development](development.md) | Repo rules, testing, release workflow |
| [Troubleshooting](troubleshooting.md) | Common failures and fixes |

## Architecture Decision Records

Significant design decisions and their rationale are recorded in [`adr/`](adr/README.md).

## Source of truth

- [`CLAUDE.md`](../CLAUDE.md) — authoritative project rules and contracts
- [`README.md`](../README.md) — user-facing quick start
- [`REQUIREMENTS.md`](../REQUIREMENTS.md) — system and dependency requirements
- `src/stream.py` — the single-file implementation
