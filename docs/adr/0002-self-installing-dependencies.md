# ADR-0002: Self-install Python dependencies at runtime

**Status:** Accepted · Refs: PR #12

## Context

The single-file distribution ([ADR-0001](0001-single-file-script.md)) has no `requirements.txt` and no install step to run `pip`. It still needs `google-auth`, `google-api-python-client`, `croniter`, and others.

## Decision

Before any third-party import, try to import each dependency; pip-install whatever is missing, then re-import in the same process. Modern Debian/Ubuntu mark the system Python as externally-managed (PEP 668), so a plain `pip install` falls back to `--user --break-system-packages` and adds the user site to `sys.path`.

## Consequences

- First run on a fresh machine just works; no manual `pip` step.
- Works in venvs, pre-PEP-668 interpreters, and externally-managed system Pythons.
- Versions are unpinned unless a specific bug requires pinning.
- `ffmpeg` is excluded — it is a system package installed via `apt` only during `--install`, never during `--start`/`--stop`.
