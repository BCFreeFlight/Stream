# Development

## Hard rules

These are non-negotiable project constraints (see [CLAUDE.md](../CLAUDE.md)):

- **One file.** All logic stays in `src/stream.py`. Never split into modules. See [ADR-0001](adr/0001-single-file-script.md).
- **No packaging.** No `requirements.txt` or `setup.py`. Dependencies declared inline.
- **No hardcoded runtime values.** Everything comes from `config.toml` or `.env`.
- **No dead config.** Every config key must be read and used.
- **Secret/non-secret split.** Secrets in `.env`, config in `config.toml`.
- **No new CLI switches or config keys** without updating `CLAUDE.md`, `README.md`, `REQUIREMENTS.md`, and example files.

## Code quality

SOLID, single-responsibility functions:

- Each function does one thing with a descriptive name.
- Dependencies passed as parameters, not created internally.
- Compose small focused functions over monoliths.
- No half-finished abstractions.

The YouTube API is deliberately two-tiered: side-effect-free single-call wrappers (`_api_*`) at the bottom, orchestration with logging/polling on top. See [ADR-0020](adr/0020-layered-youtube-api.md).

## Testing

```bash
python3 -m pytest tests/
```

- Tests live in `tests/`, organized by functional area (`test_ffmpeg.py`, `test_configuration.py`, …).
- Fixtures in `tests/conftest.py`.
- **Mock all external dependencies** — network, filesystem, subprocesses. Never make real API calls.
- Cover happy path **and** edge cases (missing files, network errors, invalid input).
- New functions need coverage; behavior changes need test updates.

CI (`.github/workflows/test.yml`) runs pytest with coverage on every push/PR to `main`, posts a results comment on PRs, and uploads to Codecov.

## Dependency bootstrap

At import time, `stream.py` tries each third-party import and pip-installs any missing package, then re-imports. It tolerates PEP 668 externally-managed environments by falling back to `--user --break-system-packages`. See [ADR-0002](adr/0002-self-installing-dependencies.md).

`ffmpeg` is a system dependency installed via `apt` only during `--install`.

## Releases

`.github/workflows/release.yml`, manual `workflow_dispatch` only:

1. Run the test workflow (gate).
2. Read the latest release tag; increment **patch** (`v1.0.4` → `v1.0.5`); start at `v0.1.0` if none.
3. `sed` the computed tag into `__version__`.
4. Attach `src/stream.py` and `src/resources.toml` (no path prefix).
5. Changelog = commits since the previous tag.

Versions are always computed dynamically — never hardcoded. See [ADR-0023](adr/0023-dynamic-patch-versioning.md).

## Adding a config key

1. Add it to `CONFIG_DEFAULTS` (backfills all installs via `_migrate_config` — [ADR-0006](adr/0006-declarative-config-migration.md)).
2. Add a comment to `CONFIG_COMMENTS`.
3. Read and use it in the script.
4. Update `CLAUDE.md`, `README.md`, `REQUIREMENTS.md`, `config.example.toml`.
5. Add tests.

## User-facing strings

All prompts/guides/messages live in `resources.toml`, not in code. Add new copy there and reference it via the loaded `res` dict. See [ADR-0021](adr/0021-externalized-strings.md).
