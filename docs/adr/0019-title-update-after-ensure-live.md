# ADR-0019: Update broadcast title after ensuring live

**Status:** Accepted · Refs: issue #35, PR #36

## Context

The title was updated **before** `ensure_broadcast_live`, while `ctx.broadcast_id` still held yesterday's completed broadcast ID. It stamped that archived broadcast with *today's* date, then `ensure_broadcast_live` created a fresh broadcast and streamed on it. Result: every archived VOD's title was silently overwritten with the next day's date.

## Decision

Move `update_broadcast_title` to run **after** `ensure_broadcast_live`, reading the final (possibly freshly created) broadcast ID from `config["youtube"]["broadcastId"]`.

## Consequences

- Yesterday's archive is never touched.
- The current broadcast gets the correct date, whether newly created or reused.
- Reinforces the ordering: state-changing transitions before metadata updates.
