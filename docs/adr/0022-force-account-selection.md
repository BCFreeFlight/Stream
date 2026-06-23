# ADR-0022: Force Google account selection on OAuth

**Status:** Accepted · Refs: PR #16

## Context

On machines signed into multiple Google accounts, the OAuth flow would silently reuse whichever account was active, risking authorizing the stream against the wrong channel.

## Decision

The OAuth flow always passes `prompt="select_account"`, forcing the account chooser on every browser flow.

## Consequences

- The operator explicitly picks the target account every time.
- One extra click during the (infrequent) browser flow.
- Re-installs still skip the browser entirely when a valid refresh token exists, so this only applies when a real flow runs.
