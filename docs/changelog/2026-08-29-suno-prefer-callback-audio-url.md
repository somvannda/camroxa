# Prefer Suno callback `audio_url` over unsigned CDN links

**Date**: 2026-08-29  
**Surfaces**: platform_api  
**Status**: Implemented

## Summary

Suno stopped allowing direct download of unsigned `cdn1.suno.ai/{id}.mp3` links (CloudFront `MissingKey`). Callback/record-info `audioUrl` on `tempfile.aiquickdraw.com` still returns `200 audio/mpeg`. The parser now stores that field first.

## Product impact

- New Suno completions persist a downloadable MP3 URL instead of a CloudFront-blocked CDN link.
- Desktop and server-side B2 ingest can download those files without a new generate charge.
- Existing rows that already stored `cdn1.suno.ai` still need a record-info refresh after this parser ships.

## Technical impact

- `_extract_clip_download_url` prefers `audio_url` / `audioUrl` over `source_audio_url` / `sourceAudioUrl`.
- Callbacks, record-info reconcile, and streaming ingest all use this helper.
- Unsigned CDN rewrite (`prefer_suno_mpeg_cdn_url`) still applies only to `cdn*.suno.ai` hosts; tempfile `.mp3` URLs are stored as-is.

## Files touched

- `platform_api/clients/suno_client.py`
- `platform_api/tests/test_suno_audio_resolver.py`
- `platform_api/CHANGELOG.md`

## Migration/deploy

No schema change. File-scoped hotfix of `suno_client.py`, then restart `camxora-api` and `camxora-worker-suno@*`. After deploy, re-poll SUCCESS tasks that still have unsigned `cdn1.suno.ai` URLs and update `audio_url_ok` / `audio_url_alt`. Tasks whose record-info now returns `data: null` cannot be refreshed.

## Tests

- `platform_api/tests/test_suno_audio_resolver.py`

## Follow-ups

- Production hotfix + URL refresh for already-success studio rows (edmbass1, Rith).
- Image SLAI reference-image 400 is a separate incident.
