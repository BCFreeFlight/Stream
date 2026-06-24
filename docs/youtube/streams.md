---
title: "YouTube Data API v3 — liveStreams Resource"
description: Reference for the YouTube Data API v3 liveStreams resource, covering how stream ingestion points are created, structured, and reused across broadcasts in this project.
category: youtube-api
tags:
  - youtube
  - streams
  - rtmp
  - liveStreams
  - ingestion
---

# YouTube Data API v3 — `liveStreams` Resource

A **stream** resource (also called a "live stream ingestion point") represents
the RTMP ingest endpoint that receives video data from ffmpeg. It is separate
from a broadcast — multiple broadcasts can be bound to the same stream over
time.

---

## Stream vs. broadcast

| Concept | Resource | Lifetime |
|---------|----------|----------|
| Ingest endpoint (RTMP URL + key) | `liveStream` | Permanent — created once at `--install`, reused forever |
| Live event (title, privacy, lifecycle) | `liveBroadcast` | Ephemeral — new one per `--start` |

A single stream resource can be re-bound to any number of successive broadcasts.
This means the RTMP URL and stream key never change — ffmpeg configuration is
stable — while each day gets a fresh broadcast with a new title and archive.

See [ADR-0007](../adr/0007-fresh-broadcast-per-start.md) and
[ADR-0012](../adr/0012-resolve-stream-id-from-key.md).

---

## `liveStreams.insert`

Creates a new stream resource and returns the RTMP ingest credentials.

### Request

```python
resp = youtube.liveStreams().insert(
    part="snippet,cdn",
    body={
        "snippet": {
            "title": "My stream resource",
        },
        "cdn": {
            "frameRate": "variable",     # "30fps" | "60fps" | "variable"
            "ingestionType": "rtmp",     # always "rtmp" for RTMP ingest
            "resolution": "variable",    # "1080p" | "720p" | "480p" | "360p" | "240p" | "variable"
        },
    }
).execute()
```

### Response shape

```json
{
  "kind": "youtube#liveStream",
  "id": "<streamId>",
  "snippet": {
    "title": "My stream resource",
    "channelId": "<channelId>"
  },
  "cdn": {
    "frameRate": "variable",
    "resolution": "variable",
    "ingestionType": "rtmp",
    "ingestionInfo": {
      "streamName": "<streamKey>",
      "ingestionAddress": "rtmp://a.rtmp.youtube.com/live2",
      "backupIngestionAddress": "rtmp://b.rtmp.youtube.com/live2"
    }
  },
  "status": {
    "streamStatus": "inactive"
  }
}
```

### Key fields

| Field | Location | Notes |
|-------|----------|-------|
| Stream key | `cdn.ingestionInfo.streamName` | Treat as a secret — never log |
| Primary RTMP URL | `cdn.ingestionInfo.ingestionAddress` | Combine with stream key: `<url>/<key>` |
| Backup RTMP URL | `cdn.ingestionInfo.backupIngestionAddress` | May be empty string; check before using |
| Primary RTMPS URL | `cdn.ingestionInfo.rtmpsIngestionAddress` | TLS-encrypted ingest; same key |
| Backup RTMPS URL | `cdn.ingestionInfo.rtmpsBackupIngestionAddress` | TLS-encrypted backup |
| Stream ID | `id` | Used to bind to broadcasts; **do not persist** — resolve at runtime from the key |

> **Why not persist the stream ID?** Stream IDs can change across
> re-authentications or if the stream resource is deleted and recreated.
> The stream key is stable. This project resolves the stream ID at runtime by
> searching for a stream whose `streamName` matches the stored key.
> See [ADR-0012](../adr/0012-resolve-stream-id-from-key.md).

### `frameRate` and `resolution`

Use `"variable"` for both unless you have specific requirements. `"variable"`
accepts any combination of frame rate and resolution from the ingest, which
matches the behavior of `ffmpeg -vcodec copy` (passthrough).

---

## `liveStreams.list`

Lists stream resources. Used both to find a stream by key and to poll its
status.

### Find a stream by key

The stream ID is not persisted — it is resolved at startup by scanning all
streams for one whose `streamName` matches the configured key.

```python
resp = youtube.liveStreams().list(part="cdn", mine=True).execute()
for item in resp.get("items", []):
    info = item["cdn"]["ingestionInfo"]
    if info["streamName"] == stream_key:
        stream_id = item["id"]
        rtmp_url = info["ingestionAddress"]
        backup_url = info.get("backupIngestionAddress", "")
        break
```

### Fetch by ID (status poll)

```python
resp = youtube.liveStreams().list(part="status", id=stream_id).execute()
items = resp.get("items", [])
stream_status = items[0]["status"]["streamStatus"] if items else None
```

---

## `streamStatus` values

| Value | Meaning |
|-------|---------|
| `inactive` | No data being received |
| `active` | Data is actively being ingested |
| `error` | Error condition — check `healthStatus` |
| `ready` | Stream is bound and ready but not yet receiving data |

The script waits for `active` before transitioning the broadcast to `testing`.

---

## Polling stream status

After launching ffmpeg, wait for the stream to become `active` before
transitioning the broadcast. The stream typically takes 10–30 seconds to
become active after ffmpeg starts sending data.

```python
for _ in range(120):   # up to ~10 minutes
    resp = youtube.liveStreams().list(part="status", id=stream_id).execute()
    items = resp.get("items", [])
    status = items[0]["status"]["streamStatus"] if items else None
    if status == "active":
        break
    time.sleep(5)
else:
    raise RuntimeError("Stream did not become active within timeout")
```

> **Gotcha:** If you transition the broadcast `→ testing` or `→ live` before
> the stream is `active`, the API returns `400 invalidTransition`. The stream
> must be ingesting data first.

> **Gotcha:** YouTube's live ingest **rejects video-only streams**. If ffmpeg
> sends video with no audio track, the stream status will remain `inactive`
> indefinitely. An audio track — even a silent one — is required. See
> [Gotchas → Video-only ingest](gotchas.md#video-only-ingest-stays-inactive).

---

## RTMP ingest URLs

YouTube provides two ingest URLs:

| URL | Purpose |
|-----|---------|
| `rtmp://a.rtmp.youtube.com/live2` | Primary ingest |
| `rtmp://b.rtmp.youtube.com/live2` | Backup ingest |

Both use the same stream key. The ffmpeg command appends the key to the URL:

```
ffmpeg ... -f flv rtmp://a.rtmp.youtube.com/live2/<streamKey>
```

This project alternates between primary and backup on retry — even attempts
use primary, odd attempts use backup. See [streaming.md](../streaming.md#retry-loop).

---

## Stream health status

The stream's `status` object provides detailed health information for
diagnosing ingest issues:

```python
resp = youtube.liveStreams().list(part="status", id=stream_id).execute()
status = resp["items"][0]["status"]
health = status.get("healthStatus", {})

print(health["status"])           # "good" | "ok" | "bad" | "noData"
for issue in health.get("configurationIssues", []):
    print(issue["severity"])      # "info" | "warning" | "error"
    print(issue["type"])          # see table below
    print(issue["description"])   # human-readable resolution guidance
```

### Common configuration issue types

| Issue type | Severity | Meaning |
|-----------|----------|---------|
| `noAudioStream` | error | No audio track — YouTube will reject the stream |
| `noVideoStream` | error | No video track |
| `videoCodec` | error | Video codec not H.264 |
| `audioCodec` | error | Audio codec not AAC or MP3 |
| `badContainer` | error | Container not FLV (RTMP requires FLV) |
| `gopSizeLong` | warning | Keyframe interval too long (>4s recommended) |
| `gopSizeOver` | error | Keyframe interval exceeds maximum |
| `openGop` | warning | Open GOP detected |
| `bitrateHigh` | warning | Ingest bitrate above recommended for the resolution |
| `bitrateLow` | warning | Ingest bitrate below recommended |
| `audioTooManyChannels` | error | >2 audio channels; only mono/stereo accepted |
| `videoResolutionUnsupported` | error | Resolution not supported by the stream config |
| `videoInterlaceMismatch` | warning | Interlaced input detected |
| `multipleAudioStreams` | warning | Multiple audio streams in the ingest |
| `multipleVideoStreams` | warning | Multiple video streams in the ingest |

---

## Stream resource persistence

Stream resources are **permanent** for the lifetime of the YouTube channel
unless explicitly deleted. One stream resource is sufficient for indefinite
daily operation — bind it to a new broadcast each day.

YouTube's UI ("YouTube Studio → Live") shows stream resources under
"Stream settings". The RTMP URL and key are visible there and match what the
API returns.
