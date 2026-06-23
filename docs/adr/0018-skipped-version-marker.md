# ADR-0018: Skipped-version marker to protect rollbacks

**Status:** Accepted · Refs: issue #41, PR #81

## Context

After rolling back from a broken `vX` to `vX-1`, nothing recorded that `vX` was rejected. The next nightly `--update` saw a newer release than the installed `vX-1` and silently re-installed `vX`, undoing the rollback.

## Decision

`--roll-back` writes the rolled-back-**from** version to `config.update.skippedVersion`. `--update` refuses any release **≤** that version and **clears** the marker once a strictly newer release ships. The marker is inspectable and clearable via `--set-property`.

## Consequences

- A rollback survives subsequent auto-update runs.
- A genuinely newer release (a fix for the bad version) is still adopted automatically, clearing the marker.
- Operators can re-enable updates immediately by clearing `skippedVersion`.
