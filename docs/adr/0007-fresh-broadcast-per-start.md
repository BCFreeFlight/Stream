---
title: "ADR-0007: Create a fresh broadcast on every --start"
description: Documents the decision to retire and recreate YouTube broadcasts on every --start while reusing the permanent stream resource.
category: adr
tags:
  - broadcast
  - youtube
  - accepted
  - streams
  - lifecycle
---

# ADR-0007: Create a fresh broadcast on every `--start`

**Status:** Accepted · Refs: PR #15, PR #8

## Context

A completed broadcast cannot be reused. Reusing a single long-lived broadcast led to limbo states and stale archives. The daily cron must produce one clean archive per day.

## Decision

Every `--start` retires any active broadcast and ensures a fresh one is live. The **stream resource** (RTMP URL + key) is created once at `--install` and reused permanently; only the broadcast rotates. When the configured broadcast is `complete`, `--start` creates a new broadcast, binds the existing stream, and updates `broadcastId` in config.

## Consequences

- One clean VOD per day; no limbo broadcasts.
- The RTMP URL/key never change, so ffmpeg config is stable.
- Broadcast IDs rotate — but viewers are unaffected because the embed URL is channel-based ([ADR-0009](0009-stable-channel-embed-url.md)).
- Orphaned broadcasts from crashes are cleaned up at the start of each run.
