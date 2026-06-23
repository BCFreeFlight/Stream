# ADR-0021: Externalize user-facing strings to `resources.toml`

**Status:** Accepted

## Context

`--install` and other commands print many prompts, multi-line setup guides, and status messages. Embedding all this copy in code clutters the logic and makes wording changes risky.

## Decision

All user-facing strings (prompts, defaults, validation messages, guides, summaries, error templates) live in `resources.toml`, loaded into a `res` dict. `stream.py` references keys from `res`; it self-downloads the file when missing ([ADR-0003](0003-self-download-release-assets.md)).

## Consequences

- Copy is separated from logic and versioned per release.
- Wording can change without touching code paths.
- `resources.toml` is a required companion asset, fetched automatically on first run.
