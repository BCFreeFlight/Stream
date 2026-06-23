# ADR-0010: Set embeddable on both broadcast and video

**Status:** Accepted · Refs: issue #20, PRs #17, #29–#33

## Context

Embeds worked on desktop but were blocked on mobile with "Playback on other websites has been disabled." YouTube exposes **two** separate embeddable flags: one on the `liveBroadcast` resource and one on the underlying `video` resource. Mobile clients enforce the video-level flag strictly; desktop is lenient. The video resource is also created asynchronously after the broadcast, causing race conditions.

## Decision

Set embeddable on **both** resources. The broadcast flag is applied via `liveBroadcasts` `contentDetails.enableEmbed` (alongside `enableDvr` and `monitorStream`). The video flag is applied via `videos.update`, polling until the video resource exists. When `embeddable=true`, the broadcast insert default is relied on and a redundant update is skipped (PR #33).

## Consequences

- Embeds work on mobile and desktop.
- Setting the video flag requires polling for the async-created video resource.
- `contentDetails` updates must include `monitorStream` to avoid clobbering it (PR #32).
