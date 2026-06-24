---
title: "ADR-0012: Resolve stream ID from the key at runtime"
description: Documents the decision to persist only the stream key in config and resolve the stream ID at runtime by matching against the YouTube live streams list.
category: adr
tags:
  - streams
  - youtube
  - runtime
  - accepted
  - configuration
---

# ADR-0012: Resolve stream ID from the key at runtime

**Status:** Accepted · Refs: PR #18, PR #28

## Context

Operations need the stream **ID** (to bind and to poll status), but persisting the ID risks it drifting out of sync with the actual stream resource if YouTube state changes or the user reuses a different key.

## Decision

Persist only the stream **key** in config. Resolve the stream **ID** at runtime by listing the user's live streams and matching `cdn.ingestionInfo.streamName` to the configured key (`find_stream_by_key`). During `--install`, the user may paste an existing key to reuse its resource instead of creating a new one.

## Consequences

- Self-healing: a stale or mismatched stream ID can never break `--start`.
- One extra `liveStreams.list` call per start.
- Reusing an existing YouTube stream resource is supported out of the box.
