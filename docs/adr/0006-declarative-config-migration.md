# ADR-0006: Declarative schema migration via deep-merge

**Status:** Accepted · Refs: PR #23

## Context

New releases add config keys. Existing installs have older `config.toml` files missing those keys, which would otherwise crash on access or require bespoke migration code per release.

## Decision

`CONFIG_DEFAULTS` is the single schema. `_migrate_config()` deep-merges defaults into the existing config and writes back any absent keys. It runs on `--start` and `--update`. Adding a key to `CONFIG_DEFAULTS` is sufficient to backfill every install — no per-key migration function.

## Consequences

- Forward-compatible upgrades with zero migration boilerplate.
- `--set-property` validates against `CONFIG_DEFAULTS`, so new keys are writable even on older config files.
- User-set values always win over defaults; only missing keys are filled.
