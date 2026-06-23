# ADR-0020: Two-tier YouTube API layering

**Status:** Accepted

## Context

YouTube broadcast orchestration mixes raw API calls with logging, polling, retries, and error handling. Combining them produces long, hard-to-test functions.

## Decision

Split the YouTube integration into two tiers:

- **Low level (`_api_*`)** — exactly one API call per function, returns the raw response, no logging or orchestration.
- **High level** — composes low-level calls with logging, polling loops, and `HttpError` handling; each represents one meaningful lifecycle step.

## Consequences

- Low-level wrappers are trivially mockable in tests (one call each).
- Orchestration reads as a sequence of named steps.
- Adheres to the project's single-responsibility rule.
