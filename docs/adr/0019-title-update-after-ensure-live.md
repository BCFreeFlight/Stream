---
title: "ADR-0019: Update broadcast title after ensuring live"
description: Documents the decision to move broadcast title updates after the ensure-live step so the correct broadcast ID is used and archived VODs are not overwritten.
category: adr
tags:
  - broadcast
  - youtube
  - title-update
  - accepted
  - lifecycle
---

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

## Amendment: first live pass, not first attempt

The update was originally gated on the retry loop's first attempt. After a reboot on 2026-09-23 the first attempt failed before ffmpeg launched (no DNS yet), so the pass that actually went live was a retry and the title was never stamped. `_stream_until_exit` now takes an `on_live` callback, invoked only after `ensure_broadcast_live` succeeds; the retry loop passes a one-shot updater (`_make_title_updater`) so the title is stamped exactly once per `--start` session, on the first pass where the broadcast is actually live.
