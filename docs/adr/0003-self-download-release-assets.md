# ADR-0003: Self-download companion release assets

**Status:** Accepted · Refs: issue #3, PR #4

## Context

`stream.py` depends on `resources.toml` (user-facing strings). Forcing users to `curl` multiple files is error-prone and couples the install one-liner to the asset list.

## Decision

Any companion asset flows through `_ensure_release_asset(filename)`: if the file exists beside the script, return it; otherwise download it from the matching GitHub release and return it. Dev builds fetch from `releases/latest`; tagged builds from their specific tag.

## Consequences

- The install one-liner downloads only `stream.py`; everything else is fetched on first use.
- Adding a future companion asset just means routing its access through the same helper.
- Requires network access on first run (already required for OAuth and ffmpeg install).
