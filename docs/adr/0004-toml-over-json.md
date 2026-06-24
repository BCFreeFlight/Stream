---
title: "ADR-0004: TOML for config and resources, not JSON"
description: Records the decision to use TOML instead of JSON for configuration and resource files, with inline comments via tomli/tomli-w.
category: adr
tags:
  - toml
  - configuration
  - accepted
  - dependencies
  - migration
---

# ADR-0004: TOML for config and resources, not JSON

**Status:** Accepted · Refs: PR #6

## Context

Config and resources were originally JSON. JSON has no comments and is unfriendly for humans hand-editing configuration.

## Decision

Use TOML for `config.toml` and `resources.toml`. Read with the stdlib `tomllib` (3.11+) or `tomli` (older); write with `tomli-w`. `save_config` injects inline comments from `CONFIG_COMMENTS` on write.

## Consequences

- Config is self-documenting with inline comments and clear sections.
- `_try_load_existing_config` still reads legacy `config.json` once, to migrate older installs.
- Requires the `tomli`/`tomli-w` dependencies (handled by [ADR-0002](0002-self-installing-dependencies.md)).
