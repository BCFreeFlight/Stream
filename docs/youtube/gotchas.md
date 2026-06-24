---
title: "YouTube Live Streaming API — Gotchas and Known Issues"
description: Catalogs non-obvious constraints, undocumented behaviors, and known bugs in the YouTube Data API v3 for live streaming, along with their workarounds.
category: youtube-api
tags:
  - youtube
  - broadcast
  - api
  - live-streaming
  - embeddable
---

# YouTube Live Streaming API — Gotchas and Known Issues

This document catalogs every non-obvious constraint, undocumented behavior, and
known bug encountered when using the YouTube Data API v3 for live streaming.
Each entry includes the symptom, root cause, and the workaround used in this
project.

---

## `mine=True` + `broadcastStatus` conflict

**Symptom:** `liveBroadcasts.list` returns `400 Bad Request` with
`incompatibleParameters` when both `mine=True` and a `broadcastStatus` filter
are included.

**Root cause:** The API documentation implies both can be used together, but
the server rejects the combination. This appears to be a long-standing,
undocumented API restriction.

**Workaround:** List all broadcasts with `mine=True` only, then filter by
`lifeCycleStatus` client-side:

```python
items = youtube.liveBroadcasts().list(
    part="id,status",
    mine=True,
    maxResults=50
).execute().get("items", [])

active = [
    i for i in items
    if i["status"]["lifeCycleStatus"] in ("live", "ready", "testing", "created")
]
```

See [`_api_list_my_broadcasts`](../../src/stream.py) and
[broadcasts.md → Orphan cleanup](broadcasts.md#orphan-cleanup-pattern).

---

## State transition errors: `created`/`ready` → `complete`

**Symptom:** `liveBroadcasts.transition(broadcastStatus="complete")` returns
`400 invalidTransition` for broadcasts in `created` or `ready` state.

**Root cause:** YouTube's state machine only permits transitioning to
`complete` from `live` or `testing`. Broadcasts that never started cannot be
completed.

**Workaround:** Delete broadcasts in `created` or `ready` state instead of
transitioning them:

```python
if lifecycle in ("live", "testing"):
    youtube.liveBroadcasts().transition(
        broadcastStatus="complete", id=bid, part="id,status"
    ).execute()
elif lifecycle in ("created", "ready"):
    youtube.liveBroadcasts().delete(id=bid).execute()
```

---

## Asynchronous video resource creation

**Symptom:** `videos.list` returns empty `items` immediately after
`liveBroadcasts.insert`, even though the broadcast was successfully created.

**Root cause:** YouTube creates the underlying video resource asynchronously.
The broadcast object exists immediately, but the video resource it corresponds
to is not queryable for 2–15 seconds.

**Workaround:** Poll until the video resource appears:

```python
for _ in range(10):
    resp = youtube.videos().list(part="status", id=broadcast_id).execute()
    if resp.get("items"):
        break
    time.sleep(2)
```

If the video never appears within the retry window, log a warning and skip
the update. Do not fail the entire startup over this.

---

## Dual embeddable flags

**Symptom:** Embeds work on desktop but show "Playback on other websites has
been disabled" on mobile.

**Root cause:** YouTube exposes two separate embeddable flags:
1. `liveBroadcasts.contentDetails.enableEmbed`
2. `videos.status.embeddable`

Mobile browsers enforce the video-level flag strictly. Desktop clients are
lenient and only check the broadcast-level flag.

**Workaround:** Set both. Because the video resource is created asynchronously,
the video-level flag must be set in a separate step with polling.

See [ADR-0010](../adr/0010-embeddable-dual-flag.md) and
[videos.md → Embeddable flag](videos.md#embeddable-flag).

---

## `contentDetails` update clobbers `monitorStream`

**Symptom:** After updating `contentDetails` to change `enableEmbed` or
`enableDvr`, the monitor stream gets unexpectedly re-enabled.

**Root cause:** `liveBroadcasts.update` with `part="contentDetails"` replaces
the entire `contentDetails` object. Any field you omit reverts to its default.
The default for `enableMonitorStream` is `true`.

**Workaround:** Always include `monitorStream` when sending a `contentDetails`
update:

```python
{
    "enableEmbed": embeddable,
    "enableDvr": enable_dvr,
    "monitorStream": {"enableMonitorStream": enable_monitor},
}
```

See [ADR-0010](../adr/0010-embeddable-dual-flag.md).

---

## Video-only ingest stays `inactive`

**Symptom:** ffmpeg is running and sending data, but `liveStreams.list →
status.streamStatus` remains `inactive` indefinitely. The broadcast never
goes live.

**Root cause:** YouTube's RTMP ingest silently rejects streams that contain
only a video track and no audio track. The stream status never advances to
`active`.

**Workaround:** Always send an audio track. If the source camera audio is
unwanted, inject a silent AAC track rather than using `-an`:

```
ffmpeg -re -rtsp_transport tcp -i <rtspUrl> \
       -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 \
       -map 0:v:0 -map 1:a:0 \
       -vcodec copy -c:a aac -b:a 128k -shortest \
       -f flv <rtmpUrl>/<streamKey>
```

See [ADR-0011](../adr/0011-silent-audio-when-muted.md) and
[streaming.md → Mute behavior](../streaming.md#mute-behavior).

---

## `ready` → `testing` fails when stream is inactive

**Symptom:** `liveBroadcasts.transition(broadcastStatus="testing")` returns
`400 invalidTransition` even though the broadcast is in `ready` state.

**Root cause:** The API requires the stream to be actively ingesting data
(`streamStatus == "active"`) before a `→ testing` transition can succeed.
The broadcast state and the stream state are independent, and both must be
satisfied.

**Workaround:** Poll `liveStreams.list` until `streamStatus == "active"` before
attempting any transition:

```python
for _ in range(120):
    resp = youtube.liveStreams().list(part="status", id=stream_id).execute()
    status = resp["items"][0]["status"]["streamStatus"]
    if status == "active":
        break
    time.sleep(5)
```

---

## Snippet update must be read–modify–write

**Symptom:** `liveBroadcasts.update` with `part="snippet"` returns `400` or
silently clears fields like `scheduledStartTime`, `description`, or
`channelId`.

**Root cause:** The API replaces the entire `snippet` object with what you
send. Server-managed fields that you omit are cleared.

**Workaround:** Always read the current snippet first, then modify only the
target field:

```python
resp = youtube.liveBroadcasts().list(part="snippet", id=broadcast_id).execute()
snippet = resp["items"][0]["snippet"]
snippet["title"] = new_title
youtube.liveBroadcasts().update(
    part="snippet",
    body={"id": broadcast_id, "snippet": snippet}
).execute()
```

---

## `scheduledStartTime` is required at insert

**Symptom:** `liveBroadcasts.insert` returns `400 invalidStartTime` when
`snippet.scheduledStartTime` is omitted.

**Root cause:** The API requires a scheduled start time even for broadcasts
that should start immediately.

**Workaround:** Set `scheduledStartTime` to the current UTC time:

```python
"scheduledStartTime": datetime.datetime.now(datetime.timezone.utc).isoformat()
```

---

## `selfDeclaredMadeForKids` must be explicitly set

**Symptom:** Broadcasts sometimes end up marked as "Made for Kids" or
`liveBroadcasts.insert` returns an error about COPPA compliance.

**Root cause:** If `selfDeclaredMadeForKids` is omitted from the `status`
object, YouTube may inherit the channel-level "Made for Kids" setting, which
could be `true`.

**Workaround:** Always explicitly set this field:

```python
"status": {
    "privacyStatus": "public",
    "selfDeclaredMadeForKids": False,
}
```

---

## Title update must happen after `ensure_broadcast_live`

**Symptom:** The previous day's archived VOD has its title stamped with the
next day's date, or the current broadcast has yesterday's date.

**Root cause:** When the configured broadcast is in `complete` state, `--start`
creates a **new** broadcast to replace it. If the title is updated before
`ensure_broadcast_live`, it gets applied to the old `complete` broadcast — the
new broadcast ends up with a stale title.

**Workaround:** Always update the title **after** ensuring the broadcast is
live, so the stamp lands on the active broadcast:

```python
ensure_broadcast_live(youtube, broadcast_id, config, logger)
# broadcast_id in config may have changed to a new ID at this point
update_broadcast_title(youtube, config["youtube"]["broadcastId"], config, logger)
```

See [ADR-0019](../adr/0019-title-update-after-ensure-live.md).

---

## `enableAutoStop: false` is critical

**Symptom:** The broadcast randomly completes mid-stream during a brief
network hiccup, even though ffmpeg reconnects within seconds. Once complete,
the broadcast cannot be resumed.

**Root cause:** The `contentDetails.enableAutoStop` flag defaults to `true` in
some API versions or when the field is omitted. With `enableAutoStop: true`,
YouTube automatically transitions the broadcast to `complete` when the ingest
stream goes inactive for more than a few seconds.

**Workaround:** Always explicitly set `enableAutoStop: false` in the insert body:

```python
"contentDetails": {
    "enableAutoStop": False,
    "enableAutoStart": False,
    ...
}
```

---

## `complete` broadcasts cannot be reused

**Symptom:** `liveBroadcasts.transition(broadcastStatus="live")` returns
`400 invalidTransition` on a broadcast that was previously live.

**Root cause:** Once a broadcast reaches `complete`, it is archived as a VOD
and its lifecycle is sealed. There is no way to reactivate it.

**Workaround:** Create a new broadcast, bind the existing stream to it, and
update `broadcastId` in config. The stream resource (RTMP URL + key) does not
change — only the broadcast rotates.

See [ADR-0007](../adr/0007-fresh-broadcast-per-start.md).

---

## Transient `liveStarting`/`testStarting` states

**Symptom:** After calling `liveBroadcasts.transition`, the broadcast gets
stuck in `liveStarting` or `testStarting` indefinitely, then eventually
reverts or errors.

**Root cause:** YouTube uses these transient states while it propagates the
transition to its CDN. They are normal and expected; the transition is not
immediate.

**Workaround:** Poll `liveBroadcasts.list` until `lifeCycleStatus` reaches
the target state before proceeding. Do not interpret `liveStarting` as a
success — wait for `live`:

```python
for _ in range(60):
    status = youtube.liveBroadcasts().list(
        part="status", id=broadcast_id
    ).execute()["items"][0]["status"]["lifeCycleStatus"]
    if status == "live":
        break
    time.sleep(3)
```

---

## `part` parameter controls what is read AND written

**Symptom:** Update calls silently lose data or return `400` about missing
required fields.

**Root cause:** The `part` parameter in both `list` and `update` calls
controls which sections of the resource are included. In `update`, only the
sections named in `part` are written — but they are **fully replaced**, not
merged. Sections omitted from `part` are not touched.

**Implication:** If you send `part="contentDetails"`, only `contentDetails`
is updated; `snippet` and `status` are untouched. But within `contentDetails`,
every field is replaced by what you send.

**Workaround:** Be explicit about `part`. Always read a section before writing
it to avoid clobbering fields you don't intend to change.

---

## OAuth consent screen "Testing" status limits token lifetime

**Symptom:** The refresh token stops working after 7 days and the browser
OAuth flow must be re-run.

**Root cause:** Google OAuth apps in "Testing" status issue refresh tokens
that expire after 7 days regardless of usage. This is a Google security
measure for unverified apps.

**Workaround:** Publish the consent screen (or use an Internal app type in a
Google Workspace org). The live streaming scopes (`youtube.*`) require
verification for external apps, but a personal project used by a single account
can operate indefinitely without publication by adding that account as a
"Test user".

> If you add yourself as a Test user, the 7-day limit does not apply. The
> 7-day limit only applies when **no** test users are defined and the app is
> in Testing status.

---

## Stream resource key matches the key returned by the API

**Symptom:** `find_stream_resource_by_key` returns `None` even though the
stream key is correct.

**Root cause:** The key shown in YouTube Studio and the key returned by
`liveStreams.list → cdn.ingestionInfo.streamName` are sometimes formatted
differently — Studio may show a hyphenated format while the API returns
the raw key.

**Workaround:** Confirm the key by listing streams via the API once after
creation, rather than copy-pasting from the Studio UI. The project uses
the API-returned key exclusively.

---

## `broadcastType` defaults to `event` — persistent broadcasts invisible

**Symptom:** `liveBroadcasts.list?mine=true` returns no results even though
broadcasts are visible in YouTube Studio.

**Root cause:** The `broadcastType` parameter defaults to `event`. Persistent
broadcasts (created with `enableAutoStop: false`) are classified differently
and are excluded from the default query.

**Workaround:** Pass `broadcastType=all` or `broadcastType=persistent` when
you need to include persistent broadcasts:

```python
youtube.liveBroadcasts().list(
    part="id,status",
    mine=True,
    broadcastType="all",
    maxResults=50
).execute()
```

---

## Non-reusable streams excluded from `mine=True` queries

**Symptom:** `liveStreams.list?mine=true` does not return a known stream.

**Root cause:** Streams created with `contentDetails.isReusable: false` are
explicitly excluded from `mine=True` list results. The only way to retrieve
them is by explicit `id`:

```python
youtube.liveStreams().list(part="cdn,status", id=stream_id).execute()
```

**Workaround:** Always create stream resources with `isReusable: true` (the
default). This project uses the default and queries by key match, which
only works on reusable streams.

---

## Stuck in `testStarting` or `liveStarting`

**Symptom:** After calling `liveBroadcasts.transition`, the broadcast stays
in `testStarting` or `liveStarting` indefinitely. Further transition calls
fail with `invalidTransition`.

**Root cause:** These are transient states YouTube uses while propagating the
transition to its CDN. Normally they resolve within seconds, but under error
conditions they can become permanent. Once in these states, no transition
target is valid — the API cannot move the broadcast forward or backward.

**Workaround:** The only recovery is to delete the stuck broadcast and create
a new one. This is a documented API limitation with no server-side recovery path:

```python
youtube.liveBroadcasts().delete(id=stuck_broadcast_id).execute()
new_id = create_broadcast(youtube, config, logger)
bind_stream_to_broadcast(youtube, new_id, stream_id, logger)
```

---

## `enableDvr: false` causes 24-hour archive delay

**Symptom:** After a broadcast ends, the archived VOD is not accessible for
~24 hours, even though the broadcast completed successfully.

**Root cause:** The YouTube docs state that `enableDvr: true` combined with
`recordFromStart: true` (both default to `true`) is required for the archived
video to be available immediately after the broadcast ends. Setting
`enableDvr: false` causes YouTube to use a different processing pipeline that
introduces approximately 24 hours of delay.

**Workaround:** Leave `enableDvr` at its default (`true`) unless you have a
specific reason to disable it and can tolerate the delay.

This project exposes `enableDvr` as a user-configurable option in `config.toml`
with `youtube.enableDvr`. The default is `false` because the original use case
does not require immediate replay. Change it to `true` if same-day VOD
availability is needed.

---

## `bind` fails when broadcast is live or complete

**Symptom:** `liveBroadcasts.bind` returns `403 liveBroadcastBindingNotAllowed`.

**Root cause:** A broadcast can only have a stream bound (or re-bound) to it
while in `created` or `ready` state. Binding is blocked once the broadcast
enters `testing`, `live`, or `complete`.

**Workaround:** Always bind the stream to a new broadcast before starting
any transition. This project binds during `--install` (initial setup) and
again when creating a fresh broadcast to replace a `complete` one.

---

## `scheduledStartTime` set to epoch zero becomes permanent

**Symptom:** A broadcast shows "Scheduled for January 1, 1970" in YouTube
Studio and the time cannot be changed via the API or Studio UI.

**Root cause:** Setting `scheduledStartTime` to Unix epoch zero (`1970-01-01T00:00:00Z`)
creates an "unscheduled" broadcast state that YouTube treats as a special case.
Once set this way, it cannot be modified.

**Workaround:** Always set `scheduledStartTime` to the current UTC time at
insert:

```python
"scheduledStartTime": datetime.datetime.now(datetime.timezone.utc).isoformat()
```

---

## `liveBroadcasts.update` requires `monitorStream` sub-object fields

**Symptom:** `liveBroadcasts.update` returns `400 required` errors for
`enableMonitorStreamRequired` or `broadcastStreamDelayMsRequired` when
updating a broadcast snippet or contentDetails.

**Root cause:** The API requires both `contentDetails.monitorStream.enableMonitorStream`
and `contentDetails.monitorStream.broadcastStreamDelayMs` to be present in the
body whenever `contentDetails` is included in the `part` parameter — even if
you only intend to change `enableEmbed` or `enableDvr`.

**Workaround:** Always include both `monitorStream` fields when sending a
`contentDetails` update:

```python
"contentDetails": {
    "enableEmbed": embeddable,
    "enableDvr": enable_dvr,
    "monitorStream": {
        "enableMonitorStream": False,
        "broadcastStreamDelayMs": 0,   # must be included
    },
}
```

---

## Quota is consumed by failed requests

**Symptom:** Quota runs low faster than expected, especially in error-retry
scenarios.

**Root cause:** All API requests — including those that return errors —
consume at least 1 quota unit. Write operations that fail still cost 50
units. A retry loop that repeatedly hits `errorStreamInactive` while
transitioning will burn quota on each failed attempt.

**Workaround:** Poll stream status and confirm `active` before transitioning,
rather than calling transition and handling the error. Read operations (1 unit)
are cheap; write operations (50 units) are not.

---

## `liveStreamingDetails.concurrentViewers` unavailable after archive

**Symptom:** `videos.list?part=liveStreamingDetails` returns no viewer count
for a completed broadcast.

**Root cause:** YouTube stops tracking `concurrentViewers` as soon as the
broadcast transitions to `complete`. The value is not persisted or accessible
after the stream ends. There is no API method to retrieve historical peak
viewer counts.

**Workaround:** If viewer counts are needed, record them during the live phase
by polling `liveStreamingDetails.concurrentViewers` while the broadcast is
`live`.
