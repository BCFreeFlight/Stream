---
title: CLI Reference
description: Complete reference for all command-line switches supported by stream.py, including their behavior and sequencing.
category: reference
tags:
  - cli
  - install
  - streaming
  - cron
  - configuration
---

# CLI Reference

Exactly one command switch is required per invocation (mutually exclusive). `--log-level` is an optional modifier.

| Switch | Summary |
|--------|---------|
| `--install` | Idempotent first-time/repeat setup |
| `--uninstall` | Stop stream, archive broadcast, remove cron (config preserved) |
| `--reinstall` | Destructive clean-slate setup |
| `--start` | Create fresh broadcast and stream (foreground, blocking) |
| `--stop` | Graceful stop + archive broadcast as VOD |
| `--recover` | Resume stream if inside the daily window (boot recovery) |
| `--update` | Back up and download the latest release |
| `--roll-back [VERSION]` | Restore from a backup |
| `--set-property KEY VALUE` | Set a `config.toml` value by dot-notation key |
| `--log-level LEVEL` | Override verbosity for this run only |

---

## `--install`

Loads existing config and prompts **only** for empty/missing values, so re-running is safe and non-destructive. See [installation](installation.md).

Steps: prompt → write `config.toml`/`.env` → install ffmpeg if missing → OAuth (reused if a valid refresh token exists) → create/bind YouTube resources → detect terminal → register cron.

## `--uninstall`

Stops any running stream, archives the broadcast, and removes all cron entries. **Preserves** `config.toml` and `.env` so a later `--install` reuses credentials.

## `--reinstall`

Requires typing `yes`. Chains `--uninstall` → delete `config.toml` + `.env` → `--install`. Preserves `logs/` and `backup/`.

## `--start`

Foreground, blocking. Retires any active broadcast, creates a fresh one ([ADR-0007](adr/0007-fresh-broadcast-per-start.md)), launches ffmpeg, and retries indefinitely on failure until `--stop` or a signal. See [broadcast lifecycle](broadcast-lifecycle.md) and [streaming](streaming.md).

## `--stop`

Writes the stop sentinel, sends `SIGTERM` to the running process, waits for exit, then transitions the broadcast to `complete` (archived as a VOD) and applies `archivePrivacy`. See [ADR-0008](adr/0008-complete-broadcast-on-stop.md).

## `--recover`

If a stream is already running, no-op. Else, if the current time is inside the `cron.start`/`cron.stop` window, delegates to `--start`; otherwise exits cleanly. Registered as an `@reboot` cron entry. See [scheduling](scheduling.md#--recover) and [ADR-0016](adr/0016-reboot-crash-recovery.md).

## `--update`

Backs up `stream.py`, `resources.toml`, `config.toml` to `backup/stream.<version>.bak.zip`, then downloads `stream.py` and `resources.toml` from the latest release. Skips releases ≤ `update.skippedVersion`. Re-registers cron after success. See [updates](updates-and-rollback.md).

## `--roll-back [VERSION]`

Restores `stream.py`, `resources.toml`, `config.toml` from a backup. Without a version, lists backups for interactive selection. Records the rolled-back-from version as `update.skippedVersion` so the next `--update` won't undo it.

## `--set-property KEY VALUE`

Sets a single `config.toml` value by dot-notation (e.g. `cron.autoUpdate true`). Repeatable for multiple keys in one call. Validates against the schema; rejects unknown keys. See [configuration](configuration.md#type-coercion---set-property).

```bash
python3 stream.py --set-property youtube.privacy private --set-property logRetentionDays 30
```

## `--log-level LEVEL`

Overrides verbosity for the current run only (`config.toml` unchanged). Valid: `debug`, `info`, `warning`, `error` (case-insensitive). Invalid values exit with an error.

```bash
python3 stream.py --start --log-level debug
```
