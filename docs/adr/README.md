---
title: Architecture Decision Records
description: Index of all architecture decision records explaining the key design choices behind the BC Free Flight Stream project.
category: overview
tags:
  - adr
  - architecture
  - decisions
  - index
---

# Architecture Decision Records

Each ADR captures one significant decision: its context, the choice made, and the consequences. They explain **why** the code is shaped the way it is. Many trace back to specific issues/PRs in [BCFreeFlight/Stream](https://github.com/BCFreeFlight/Stream).

## Format

`Status · Context · Decision · Consequences`. Short by design.

## Index

| ADR | Decision |
|-----|----------|
| [0001](0001-single-file-script.md) | Keep `stream.py` a single file |
| [0002](0002-self-installing-dependencies.md) | Self-install Python dependencies at runtime |
| [0003](0003-self-download-release-assets.md) | Self-download companion release assets |
| [0004](0004-toml-over-json.md) | TOML for config and resources, not JSON |
| [0005](0005-config-secrets-split.md) | Split secrets (`.env`) from config (`config.toml`) |
| [0006](0006-declarative-config-migration.md) | Declarative schema migration via deep-merge |
| [0007](0007-fresh-broadcast-per-start.md) | Create a fresh broadcast on every `--start` |
| [0008](0008-complete-broadcast-on-stop.md) | Complete the broadcast on `--stop` to archive a VOD |
| [0009](0009-stable-channel-embed-url.md) | Use the channel-based stable embed URL |
| [0010](0010-embeddable-dual-flag.md) | Set embeddable on both broadcast and video |
| [0011](0011-silent-audio-when-muted.md) | Inject a silent AAC track when muted |
| [0012](0012-resolve-stream-id-from-key.md) | Resolve stream ID from the key at runtime |
| [0013](0013-retry-primary-backup-alternation.md) | Alternate primary/backup RTMP across retries |
| [0014](0014-pid-and-stop-sentinel.md) | PID file + stop sentinel process model |
| [0015](0015-cron-self-registration.md) | Marker-based cron self-registration |
| [0016](0016-reboot-crash-recovery.md) | `@reboot` `--recover` crash recovery |
| [0017](0017-optional-auto-update.md) | Auto-update cron is opt-in |
| [0018](0018-skipped-version-marker.md) | Skipped-version marker to protect rollbacks |
| [0019](0019-title-update-after-ensure-live.md) | Update broadcast title after ensuring live |
| [0020](0020-layered-youtube-api.md) | Two-tier YouTube API layering |
| [0021](0021-externalized-strings.md) | Externalize user-facing strings to `resources.toml` |
| [0022](0022-force-account-selection.md) | Force Google account selection on OAuth |
| [0023](0023-dynamic-patch-versioning.md) | Dynamic patch versioning in the release workflow |
| [0024](0024-idempotent-install.md) | Make `--install` fully idempotent |
