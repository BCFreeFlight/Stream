# Troubleshooting

Run any command with `--log-level debug` for full detail.

## Stream never goes live / status stuck `inactive`

| Cause | Fix |
|-------|-----|
| Muted video-only stream | Muting injects a silent AAC track automatically; ensure you're on a current version ([ADR-0011](adr/0011-silent-audio-when-muted.md)) |
| RTSP unreachable | Verify the camera URL and that the host can reach it; check `[ffmpeg]` debug lines |
| Wrong RTSP credentials | Special characters are auto-encoded at install; re-run `--install` if you changed the password |
| Stream key mismatch | The stream ID is resolved from the key at runtime; re-run `--install` to repair |

## "Playback on other websites has been disabled" (embed blocked)

Both the broadcast-level and video-level `embeddable` flags must be true; mobile enforces the video flag strictly. Ensure `youtube.embeddable = true` and re-`--start`. See [ADR-0010](adr/0010-embeddable-dual-flag.md).

## OAuth fails or authorizes the wrong account

- The flow always shows the account chooser — pick the correct account.
- If the refresh token was revoked, the browser flow reopens automatically.
- To switch accounts permanently, use `--reinstall`.

## Broadcast title shows tomorrow's date

Fixed: the title is now stamped after the broadcast goes live, never on the previous day's archive. Update to the latest release. See [ADR-0019](adr/0019-title-update-after-ensure-live.md).

## Rollback keeps getting undone by auto-update

Expected to be prevented: `--roll-back` sets `update.skippedVersion`. If auto-update still re-installs, verify the marker:

```bash
python3 stream.py --set-property update.skippedVersion v1.0.20
```

See [ADR-0018](adr/0018-skipped-version-marker.md).

## pip install fails (externally-managed environment)

PEP 668 systems are handled via a `--user --break-system-packages` fallback. If it still fails, run inside a virtualenv or pre-install the [dependencies](../REQUIREMENTS.md#python-packages).

## Stream didn't resume after a reboot

- `--recover` only acts inside the `cron.start`/`cron.stop` window.
- Confirm the `@reboot` entry exists: `crontab -l | grep bcfreeflight_stream`.
- Re-run `--install` to repair cron entries.

## Multiple terminal windows / no window opens

- Only the start cron opens a window; it closes when stop fires.
- If none opens, the detected `terminal` may be wrong — set it: `--set-property terminal xterm`.
- Cron start lines need `DISPLAY=:0`; this is set automatically.

## Logs missing or growing

- Logs are in `logDir` (default `logs/`), one file per day.
- Old logs are pruned on `--start` per `logRetentionDays`.
- At the default `info` level, ffmpeg noise is hidden — use `--log-level debug` to see it.
