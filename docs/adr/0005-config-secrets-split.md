# ADR-0005: Split secrets (`.env`) from config (`config.toml`)

**Status:** Accepted

## Context

The script handles both non-secret settings (RTSP URL, schedule, codecs) and secrets (OAuth client secret, refresh/access tokens). Mixing them risks committing or sharing secrets.

## Decision

- `config.toml` holds **only** non-secret values.
- `.env` holds **only** secrets and auto-refreshed tokens.
- When adding a value, classify it first: secret → `.env`, otherwise → `config.toml`. The OAuth **client ID** is non-secret and lives in `config.toml`; the **client secret** lives in `.env`.

## Consequences

- `config.toml` can be shared or inspected without leaking credentials.
- A single clear rule for where any new value belongs.
- Both files are runtime-generated and never committed; secrets are also never logged.
