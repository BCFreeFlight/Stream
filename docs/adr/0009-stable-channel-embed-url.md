---
title: "ADR-0009: Use the channel-based stable embed URL"
description: Documents the decision to use a channel-based embed URL that remains stable across daily broadcast rotations.
category: adr
tags:
  - embed
  - broadcast
  - youtube
  - accepted
  - streams
---

# ADR-0009: Use the channel-based stable embed URL

**Status:** Accepted

## Context

Broadcast IDs rotate daily ([ADR-0007](0007-fresh-broadcast-per-start.md)). A URL tied to a specific broadcast ID would break every day and could not be safely embedded in a webpage.

## Decision

Embed the **channel** form, `/embed/live_stream?channel=<channelId>`, which always resolves to whatever broadcast is currently live on the channel. It is not tied to any broadcast ID.

## Consequences

- The embed URL is set once and never changes, even as broadcasts rotate.
- Safe to hardcode in a website.
- When nothing is live, the channel embed simply shows no active stream.
