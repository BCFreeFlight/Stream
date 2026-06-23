# ADR-0015: Marker-based cron self-registration

**Status:** Accepted

## Context

The script must run unattended on a daily schedule with no manual crontab editing, and re-running `--install` must not accumulate duplicate entries or disturb the user's other cron jobs.

## Decision

`--install` writes its own crontab entries, each tagged with the trailing comment `# bcfreeflight_stream`. Registration removes all marked lines, then re-adds the current set (start, stop, `@reboot` recover, and optionally update). `--uninstall` removes exactly the marked lines.

## Consequences

- Idempotent: re-running `--install` updates entries without duplication.
- The script only ever touches its own lines; unrelated cron jobs are untouched.
- The start entry opens a single titled terminal window that closes when stop fires, preventing window accumulation.
