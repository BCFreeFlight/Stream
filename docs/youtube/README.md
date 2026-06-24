---
title: "YouTube Live Streaming API — Reference Guide"
description: Comprehensive reference for every YouTube Data API v3 Live Streaming surface used by BC Free Flight Stream, covering broadcasts, streams, videos, authentication, and known quirks.
category: youtube-api
tags:
  - youtube
  - broadcast
  - streams
  - oauth
  - live-streaming
---

# YouTube Live Streaming API — Reference Guide

Comprehensive documentation for the YouTube Data API v3 Live Streaming features
as used in **BC Free Flight Stream**. Written for both humans and AI tooling.

---

## Scope

This guide covers every API surface the project touches:

| Section | API surface |
|---------|-------------|
| [Authentication](authentication.md) | OAuth 2.0, scopes, token lifecycle, quota |
| [Broadcasts](broadcasts.md) | `liveBroadcasts` resource — all methods |
| [Streams](streams.md) | `liveStreams` resource — all methods |
| [Videos](videos.md) | `videos` resource — live broadcast video properties |
| [Gotchas](gotchas.md) | Documented quirks, undocumented constraints, known bugs |

---

## Quick reference — API calls made by this project

| Call | Method | When |
|------|--------|------|
| Create broadcast | `liveBroadcasts.insert` | `--install`, `--start` (fresh broadcast after complete) |
| List broadcasts | `liveBroadcasts.list` | `--start` (orphan cleanup) |
| Update broadcast snippet | `liveBroadcasts.update` (part=snippet) | `--start` (update title) |
| Update broadcast content details | `liveBroadcasts.update` (part=contentDetails) | `--install` (embeddable, DVR, monitor) |
| Bind stream to broadcast | `liveBroadcasts.bind` | `--install`, `--start` |
| Transition broadcast | `liveBroadcasts.transition` | `--start` (testing → live), `--stop` (live → complete) |
| Delete broadcast | `liveBroadcasts.delete` | `--start` (orphans in created/ready state) |
| Get broadcast lifecycle status | `liveBroadcasts.list` (by id) | `--start`, `--stop` (lifecycle checks) |
| Create stream resource | `liveStreams.insert` | `--install` |
| List stream resources | `liveStreams.list` | `--start` (resolve stream ID from key) |
| Get stream status | `liveStreams.list` (by id) | `--start` (poll until active) |
| Get video snippet | `videos.list` (part=snippet) | `--install` (before setting category) |
| Update video snippet | `videos.update` (part=snippet) | `--install` (set categoryId) |
| Get video status | `videos.list` (part=status) | `--install` (before setting embeddable) |
| Update video status | `videos.update` (part=status) | `--install`, `--stop` (embeddable, archivePrivacy) |

---

## Broadcast state machine at a glance

```
created → ready → testing → live → complete
              ↑                        ↑
          (deleted)              (archived VOD)
```

- `created` and `ready` must be **deleted** — they cannot transition to `complete`.
- `complete` broadcasts are **archived** as VODs on the channel.
- A broadcast in `complete` state **cannot be reused** — a new one must be created.

Full state machine details: [broadcasts.md → State machine](broadcasts.md#state-machine).

---

## Embed URL patterns

| Pattern | URL | Notes |
|---------|-----|-------|
| Channel embed (stable) | `https://www.youtube.com/embed/live_stream?channel=<channelId>` | Always resolves to the current live broadcast. Safe to hardcode. |
| Broadcast embed (ephemeral) | `https://www.youtube.com/embed/<broadcastId>` | Tied to one broadcast. Breaks when the broadcast rotates. |
| Direct watch URL | `https://youtube.com/live/<broadcastId>` | Useful for logging; do not embed. |

This project uses the **channel embed** exclusively. See [ADR-0009](../adr/0009-stable-channel-embed-url.md).

---

## Prerequisites

- A Google Cloud project with the **YouTube Data API v3** enabled
- An OAuth 2.0 client (Desktop app type) — client ID + secret
- At least one YouTube channel associated with the authorized Google account
- The account must be eligible for live streaming (phone verification may be required for new accounts)
