# ADR-0008: Complete the broadcast on `--stop` to archive a VOD

**Status:** Accepted · Refs: issue #7, PR #8

## Context

`--stop` originally only killed ffmpeg. The broadcast stayed in limbo and the content was never archived, so viewers could not watch past streams.

## Decision

After stopping ffmpeg, `--stop` transitions the broadcast to `complete`, which makes YouTube archive it as a VOD. It then applies `archivePrivacy` to the archived video. Because completing makes a broadcast non-reusable, `--start` handles the `complete` state by creating a fresh broadcast ([ADR-0007](0007-fresh-broadcast-per-start.md)).

## Consequences

- Each day's stream becomes a watchable VOD on the channel.
- `archivePrivacy` lets the live stream be public while archives default to private.
- The stop/start pair is self-healing: stop archives, the next start makes a new broadcast.
