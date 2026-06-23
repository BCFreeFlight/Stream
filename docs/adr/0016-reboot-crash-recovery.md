# ADR-0016: `@reboot` `--recover` crash recovery

**Status:** Accepted

## Context

The host can lose power or reboot mid-stream. Without intervention the stream stays down until the next morning's start cron, losing hours of coverage.

## Decision

`--install` registers an `@reboot` cron entry that runs `--recover` headless at boot. `--recover`:

- no-ops if a stream is already running;
- delegates to `--start` if the current time is inside the daily window;
- exits cleanly if outside the window.

The window check (`is_in_stream_window`) compares the most recent fire times of `cron.start` and `cron.stop` via `croniter` — reusing real cron semantics (including day/month ranges) rather than reimplementing them — with a 1-second epsilon so the exact start second counts as inside.

## Consequences

- A reboot during the streaming window resumes the stream automatically.
- Reboots outside the window do nothing, as intended.
- Adds `croniter` as a dependency.
