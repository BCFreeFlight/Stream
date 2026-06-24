---
title: "ADR-0013: Alternate primary/backup RTMP across retries"
description: Documents the decision to alternate between primary and backup RTMP ingest endpoints on each retry attempt for unattended stream recovery.
category: adr
tags:
  - retry
  - ffmpeg
  - streams
  - resilience
  - accepted
---

# ADR-0013: Alternate primary/backup RTMP across retries

**Status:** Accepted · Refs: PR #13

## Context

ffmpeg can exit for transient reasons (network blips, ingest hiccups). A single ingest endpoint may be temporarily degraded. The stream must recover unattended.

## Decision

The retry loop runs indefinitely (no max count) until `--stop` or a signal. Each attempt is numbered: even attempts use `streamURL`, odd attempts use `backupStreamUrl` when configured (`select_rtmp_url`). On retry, the script reconnects to the **same** broadcast and re-authenticates if needed.

## Consequences

- Survives transient failures of either ingest endpoint.
- No human intervention required for recovery.
- The stop sentinel is checked before every retry and during the delay, so stop is always honored ([ADR-0014](0014-pid-and-stop-sentinel.md)).
