---
title: "YouTube Data API v3 — videos Resource (Live Broadcast Context)"
description: "Reference for the YouTube videos resource as it relates to live broadcasts, covering the broadcast-to-video relationship, asynchronous creation, and how to read and update video properties."
category: youtube-api
tags:
  - youtube
  - broadcast
  - videos
  - api
  - embeddable
---

# YouTube Data API v3 — `videos` Resource (Live Broadcast Context)

When a `liveBroadcast` is created, YouTube automatically creates an associated
`video` resource. This video resource holds properties that are separate from
the broadcast — including the embeddable flag, category, and archive privacy
settings.

Understanding the relationship between the broadcast resource and its underlying
video resource is essential for controlling how archived content appears on the
channel.

---

## Broadcast → video relationship

| Broadcast field | Video field | Sync behavior |
|-----------------|-------------|---------------|
| `status.privacyStatus` | `status.privacyStatus` | Set independently; use `videos.update` for the archive privacy after `complete` |
| `contentDetails.enableEmbed` | `status.embeddable` | **Not synced** — must be set separately on both resources |
| `snippet.categoryId` | `snippet.categoryId` | Must be set via `videos.update`; broadcast insert does not accept it |

The broadcast ID and the video ID are **the same value**. Use it for both
`liveBroadcasts.*` and `videos.*` calls.

---

## Asynchronous video resource creation

> **Critical gotcha:** The video resource is **not** immediately available
> after `liveBroadcasts.insert`. YouTube creates it asynchronously.

If you call `videos.list` immediately after creating a broadcast, you will get
an empty `items` array. You must poll until the video appears:

```python
for _ in range(10):
    resp = youtube.videos().list(part="status", id=broadcast_id).execute()
    if resp.get("items"):
        break
    time.sleep(2)
else:
    # Video resource not yet available — skip the update
    pass
```

This typically resolves within 2–10 seconds but can take longer under load.

---

## `videos.list`

Fetches properties of the video resource. Used before any update to read the
current state.

### Fetch video snippet

```python
resp = youtube.videos().list(part="snippet", id=broadcast_id).execute()
items = resp.get("items", [])
snippet = items[0]["snippet"] if items else None
```

### Fetch video status

```python
resp = youtube.videos().list(part="status", id=broadcast_id).execute()
items = resp.get("items", [])
status = items[0]["status"] if items else None
```

---

## `videos.update`

Updates properties of the video resource. Always use read–modify–write: fetch
the current values, modify only what you need, send the full object back.

> **Gotcha:** Do not construct a snippet or status from scratch. The API
> replaces the entire section you send in `part`. Missing required fields
> (e.g., `categoryId` on a snippet, `privacyStatus` on a status) cause
> validation errors.

### Set video category

```python
resp = youtube.videos().list(part="snippet", id=broadcast_id).execute()
snippet = resp["items"][0]["snippet"]
snippet["categoryId"] = "22"   # 22 = People & Blogs
youtube.videos().update(
    part="snippet",
    body={"id": broadcast_id, "snippet": snippet}
).execute()
```

The `categoryId` must match an ID from YouTube's video category taxonomy for
the channel's content region. Common values:

| ID | Category |
|----|----------|
| `1` | Film & Animation |
| `2` | Autos & Vehicles |
| `10` | Music |
| `17` | Sports |
| `22` | People & Blogs |
| `23` | Comedy |
| `24` | Entertainment |
| `25` | News & Politics |
| `28` | Science & Technology |

> **Gotcha:** Not all category IDs are valid for all regions or for live
> streams. If a category is rejected with `400 invalidCategoryId`, fall back
> to `22` (People & Blogs), which is universally accepted.

---

## Embeddable flag

The video resource has an `embeddable` flag in its `status` object. This is
**separate** from `liveBroadcasts.contentDetails.enableEmbed`. Both must be
`true` for embedding to work reliably across all clients.

- Desktop browsers enforce the broadcast-level flag
- Mobile browsers enforce the video-level flag strictly
- Setting only one causes embeds to fail on some devices

### Set video embeddable

```python
resp = youtube.videos().list(part="status", id=broadcast_id).execute()
status = resp["items"][0]["status"]
status["embeddable"] = True
youtube.videos().update(
    part="status",
    body={"id": broadcast_id, "status": status}
).execute()
```

### Set broadcast embeddable

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

Both calls are required. See [ADR-0010](../adr/0010-embeddable-dual-flag.md).

---

## Archive privacy

After a broadcast is transitioned to `complete`, it becomes a VOD. The
`archivePrivacy` setting controls who can see the archived video.

```python
youtube.videos().update(
    part="status",
    body={
        "id": broadcast_id,
        "status": {
            "privacyStatus": "private",   # "public" | "unlisted" | "private"
        },
    }
).execute()
```

> **Note:** The broadcast's `status.privacyStatus` controls visibility
> **while live**. The `archivePrivacy` applied via `videos.update` after
> `complete` controls visibility of the **archived VOD**. These are independent.

> **Timing:** The video's privacy can only be updated after the broadcast is
> in `complete` state. Attempting to update it during `live` has no effect
> on the eventual archive.

---

## `videos` resource `status` fields relevant to live streaming

| Field | Type | Description |
|-------|------|-------------|
| `privacyStatus` | string | `public`, `unlisted`, or `private` |
| `embeddable` | boolean | Whether the video can be embedded on external sites |
| `madeForKids` | boolean | Set to `false` for general-audience content |
| `selfDeclaredMadeForKids` | boolean | Set during broadcast creation; reflected here |
| `publicStatsViewable` | boolean | Whether view count / likes are public |

---

## `videos` resource `snippet` fields relevant to live streaming

| Field | Type | Notes |
|-------|------|-------|
| `title` | string | Max 100 chars; also visible as the broadcast title |
| `categoryId` | string | Numeric string ID from the category taxonomy |
| `channelId` | string | Read-only; set by YouTube |
| `liveBroadcastContent` | string | `live`, `upcoming`, or `none` — read-only |

> **Gotcha:** `snippet.title` is shared between the video resource and the
> broadcast snippet. Updating it via `liveBroadcasts.update` and `videos.update`
> both work, but the change may take a few seconds to propagate across both.
