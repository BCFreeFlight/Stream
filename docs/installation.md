---
title: Installation
description: Step-by-step guide to installing and configuring the BC Free Flight Stream script, including Google Cloud setup, OAuth authentication, and cron registration.
category: guide
tags:
  - installation
  - oauth
  - ffmpeg
  - cron
  - youtube
---

# Installation

## Requirements

- Linux Mint / Ubuntu-based system
- Python 3.8+
- A Google Cloud project with **YouTube Data API v3** enabled
- An RTSP-capable camera reachable from the host

See [REQUIREMENTS.md](../REQUIREMENTS.md) for the full list.

## Quick install

```bash
curl -fLO https://github.com/BCFreeFlight/Stream/releases/latest/download/stream.py && python3 stream.py --install
```

`stream.py` self-downloads companion assets (`resources.toml`) on first run ([ADR-0003](adr/0003-self-download-release-assets.md)) and self-installs Python dependencies ([ADR-0002](adr/0002-self-installing-dependencies.md)). `ffmpeg` is installed via `apt` during `--install` if missing.

## Google Cloud setup

1. [Google Cloud Console](https://console.cloud.google.com/) → create/select a project
2. **APIs & Services → Library** → enable **YouTube Data API v3**
3. **OAuth consent screen** → External → add your account as a test user
4. **Credentials → Create Credentials → OAuth client ID → Desktop app**
5. Copy the **Client ID** and **Client Secret** for `--install`

The interactive wizard prints these same steps if no credentials are configured.

## What `--install` does

| Step | Detail |
|------|--------|
| Prompt | Only for empty/missing values (idempotent — [ADR-0024](adr/0024-idempotent-install.md)) |
| Write files | `config.toml` and `.env` beside the script |
| ffmpeg | `apt install -y ffmpeg` if not on PATH |
| OAuth | Browser flow, unless a valid refresh token already exists (then reused) |
| YouTube | Create broadcast + stream resource, bind them, set category/embeddable |
| Terminal | Auto-detect emulator for the cron job |
| Cron | Register start, stop, `@reboot` recover (+ update if `autoUpdate`) |

The stream resource (RTMP URL + key) is created **once** here and reused permanently; only the broadcast rotates. See [broadcast lifecycle](broadcast-lifecycle.md).

## Idempotency

Re-running `--install` is safe: existing config is loaded, existing OAuth credentials/YouTube resources are reused, and cron entries are replaced (not duplicated, thanks to the `# bcfreeflight_stream` marker). Use it to apply new config or repair cron.

## Reusing an existing stream key

During `--install` you may paste an existing YouTube stream key to reuse its RTMP resource instead of generating a new one (PR #28). Leave blank to auto-create.

## Uninstall vs Reinstall

| Command | Stops stream | Removes cron | Deletes config/.env | Keeps logs/backup |
|---------|:---:|:---:|:---:|:---:|
| `--uninstall` | ✅ | ✅ | ❌ (preserved) | ✅ |
| `--reinstall` | ✅ | ✅ | ✅ (after `yes`) | ✅ |

Use `--uninstall` to pause unattended operation while keeping credentials. Use `--reinstall` to switch Google accounts or start fresh.
