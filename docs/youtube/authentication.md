---
title: "YouTube Data API v3 — Authentication"
description: Covers OAuth 2.0 setup, required scopes, quota costs, and token lifecycle for authenticating with the YouTube Data API v3.
category: youtube-api
tags:
  - oauth
  - youtube
  - authentication
  - quota
  - tokens
---

# YouTube Data API v3 — Authentication

## OAuth 2.0 overview

The YouTube Data API v3 requires OAuth 2.0 for all operations that read or
modify a user's YouTube channel. There is no API-key-only path for live
streaming. The OAuth client type **must** be **Desktop app** (formerly
"Installed application") — not "Web application" — because the redirect URI
needs to work on a machine without a public hostname.

---

## Scopes required

| Scope | Why |
|-------|-----|
| `https://www.googleapis.com/auth/youtube` | Full read/write access to the account's YouTube resources |
| `https://www.googleapis.com/auth/youtube.force-ssl` | Forces all connections over HTTPS; required by some liveBroadcasts mutations |

Both scopes must be requested together. Requesting only one will cause API calls
to fail with a `403 insufficientPermissions` error.

---

## Quota

The YouTube Data API v3 uses a unit-based quota system, **not** a simple
request count. The default quota is **10,000 units per day** per Google Cloud
project.

### Write operation costs

| Operation | Cost |
|-----------|------|
| `liveBroadcasts.insert` | 50 units |
| `liveBroadcasts.update` | 50 units |
| `liveBroadcasts.bind` | 50 units |
| `liveBroadcasts.transition` | 50 units |
| `liveBroadcasts.delete` | 50 units |
| `liveStreams.insert` | 50 units |
| `videos.update` | 50 units |

### Read operation costs

| Operation | Cost |
|-----------|------|
| `liveBroadcasts.list` | 1 unit |
| `liveStreams.list` | 1 unit |
| `videos.list` | 1 unit |

### Budget estimate for a daily run

A typical `--start` sequence (clean slate, no orphans):

1. `liveBroadcasts.list` (orphan cleanup): 1
2. `liveBroadcasts.transition → complete` (retire current): 50
3. `liveBroadcasts.list` (lifecycle check): 1
4. `liveStreams.list` × up to 120 (polling stream active, worst case): 120
5. `liveBroadcasts.transition → testing`: 50
6. `liveBroadcasts.transition → live`: 50
7. `liveBroadcasts.list` (title update prerequisite): 1
8. `liveBroadcasts.update` (title update): 50

**Total per run:** ~323 units. Well within the 10,000 daily limit for normal use.

If crashes cause many retries with orphan cleanup each time, usage increases.
Monitor quota at: **Google Cloud Console → APIs & Services → YouTube Data API v3 → Quotas**.

---

## Token lifecycle

```
 Client ID + Secret  (permanent — entered at --install, stored in config.toml / .env)
         │
         ▼
  [Browser OAuth flow]
         │
         ├── Refresh Token  (long-lived — stored in .env, survives for months/years)
         │
         └── Access Token   (short-lived, ~1 hour — stored in .env, refreshed automatically)
```

### Token storage

| Token | File | Key |
|-------|------|-----|
| Client ID | `config.toml` | `google.clientId` |
| Client Secret | `.env` | `GOOGLE_CLIENT_SECRET` |
| Refresh Token | `.env` | `GOOGLE_REFRESH_TOKEN` |
| Access Token | `.env` | `GOOGLE_ACCESS_TOKEN` |

Secrets are **never** written to `config.toml` and never logged.

### Token refresh flow

On each `--start`/`--stop`/`--recover`:

1. Load `.env` into the environment.
2. If no `GOOGLE_REFRESH_TOKEN` is set → run the full browser OAuth flow.
3. Build a `Credentials` object from the stored tokens.
4. If the access token is still valid → use it directly.
5. If expired → call `creds.refresh(GoogleAuthRequest())`, which hits
   `https://oauth2.googleapis.com/token` with the refresh token.
6. Save the new access token back to `.env`.
7. If refresh fails → fall back to the browser OAuth flow.

### When refresh tokens expire

Google refresh tokens for Desktop apps are **long-lived** (months to years)
but can be invalidated by:
- The user revokes access from [Google Account security page](https://myaccount.google.com/permissions)
- The Google Cloud project is deleted or the OAuth client is deleted
- The account password changes
- More than 50 refresh tokens are issued for the same client (oldest is revoked)

When a refresh token is invalidated, the next run will open the browser flow.

---

## Creating the OAuth client

1. Go to **Google Cloud Console → APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Application type: **Desktop app**
4. Give it a name (e.g. "BC Free Flight Stream")
5. Download the JSON, or copy the **Client ID** and **Client Secret** directly
6. On the **OAuth consent screen**, add the two scopes listed above
7. If the app is in "Testing" status, add the Google account that owns the
   YouTube channel as a **Test user** — otherwise OAuth will fail with
   `access_denied`

> **Important:** If the OAuth consent screen is in "Testing" status, tokens
> expire after **7 days** regardless. Publish the consent screen (or switch to
> an internal app if the GCP org allows it) to get long-lived tokens.

---

## Python implementation

This project uses `google-auth-oauthlib` and `google-auth`:

```python
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# Initial flow (browser opens automatically)
flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(port=0, prompt="select_account")

# Refresh expired token
creds = Credentials(token=access_token, refresh_token=refresh_token, ...)
creds.refresh(GoogleAuthRequest())

# Build the API service
from googleapiclient.discovery import build
youtube = build("youtube", "v3", credentials=creds)
```

The `prompt="select_account"` argument forces the Google account chooser to
appear every time, preventing silent re-authorization of the wrong account on
multi-account machines. See [ADR-0022](../adr/0022-force-account-selection.md).
