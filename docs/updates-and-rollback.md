---
title: Updates & Rollback
description: Explains how the script self-updates from GitHub Releases and how to roll back to a previous version using versioned backups.
category: guide
tags:
  - update
  - rollback
  - versioning
  - backup
  - github-releases
---

# Updates & Rollback

The script updates itself in place from GitHub Releases, with versioned backups for safe rollback.

## `--update`

```
1. migrate config
2. fetch latest release tag from GitHub API
3. if latest == current or skipped: stop
4. back up stream.py + resources.toml + config.toml → backup/stream.<version>.bak.zip
5. download stream.py + resources.toml from latest release
6. clear update.skippedVersion (if set)
7. re-register cron entries
```

- **Backup includes `config.toml`** so a rollback restores configuration too, not just code (PR #26).
- **Cron is re-registered** after a successful update because the new `stream.py` may change cron-line format or add the update entry (issue #39 / PR #40).
- A download failure leaves the backup in place and prints its path.

## Skipped-version marker

Without a marker, rolling back from `vX` to `vX-1` would be silently undone by the next nightly `--update` (it sees a newer release and re-installs it).

`--roll-back` records the rolled-back-**from** version as `update.skippedVersion`. `--update` then **refuses** any release ≤ that version, and **clears** the marker once a genuinely newer release ships. See [ADR-0018](adr/0018-skipped-version-marker.md).

Clear it manually to re-enable updates immediately:

```bash
python3 stream.py --set-property update.skippedVersion ""
```

## `--roll-back [VERSION]`

```bash
python3 stream.py --roll-back v0.1.2   # specific version
python3 stream.py --roll-back          # interactive picker
```

Interactive picker lists newest-first:

```
Available backups:
  1. v0.1.3  (12 KB)
  2. v0.1.2  (11 KB)
Enter number to restore (or 'q' to cancel):
```

Restoring extracts `stream.py`, `resources.toml`, and `config.toml` from the chosen zip and sets `skippedVersion` to the version you rolled back from.

## Versioning

- `__version__` is `"dev"` in source; the release workflow injects the real tag via `sed`.
- Versions are `vMAJOR.MINOR.PATCH`; `--update` and the skipped-version check compare them as integer tuples.
- Dev builds resolve asset URLs to `releases/latest`; tagged builds to their specific tag.

## Backups

- Location: `backup/` beside the script (never committed).
- Naming: `stream.<version>.bak.zip` (e.g. `stream.v0.1.3.bak.zip`).
- Created only by `--update`. Preserved across `--uninstall` and `--reinstall`.
