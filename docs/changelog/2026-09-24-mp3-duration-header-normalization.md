# MP3 duration-header normalization (Xing/Info)

**Date:** 2026-09-24
**Surface:** platform_api
**Related:** PR #155

## Summary

Suno's CDN MP3s omit the Xing/Info header, so ffprobe and most players estimate
the duration from the file size and over-report by several seconds. An exported
MP4 that carries the real audio length therefore looked shorter than the MP3 —
the recurring "export video duration != mp3 duration" reports (edmbass1,
tepchanpanharith). Normalize the header server-side so every download is
correctly labelled, regardless of desktop client version.

## Product impact

- Desktop users downloading archived tracks from B2 get an MP3 whose reported
  duration matches the exported video.
- Music-web owner MP3 downloads and admin support downloads are normalized too.
- No re-encoding: the audio bytes are unchanged (lossless remux), so quality and
  file size are effectively identical.

## Technical impact

- New `platform_api/services/mp3_duration_header.py`:
  `ensure_mp3_duration_header[_async]()` re-muxes header-less MPEG audio with
  `ffmpeg -c copy -write_xing 1`. No-ops for Opus/M4A/WAV/already-headed files
  and returns the original bytes on any failure (best-effort).
- Normalized before all three B2 MP3 uploads in
  `streaming_upload_service.py` (album, web-music, retry paths).
- Normalized when serving web (`web_music_service.download_mp3`) and admin
  (`admin_user_web_music.download_user_web_music_clip`) MP3 downloads.
- ffmpeg is resolved via `CAMXORA_FFMPEG_PATH` or `PATH`; already present on the
  API host (used by `hls_packager`).

## Files touched

- `platform_api/services/mp3_duration_header.py` (new)
- `platform_api/services/streaming_upload_service.py`
- `platform_api/services/web_music_service.py`
- `platform_api/routers/admin_user_web_music.py`
- `platform_api/tests/test_mp3_duration_header.py` (new)
- `scripts/deploy/backfill_mp3_duration_headers_production.py` (new)
- `scripts/deploy/deploy_cdn_cache_bust_production.py` (new)

## Migration/deploy

No DB migration. A file-scoped production hotfix ships the four changed files
(no full tree sync):

```
python scripts/deploy/deploy_mp3_duration_header_production.py            # dry-run
python scripts/deploy/deploy_mp3_duration_header_production.py --apply
```

Then run the backfill (background job; poll with `--status`):

```
python scripts/deploy/backfill_mp3_duration_headers_production.py --apply
python scripts/deploy/backfill_mp3_duration_headers_production.py --status
python scripts/deploy/backfill_mp3_duration_headers_production.py --kill
```

The sweep uses ranged 8 KiB reads to find header-less MP3s, so only affected
objects are downloaded and re-uploaded. Non-MPEG objects stored under `.mp3`
keys (Opus-in-MP4) are left untouched. Production run (2026-09-24): 13,068 keys
scanned, 11,189 already OK, 982 fixed, 897 non-MPEG, 0 failures.

Cloudflare (`media.camxora.com`) serves objects with a 1-year TTL keyed by URL,
so re-uploaded objects kept serving stale bytes (verified live: ~7% of
re-uploaded keys returned the old header-less file with `cf-cache-status: HIT`).
Rather than a CDN purge, the desktop download paths now append the current
object ETag to the CDN URL (`get_signed_get_url(..., cache_bust=True)` in
`_resolve_pending_b2_urls` and `_resolve_b2_redownload_urls`), so the CDN
fetches fresh content:

```
python scripts/deploy/deploy_cdn_cache_bust_production.py --apply
```

## Tests

- `pytest tests/test_mp3_duration_header.py tests/test_streaming_upload_service.py tests/test_web_music_router.py tests/test_admin_user_web_music.py tests/test_web_music_b2_ingest_retry.py -q` → 32 passed.
- `pytest tests/test_storage_service_cache_bust.py tests/test_batch_download_health.py tests/test_streaming_catalog_playback.py -q` → 18 passed.
- `ruff` clean on new code; `mypy` clean on the new module.

## Follow-ups

- Files already saved on a user's disk can't be changed server-side; the desktop
  1.4.2 client backfills those on sync. Users on ≤1.4.1 who never upgrade still
  need the 1.4.2 rollout for their existing files.
- Consider folding header normalization into the periodic B2 backfill sweep so
  any future header-less object self-heals.
