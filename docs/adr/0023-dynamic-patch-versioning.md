# ADR-0023: Dynamic patch versioning in the release workflow

**Status:** Accepted · Refs: PR #5, PR #10

## Context

Releases are cut manually. Hardcoding version numbers in source or workflow files is error-prone and drifts from the actual release history.

## Decision

The release workflow (`workflow_dispatch` only) reads the latest release tag from the GitHub API, increments the **patch** component, and injects it into `__version__` via `sed` at build time. It starts at `v0.1.0` when no releases exist. Source always carries `__version__ = "dev"`. Releases are gated on the test workflow passing.

## Consequences

- Versions are always consistent with release history; nothing to bump by hand.
- Minor/major bumps require a manual tag adjustment (patch-only automation by design).
- Dev checkouts report `dev` and resolve assets from `releases/latest`.
- GitHub Actions are kept on Node.js 24-compatible versions (issue #9 / PR #10).
