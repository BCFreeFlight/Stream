# Configuration

Two files live beside `stream.py`, both created by `--install` and never committed:

- **`config.toml`** — all non-secret values
- **`.env`** — secrets and auto-refreshed tokens

The split is a hard rule: secrets never appear in `config.toml`, non-secrets never appear in `.env`. See [ADR-0005](adr/0005-config-secrets-split.md).

Every key is **read and acted on** by the script — there are no dead fields. Edit `config.toml` by hand or via [`--set-property`](cli-reference.md#--set-property).

## config.toml

### Root

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `pidFile` | string | `./stream.pid` | PID file path |
| `stopSentinel` | string | `./stream.stop` | Stop sentinel file path |
| `logDir` | string | `./logs` | Log directory |
| `logRetentionDays` | integer | `15` | Delete logs older than this many days (pruned on `--start`) |
| `logLevel` | string | `info` | Persistent verbosity: `debug`, `info`, `warning`, `error` |
| `retryDelaySecs` | integer | `5` | Seconds between retry attempts |
| `terminal` | string | *(auto-detected)* | Terminal emulator for the start cron job |

### `[google]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `clientId` | string | *(prompted)* | OAuth 2.0 client ID (not secret; the secret is in `.env`) |

### `[stream]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `rtspUrl` | string | *(prompted)* | Full RTSP camera URL. Credentials are percent-encoded on install — see [streaming](streaming.md#rtsp-credential-encoding) |
| `videoCodec` | string | `copy` | ffmpeg video codec (`copy` = passthrough, no re-encode) |
| `audioCodec` | string | `copy` | ffmpeg audio codec (ignored when `mute = true`) |
| `mute` | boolean | `false` | If `true`, replaces camera audio with a silent AAC track — see [ADR-0011](adr/0011-silent-audio-when-muted.md) |

### `[youtube]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `broadcastTitle` | string | `My Location: {date}` | Title template; `{date}` → today's ISO date (the only supported token) |
| `privacy` | string | `public` | Live broadcast privacy: `public`, `unlisted`, `private` |
| `categoryId` | string | `22` | YouTube category ID (22 = People & Blogs) |
| `enableMonitorStream` | boolean | `false` | Enable YouTube's monitor stream |
| `embeddable` | boolean | `true` | Allow embedding on external sites (set on both broadcast and video) — see [ADR-0010](adr/0010-embeddable-dual-flag.md) |
| `enableDvr` | boolean | `false` | Allow viewers to rewind/scrub the live feed |
| `archivePrivacy` | string | `private` | Privacy applied to the archived VOD after `--stop` |
| `broadcastId` | string | *(auto)* | Persistent broadcast ID; created by `--install`, rotated by `--start` |
| `streamURL` | string | *(auto)* | Primary RTMP ingest URL |
| `backupStreamUrl` | string | *(auto)* | Backup RTMP ingest URL (used on odd retry attempts) |
| `streamKey` | string | *(auto)* | RTMP stream key; the stream ID is resolved from this at runtime, never persisted |

### `[cron]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | boolean | `true` | If `false`, no cron entries are registered |
| `start` | string | `30 6 1-31 4-10 *` | Daily start (6:30 AM, Apr–Oct) |
| `stop` | string | `25 18 1-31 4-10 *` | Daily stop (6:25 PM, Apr–Oct) |
| `autoUpdate` | boolean | `false` | If `true`, registers an update cron — opt-in by design ([ADR-0017](adr/0017-optional-auto-update.md)) |
| `update` | string | `0 0 * * *` | Update check schedule (only used when `autoUpdate = true`) |

### `[update]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `skippedVersion` | string | `""` | Set by `--roll-back`; `--update` skips releases ≤ this until a newer one ships. Cleared on successful update. See [ADR-0018](adr/0018-skipped-version-marker.md) |

## .env

Secrets only. Never share or commit.

| Key | Written by | Description |
|-----|-----------|-------------|
| `GOOGLE_CLIENT_SECRET` | `--install` prompt | OAuth 2.0 client secret |
| `GOOGLE_REFRESH_TOKEN` | `--install` OAuth flow | Long-lived refresh token |
| `GOOGLE_ACCESS_TOKEN` | runtime | Short-lived access token, auto-refreshed |

## Schema migration

`config.toml` is upgraded automatically. On `--start` and `--update`, `_migrate_config()` deep-merges `CONFIG_DEFAULTS` into the existing file and writes back any missing keys. Adding a key to `CONFIG_DEFAULTS` is sufficient to backfill every existing install — no per-key migration code. See [ADR-0006](adr/0006-declarative-config-migration.md).

## Terminal auto-detection

`--install` sets `terminal` by probing PATH in order:

```
gnome-terminal → xterm → konsole → xfce4-terminal → (fallback) xterm
```

The cron line format differs per emulator; see [scheduling](scheduling.md#terminal-handling).

## Type coercion (`--set-property`)

Values are coerced to the schema type:

| Type | Accepted input |
|------|----------------|
| boolean | `true`/`false`/`yes`/`no`/`1`/`0` (case-insensitive) |
| integer | any whole-number string |
| string | passed through as-is |

Unknown keys and section paths are rejected.
