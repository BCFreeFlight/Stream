---
title: "YouTube Data API v3 — liveBroadcasts Resource"
description: Reference for the YouTube Data API v3 liveBroadcasts resource, covering broadcast lifecycle states, valid transitions, and API methods used to create, manage, and archive live broadcasts.
category: youtube-api
tags:
  - youtube
  - broadcast
  - lifecycle
  - live-streaming
  - api
---

# YouTube Data API v3 — `liveBroadcasts` Resource

A **broadcast** represents a YouTube live event. It has a title, privacy
setting, lifecycle state, and a bound stream resource that delivers the video
content. Broadcasts can be archived as VODs when completed.

---

## State machine

Broadcasts move through a linear lifecycle. Not all transitions are allowed
from all states.

```
created ──────────────────────────── delete
   │
   ▼ (automatic, once stream is bound and checked)
 ready ────────────────────────────── delete
   │
   ▼ (liveBroadcasts.transition → testing)
testing ──────────────────────────── complete
   │
   ▼ (liveBroadcasts.transition → live)
 live ─────────────────────────────── complete
   │
   ▼ (liveBroadcasts.transition → complete, or automatic on stream end)
complete  (archived VOD — cannot be transitioned further)
```

### Valid transitions

| From | To | Method |
|------|-----|--------|
| `ready` | `testing` | `liveBroadcasts.transition` |
| `testing` | `live` | `liveBroadcasts.transition` |
| `testing` | `complete` | `liveBroadcasts.transition` |
| `live` | `complete` | `liveBroadcasts.transition` |
| `created` | (no transition) | **delete only** |
| `ready` | (no transition to complete) | **delete only** |

> **Critical gotcha:** Broadcasts in `created` or `ready` state **cannot** be
> transitioned to `complete`. Attempting to do so returns a `400 Bad Request`
> with `invalidTransition`. They must be **deleted** instead.
> See [Gotchas → State transition errors](gotchas.md#state-transition-errors).

### `lifeCycleStatus` values (full set)

| Value | Meaning |
|-------|---------|
| `created` | Broadcast created, not yet checked or ready |
| `ready` | Stream is bound and health checks passed |
| `testStarting` | Transitioning to testing (transient) |
| `testing` | Live in monitor stream only |
| `liveStarting` | Transitioning to live (transient) |
| `live` | Live on the public channel |
| `complete` | Broadcast ended, archived as VOD |
| `revoked` | Removed by YouTube policy |

---

## `liveBroadcasts.insert`

Creates a new broadcast. The stream resource must be bound separately.

### Request

```python
youtube.liveBroadcasts().insert(
    part="snippet,status,contentDetails",
    body={
        "snippet": {
            "title": "My Stream: 2026-04-12",
            "scheduledStartTime": "2026-04-12T06:30:00+00:00",  # required
        },
        "status": {
            "privacyStatus": "public",           # public | unlisted | private
            "selfDeclaredMadeForKids": False,     # required — omitting causes errors
        },
        "contentDetails": {
            "monitorStream": {
                "enableMonitorStream": False,     # true = test in YouTube Studio first
            },
            "enableAutoStart": False,             # true = go live when stream data arrives
            "enableAutoStop": False,              # true = auto-complete when stream ends
            "enableDvr": False,                   # true = allow viewers to rewind
        },
    }
).execute()
```

### Response shape

```json
{
  "kind": "youtube#liveBroadcast",
  "id": "<broadcastId>",
  "snippet": {
    "title": "My Stream: 2026-04-12",
    "scheduledStartTime": "2026-04-12T06:30:00.000Z",
    "channelId": "<channelId>"
  },
  "status": {
    "lifeCycleStatus": "created",
    "privacyStatus": "public",
    "recordingStatus": "notRecording"
  },
  "contentDetails": {
    "enableEmbed": true,
    "enableDvr": false,
    "enableAutoStart": false,
    "enableAutoStop": false,
    "monitorStream": {
      "enableMonitorStream": false
    }
  }
}
```

### Key parameters

| Field | Required | Notes |
|-------|----------|-------|
| `snippet.title` | Yes | Max 100 characters |
| `snippet.scheduledStartTime` | Yes | RFC 3339 datetime. Must be set even for immediate starts. |
| `status.privacyStatus` | Yes | `public`, `unlisted`, or `private` |
| `status.selfDeclaredMadeForKids` | Yes (effectively) | Omitting or leaving null causes unpredictable behavior |
| `contentDetails.enableAutoStop` | Recommended: `false` | If `true`, YouTube auto-completes the broadcast the moment the stream goes inactive — brief network hiccups end the broadcast permanently. |

---

## `liveBroadcasts.list`

Lists broadcasts. Supports filtering by status or fetching by ID.

### Fetch by ID (lifecycle check)

```python
resp = youtube.liveBroadcasts().list(
    part="status",
    id="<broadcastId>"
).execute()
status = resp["items"][0]["status"]["lifeCycleStatus"]
```

### List all channel broadcasts

```python
resp = youtube.liveBroadcasts().list(
    part="id,status",
    mine=True,
    maxResults=50
).execute()
items = resp.get("items", [])
```

> **Critical gotcha:** The API **rejects** requests that combine `mine=True`
> with a `broadcastStatus` filter. You must list all broadcasts and filter
> `lifeCycleStatus` client-side. See [Gotchas → mine=True + broadcastStatus](gotchas.md#mine-true-broadcaststatus-conflict).

### Pagination

Results are paginated. If the channel has more than `maxResults` broadcasts,
the response includes a `nextPageToken`. For orphan cleanup purposes,
`maxResults=50` covers all realistic scenarios.

```python
page_token = None
while True:
    resp = youtube.liveBroadcasts().list(
        part="id,status",
        mine=True,
        maxResults=50,
        pageToken=page_token
    ).execute()
    items.extend(resp.get("items", []))
    page_token = resp.get("nextPageToken")
    if not page_token:
        break
```

---

## `liveBroadcasts.update`

Updates broadcast properties. The `part` parameter must exactly match the
resource sections being written.

### Update snippet (title)

```python
# Always fetch the full snippet first — the API replaces the entire section.
resp = youtube.liveBroadcasts().list(part="snippet", id=broadcast_id).execute()
snippet = resp["items"][0]["snippet"]
snippet["title"] = new_title
youtube.liveBroadcasts().update(
    part="snippet",
    body={"id": broadcast_id, "snippet": snippet}
).execute()
```

> **Gotcha:** Never construct a snippet from scratch for an update. The snippet
> contains fields like `channelId`, `publishedAt`, `actualStartTime` that are
> set by YouTube. If you send a partial snippet, those fields are cleared or
> the call fails with `400`. Always read–modify–write.

### Update contentDetails (embeddable, DVR, monitor stream)

```python
youtube.liveBroadcasts().update(
    part="contentDetails",
    body={
        "id": broadcast_id,
        "contentDetails": {
            "enableEmbed": True,
            "enableDvr": False,
            "monitorStream": {
                "enableMonitorStream": False,
            },
        },
    }
).execute()
```

> **Gotcha:** When updating `contentDetails`, you **must** include
> `monitorStream` in the body even if you're not changing it. The API treats
> the entire `contentDetails` object as a replacement — omitting `monitorStream`
> resets it to the default (enabled). See [ADR-0010](../adr/0010-embeddable-dual-flag.md).

---

## `liveBroadcasts.bind`

Associates a `liveStream` resource with a broadcast. A broadcast can only
deliver video once a stream is bound to it.

```python
youtube.liveBroadcasts().bind(
    part="id,contentDetails",
    id=broadcast_id,
    streamId=stream_id
).execute()
```

- Binding can only be done while the broadcast is in `created` or `ready` state.
- A stream can be re-bound to a new broadcast; this is how fresh daily
  broadcasts reuse a permanent stream resource.
- The `part` parameter must include at least `id` and `contentDetails`.

---

## `liveBroadcasts.transition`

Changes the broadcast's lifecycle state. The stream must be active (ingesting
data) before a `→ testing` or `→ live` transition will succeed.

```python
youtube.liveBroadcasts().transition(
    broadcastStatus="live",   # "testing" | "live" | "complete"
    id=broadcast_id,
    part="id,status"
).execute()
```

### Transition sequence

```
ready → testing → live → complete
```

You **cannot** skip `testing`. To go from `ready` to `live`:
1. Transition `→ testing`
2. Poll until `lifeCycleStatus == "testing"`
3. Transition `→ live`

### `streamStatus` must be `active` before transitioning

If you call `liveBroadcasts.transition → testing` before the stream is
ingesting data, the API returns:

```
400 Bad Request
{
  "error": {
    "code": 400,
    "message": "The transition cannot be performed since the specified broadcast is not in the correct state.",
    "errors": [{ "reason": "invalidTransition" }]
  }
}
```

Wait for `liveStreams.list → items[0].status.streamStatus == "active"` before
transitioning. See [streams.md → Polling stream status](streams.md#polling-stream-status).

### Transient states

YouTube uses `testStarting` and `liveStarting` as transient states during
transitions. These are not values you pass to `broadcastStatus` — they appear
in `lifeCycleStatus` responses while the transition is in progress. Poll until
you reach the target state before proceeding.

---

## `liveBroadcasts.delete`

Deletes a broadcast permanently. Only valid for broadcasts in `created` or
`ready` state.

```python
youtube.liveBroadcasts().delete(id=broadcast_id).execute()
```

- Returns HTTP 204 (no body) on success.
- Will fail with `403 liveBroadcastDeletionNotAllowed` on broadcasts in
  `testing`, `live`, or `complete` state.

---

## Orphan cleanup pattern

When a crash leaves broadcasts in an active state, the next `--start` must
clean them up. Because `mine=True + broadcastStatus` is rejected, filter
client-side:

```python
items = youtube.liveBroadcasts().list(
    part="id,status", mine=True, maxResults=50
).execute().get("items", [])

for item in items:
    bid = item["id"]
    if bid == current_broadcast_id:
        continue
    lifecycle = item.get("status", {}).get("lifeCycleStatus", "")
    if lifecycle in ("live", "testing"):
        youtube.liveBroadcasts().transition(
            broadcastStatus="complete", id=bid, part="id,status"
        ).execute()
    elif lifecycle in ("created", "ready"):
        youtube.liveBroadcasts().delete(id=bid).execute()
```

---

## API error codes reference

### `liveBroadcasts.insert` errors

| HTTP | Code | Meaning |
|------|------|---------|
| 400 | `titleRequired` | `snippet.title` missing |
| 400 | `scheduledStartTimeRequired` | `snippet.scheduledStartTime` missing |
| 400 | `privacyStatusRequired` | `status.privacyStatus` missing |
| 400 | `invalidTitle` | Title violates length/content constraints |
| 400 | `invalidPrivacyStatus` | Privacy value not `public`/`unlisted`/`private` |
| 400 | `invalidScheduledStartTime` | Time is in the past or malformed |
| 400 | `invalidAutoStart` / `invalidAutoStop` | Invalid auto-start/stop setting |
| 403 | `insufficientLivePermissions` | Account not authorized for live streaming |
| 403 | `livePermissionBlocked` | Account is blocked from live streaming |
| 403 | `liveStreamingNotEnabled` | Account has not enabled live streaming (may need phone verification) |
| 429 | `userBroadcastsExceedLimit` | Too many broadcasts on channel; delete old ones |

### `liveBroadcasts.transition` errors

| HTTP | Code | Meaning |
|------|------|---------|
| 400 | `idRequired` | Broadcast ID missing |
| 400 | `statusRequired` | `broadcastStatus` parameter missing |
| 403 | `invalidTransition` | Transition not allowed from current state |
| 403 | `redundantTransition` | Already in or moving to the requested state |
| 403 | `errorStreamInactive` | Bound stream is not active — wait for `streamStatus == "active"` |
| 403 | `concurrentBroadcastsExceedLimit` | Channel at maximum concurrent live broadcasts |
| 500 | `errorExecutingTransition` | Server-side failure; retry after a delay |

### `liveBroadcasts.update` restricted fields

These fields **cannot be changed** once the broadcast is in `testing` or `live`:

| Field | Error code |
|-------|-----------|
| `contentDetails.monitorStream.enableMonitorStream` | `enableMonitorStreamModificationNotAllowed` |
| `contentDetails.enableDvr` | `enableDvrModificationNotAllowed` |
| `contentDetails.enableEmbed` | (forbidden) |
| `contentDetails.recordFromStart` | `recordFromStartModificationNotAllowed` |
| `contentDetails.closedCaptionsType` | `closedCaptionsTypeModificationNotAllowed` |
| `contentDetails.enableAutoStart` | `enableAutoStartModificationNotAllowed` |

---

## Embeddable flag on the broadcast

The broadcast has its own `contentDetails.enableEmbed` flag **separate** from
the underlying video resource's embeddable flag. Both must be `true` for
embedding to work on all clients. See [videos.md → Embeddable flag](videos.md#embeddable-flag).

Setting via `liveBroadcasts.update`:

```python
youtube.liveBroadcasts().update(
    part="contentDetails",
    body={
        "id": broadcast_id,
        "contentDetails": {
            "enableEmbed": True,
            "enableDvr": False,
            "monitorStream": {"enableMonitorStream": False},
        },
    }
).execute()
```
