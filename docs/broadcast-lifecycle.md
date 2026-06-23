# YouTube Broadcast Lifecycle

## Two resources

| Resource | Created | Lifetime |
|----------|---------|----------|
| **Stream** (RTMP URL + key) | once, at `--install` | permanent, reused forever |
| **Broadcast** | fresh on every `--start` | retired/archived on `--stop` |

A stream resource can be re-bound to many broadcasts. Keeping it permanent means the RTMP URL/key never change, while each day gets a clean broadcast. See [ADR-0007](adr/0007-fresh-broadcast-per-start.md).

The **embed URL is channel-based** and always points at the current live broadcast, so rotating broadcast IDs is invisible to viewers. See [ADR-0009](adr/0009-stable-channel-embed-url.md).

## Lifecycle states

YouTube broadcasts move through: `created` → `ready` → `testing` → `live` → `complete`.

| Transition | Allowed from |
|-----------|--------------|
| → `testing` | `ready` |
| → `live` | `testing` (or `ready` via testing) |
| → `complete` | `live`, `testing` |
| delete | `created`, `ready` (cannot be completed) |

## During `--install`

1. `liveBroadcasts.insert` — create broadcast (`enableAutoStop: false`, `enableAutoStart: false`)
2. `liveStreams.insert` — create stream resource
3. `liveBroadcasts.bind` — bind stream to broadcast
4. Persist `broadcastId`, `streamURL`, `backupStreamUrl`, `streamKey`
5. Apply `categoryId` and `embeddable` (broadcast + video)

`enableAutoStop: false` keeps YouTube from auto-completing the broadcast during brief ingest gaps.

## During `--start`

```
1. cleanup orphaned broadcasts   (complete live/testing, delete created/ready)
2. retire current broadcast      (if active, transition → complete)
3. launch ffmpeg
4. wait for stream → active
5. ensure broadcast live:
      complete  → create fresh broadcast, bind stream, update config → live
      ready/created → testing → live
      testing   → live
      live      → no-op
6. update broadcast title with today's date   (AFTER step 5)
```

Title update happens **after** `ensure_broadcast_live` so it stamps the *new* broadcast, never yesterday's archived one. Doing it earlier corrupted the prior day's VOD title with tomorrow's date. See [ADR-0019](adr/0019-title-update-after-ensure-live.md).

Orphan cleanup is client-side: the Data API rejects `mine=True` combined with a `broadcastStatus` filter, so the script lists all broadcasts and filters by `lifeCycleStatus` itself. Orphans in `created`/`ready` are deleted (they cannot transition to `complete`); `live`/`testing` are completed (PR #19).

## During `--stop`

1. Stop ffmpeg
2. If broadcast is `live`, transition → `complete` (archived as VOD)
3. Apply `archivePrivacy` to the archived video

Completing on stop is what makes past streams watchable on the channel. See [ADR-0008](adr/0008-complete-broadcast-on-stop.md).

## Embeddable: two flags

Embedding requires **both** the broadcast-level and video-level `embeddable` flags to be true. Mobile browsers enforce the video-level flag strictly; desktop is lenient. The video resource is created asynchronously, so the script polls until it exists before setting its flag. See [ADR-0010](adr/0010-embeddable-dual-flag.md).

## Retry behavior

On retry, the script reconnects to the **same** broadcast — it does not create a new one mid-session — alternating primary/backup RTMP URLs. See [streaming](streaming.md#retry-loop).
