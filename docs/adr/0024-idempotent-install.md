# ADR-0024: Make `--install` fully idempotent

**Status:** Accepted · Refs: PR #22

## Context

Operators re-run `--install` to apply new settings or repair state. A destructive install that re-prompts for everything and recreates YouTube resources would be dangerous to run twice.

## Decision

`--install` loads existing config and prompts **only** for empty/missing values (`_smart_prompt`). Existing OAuth credentials are reused without a browser flow when valid; existing YouTube resources are reused rather than recreated; cron entries are replaced via the marker, not duplicated ([ADR-0015](0015-cron-self-registration.md)).

## Consequences

- Re-running `--install` is safe and non-destructive.
- It doubles as a repair tool (fix cron, apply new config keys).
- Destructive resets are an explicit, separate path: `--reinstall`.
