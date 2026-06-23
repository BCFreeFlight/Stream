# ADR-0011: Inject a silent AAC track when muted

**Status:** Accepted · Refs: PR #14

## Context

A naive mute (`-an`, drop audio) produces a video-only stream. YouTube's live ingest rejects video-only streams — `streamStatus` stays `inactive` forever and the broadcast never goes live.

## Decision

When `mute = true`, inject a silent AAC track instead of dropping audio:

```
-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 \
-map 0:v:0 -map 1:a:0 -c:a aac -b:a 128k -shortest
```

`-shortest` makes ffmpeg exit when the RTSP input ends rather than running forever against the infinite silent source.

## Consequences

- Muted streams remain valid for YouTube ingest and go live normally.
- Viewers get a functionally silent experience.
- Muted streams always re-encode audio to AAC (there is no real audio to `copy`).
