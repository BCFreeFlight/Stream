---
title: Logging
description: Reference for log output format, levels, retention, and secret hygiene in the BC Free Flight Stream script.
category: reference
tags:
  - logging
  - ffmpeg
  - configuration
  - retention
---

# Logging

## Output

Every log line is written to a daily file **and** mirrored to stdout in real time.

- **Location:** `logDir` (default `logs/`), beside the script
- **File:** one per day, `YYYY-MM-DD.log`
- **Format:** `[2026-04-12T06:30:00+00:00] [LEVEL] message` (UTC, ISO-8601)

## Levels

| Level | Numeric | Use |
|-------|:---:|-----|
| `DEBUG` | 0 | ffmpeg output, polling status, internal transitions |
| `INFO` | 1 | milestones (broadcast created, live, stopped) |
| `WARN` | 2 | recoverable problems (refresh failed, retry) |
| `ERROR` | 3 | unrecoverable errors |

A message is emitted only if its level ≥ the configured threshold. Default is `info`, which suppresses ffmpeg progress noise and shows only milestones.

## Setting the level

| Method | Scope |
|--------|-------|
| `logLevel` in `config.toml` | persistent |
| `--log-level LEVEL` | current run only |
| `--set-property logLevel debug` | persistent |

`--log-level` takes precedence over config for that run. Invalid values exit with an error.

## ffmpeg output

- All ffmpeg stdout/stderr is logged with the `[ffmpeg]` prefix.
- Lines containing `warning` are promoted to `WARN`; the rest are `DEBUG` (hidden at the default `info` level). See [streaming](streaming.md#output-relay).

## Retention

On each `--start`, log files older than `logRetentionDays` (default 15) are deleted. The date is parsed from the filename stem; unparseable names are skipped.

## Secret hygiene

Secrets, tokens, and stream keys are never written to logs. The ffmpeg launch line redacts the stream key as `<REDACTED>`.
