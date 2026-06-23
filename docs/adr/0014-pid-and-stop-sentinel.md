# ADR-0014: PID file + stop sentinel process model

**Status:** Accepted

## Context

`--start` runs in the foreground and retries forever. A separate `--stop` invocation (or the stop cron, or `Ctrl-C`) must reliably halt it, including mid-retry-delay, without racing the retry loop.

## Decision

Two coordinating files beside the script:

- **`stream.pid`** — the running PID. `--start` kills any existing live process first (single instance); stale PIDs are pruned.
- **`stream.stop`** — a presence-only sentinel. Created by `--stop` and the signal handler; checked before every retry and during the retry delay. `SIGINT`/`SIGTERM` are treated identically to `--stop`.

## Consequences

- Stop is honored even while waiting between retries — no extra ffmpeg launch.
- One running instance at a time, guaranteed.
- Both files are always cleaned up on exit, clean or signal-driven.
