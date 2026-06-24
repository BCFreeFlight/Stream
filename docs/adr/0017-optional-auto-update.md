---
title: "ADR-0017: Auto-update cron is opt-in"
description: Documents the decision to make the automatic update cron entry opt-in via the cron.autoUpdate config flag, defaulting to false to prevent unattended updates without operator consent.
category: adr
tags:
  - cron
  - auto-update
  - configuration
  - accepted
---

# ADR-0017: Auto-update cron is opt-in

**Status:** Accepted · Refs: PR #21

## Context

Unattended hosts benefit from automatic updates, but silently pulling new code onto a running production stream risks introducing a breaking change without the operator's consent.

## Decision

`cron.autoUpdate` defaults to `false`. The update cron entry (`cron.update`, default midnight daily) is registered **only** when `autoUpdate` is enabled — during `--install` or by setting it later and re-running `--install`. Existing installs receive both keys with safe defaults via [config migration](0006-declarative-config-migration.md).

## Consequences

- No host updates itself without explicit opt-in.
- Operators who want hands-off operation can enable it with one setting.
- The update path itself is protected against undoing rollbacks ([ADR-0018](0018-skipped-version-marker.md)).
