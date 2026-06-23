# Streaming & ffmpeg

## ffmpeg command

Built by `build_ffmpeg_command` from `[stream]` config:

```
ffmpeg -re -rtsp_transport tcp -i <rtspUrl> [silent-audio-input] [maps] \
       -vcodec <videoCodec> [audio-flags] -f flv <rtmpUrl>/<streamKey>
```

- `-re` — read input at native frame rate (real-time pacing)
- `-rtsp_transport tcp` — TCP transport, more reliable than UDP over WAN
- `-f flv` — FLV container required by YouTube RTMP ingest
- Output is `<rtmpUrl>/<streamKey>`; the key is redacted in logs as `<REDACTED>`

Default codecs are `copy` (passthrough), so the camera's existing H.264/AAC streams are forwarded without re-encoding — minimal CPU.

## Mute behavior

When `mute = true`, the script does **not** drop audio (`-an`). YouTube's live ingest rejects video-only streams — the stream status stays `inactive` forever. Instead it injects a silent AAC track:

```
-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 \
-map 0:v:0 -map 1:a:0 -c:a aac -b:a 128k -shortest
```

`-shortest` makes ffmpeg exit when the RTSP input ends rather than running forever against the infinite silent source. See [ADR-0011](adr/0011-silent-audio-when-muted.md).

## RTSP credential encoding

Camera passwords often contain URI-reserved characters (`$ @ / # ? :`) that break ffmpeg's URL parser. `encode_rtsp_credentials` percent-encodes the userinfo portion on install. It is **idempotent** — already-encoded input is decoded then re-encoded, so running it twice is safe (PR #13).

## Output relay

`relay_ffmpeg_output` starts a **daemon thread immediately** to pump ffmpeg stdout/stderr to the logger. Without it, ffmpeg's stderr fills the ~64 KB pipe buffer and ffmpeg blocks — hiding the very errors needed to diagnose why a stream never goes active. ffmpeg lines containing `warning` are logged at `warn`; the rest at `debug`.

## Retry loop

`_run_stream_loop` runs indefinitely until stopped:

```
attempt = 0
loop:
   connect (alternate RTMP by attempt parity)
   if stop requested: break
   stream until ffmpeg exits
   on error: log + clean up ffmpeg
   if stop requested: break
   wait retryDelaySecs; if stop requested during wait: break
   attempt += 1
```

- **No max retry count.** Runs until `--stop` or a signal.
- **RTMP alternation:** even attempts use `streamURL`, odd attempts use `backupStreamUrl` (if configured). See `select_rtmp_url`.
- **Stop checks** happen before every retry and during the delay, via the [stop sentinel](process-management.md#stop-sentinel).
- On retry the script reconnects to the **same** broadcast; it re-authenticates if needed.

## Stream activation

After launching ffmpeg, the script polls `liveStreams.list` until `streamStatus == active` (up to ~10 min) before transitioning the broadcast live. If the stream ID can't be resolved from the key, it falls back to a fixed 15 s wait.
