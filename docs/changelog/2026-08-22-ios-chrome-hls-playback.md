# iOS Chrome → HLS native video (2026-08-22)

## Problem
Safari iOS lock screen fixed via AES-128 HLS + in-DOM `<video>`. iOS Chrome stayed on Web Audio + silent hold — lock screen never synced with playback (same symptom Safari had).

## Fix (CriOS only — Safari path unchanged)
- Route **iOS Chrome to the same HLS lane** as Safari (`shouldUseIosHlsPlayback()`).
- Render **in-DOM `<video>`** for CriOS (`shouldUseIosNativeVideoElement()` includes `isIosChrome()`).
- **`primeIosChromeVideoGesture()`** — start silent hold on `<video>` synchronously on tap so `play()` still works after async license session (avoids historical `NotAllowedError`).
- Web Audio remains **fallback only** when `hls_url` is missing.

Traces: `play_path path=hls_aes128 crios=1`, `play_start ... crios=1`.

## Deploy
```bash
python scripts/deploy/hotfix_sandbox_ios_hls_now_playing.py
```
