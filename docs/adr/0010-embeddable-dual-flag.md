# ADR-0010: Set embeddable on both broadcast and video

**Status:** Accepted · Refs: issue #20, PRs #17, #29–#33 · Fixed: issue #110, PR #112

## Context

Embeds worked on desktop but were blocked on mobile with "Playback on other websites has been disabled." YouTube exposes **two** separate embeddable flags: one on the `liveBroadcast` resource and one on the underlying `video` resource. Mobile clients enforce the video-level flag strictly; desktop is lenient. The video resource is also created asynchronously after the broadcast, causing race conditions.

## Decision

Set embeddable on **both** resources:

1. The broadcast flag is applied via `liveBroadcasts.update` (`contentDetails.enableEmbed`) alongside `enableDvr` and `monitorStream`. This call is made **unconditionally** after every broadcast creation — the old guard (`if not embeddable`) was removed in PR #112 because it prevented the update from ever running when `embeddable=true`, which is the default for every install.

2. The video flag is applied via `videos.update`, polling until the video resource exists. When `embeddable=true` during install, a separate update call is made after the broadcast's video resource appears (PR #33).

Both `enableEmbed` and `enableDvr` are set explicitly on every broadcast creation to avoid relying on YouTube API defaults, which may differ from the configured values — particularly for broadcasts created before v0.1.21, which retain YouTube's default DVR-enabled state unless explicitly corrected via the update call.

## Consequences

- Embeds work on mobile and desktop regardless of config values.
- DVR is reliably disabled (`enableDvr=false`) on every newly created broadcast, including those that existed before v0.1.21.
- Setting the video flag requires polling for the async-created video resource.
- `contentDetails` updates must include `monitorStream` to avoid clobbering it (PR #32).
- The unconditional update call adds one extra API request per broadcast creation, which is negligible compared to the reliability gain.
