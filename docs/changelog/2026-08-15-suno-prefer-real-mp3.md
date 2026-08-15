# Prefer Suno `{id}.mp3` over `{id}.m4a`

**Date:** 2026-08-15  
**Surfaces:** `platform_api`, `camxora_python` (desktop)  
**Branch:** `bugfix/opus-mp4-export-queue`

## Summary

Suno’s finished-clip CDN now publishes **two** files for the same clip id:

- `https://cdn1.suno.ai/{id}.m4a` — `audio/m4a; codecs=opus` (ISO-BMFF)
- `https://cdn1.suno.ai/{id}.mp3` — `audio/mpeg`

Callbacks/polls often persist `source_audio_url` as **`.m4a`**. Camxora always
saves to `{n}. Title_OK.mp3` with no magic-byte check, so the studio library
got real Opus audio under an MP3 name (Windows still plays it; mpg123/librosa
do not).

This was **not** “downloaded too early / stream URL.” Both formats were already
live; we picked the wrong URL.

## Product impact

- New downloads wait for / fetch the **MPEG** sibling. Speed is not the goal.
- If `{id}.mp3` is missing or still not MPEG, the file is **not** saved; the
  row stays pending and retries on the next poll.
- “Download missing MP3s” treats Opus-in-MP4 `.mp3` names as missing and
  replaces them.
- Existing on-disk Opus files still export via ffmpeg (see the export-hang
  changelog) until they are re-downloaded.

## Technical impact

- `prefer_suno_mpeg_cdn_url` / `coerce_suno_download_url` rewrite Suno CDN
  `.m4a`/`.mp4`/`.webm`/`.opus`/`.aac` to `.mp3`.
- Clip extract + pending list + redownload plan + streaming download use that.
- Desktop `_download_file` GETs the rewritten URL and sniffs ID3/MPEG vs `ftyp`.
- Server `download_suno_mp3_bytes` rejects non-MPEG so Backblaze does not
  archive Opus labeled as `audio/mpeg`.

## Files touched

- `platform_api/clients/suno_client.py`
- `platform_api/services/suno_audio_resolver.py`
- `camxora_python/shared/lib/suno_mp3_download.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/shared/lib/missing_mp3.py`
- Tests under `platform_api/tests/` and `camxora_python/tests/`
- Root `CHANGELOG.md`, `platform_api/CHANGELOG.md`

## Migration / deploy

- Sandbox API first (pending-download URLs rewrite even for old `.m4a` rows).
- Desktop installer needed for sniff / refuse-to-save. Ships as rebuilt
  **1.3.0**. After API rewrite, even an old 1.3.0 client gets MPEG URLs from
  pending-download; sniff still needs the new build.
- Production API on explicit ship request.
- Four unique library tracks already saved as Opus can be replaced with
  Progress **Download missing MP3s** (or delete the file and let sync retry).
  Clip ids: Chase `441cb4bf-…` / `227f6315-…`, Sunline `d9821ce4-…` /
  `eac0c941-…`.

## Tests

- `pytest platform_api/tests/test_suno_audio_resolver.py camxora_python/tests/test_suno_mp3_download.py camxora_python/tests/test_music_download_coordinator.py camxora_python/tests/test_missing_mp3.py -q`
