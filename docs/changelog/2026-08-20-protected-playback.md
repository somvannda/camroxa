# Protected playback for music_web

**Date:** 2026-08-20  
**Branch:** `feature/music-web-protected-playback`

## Summary

Camxora Music now encrypts ingested audio at rest (CXO1) and streams a chunked AES-256-GCM package (CXA1) through a License API. Confirmed users can play public catalog, public playlists, and their own Create tracks. Downloads are owner-only, paid, watermarked, and audited. The browser never receives a Suno or signed B2 MP3 URL.

## Product impact

- Unconfirmed accounts cannot play or download.
- Free confirmed users can listen (public + own). They cannot download anyone’s files.
- Paid users (active web sub or desktop license) can download **their own** MP3/WAV/LRC/SRT. Expired paid still listen, cannot download.
- Catalog and other people’s tracks are play-only. Saving a segment without decrypt is not a playable MP3.
- Create copy: download MP3s means **your songs**, not the catalog.

## Technical impact

- Alembic `107_protected_playback`: `content_keys`, `playback_devices`, `content_license_sessions`, `playback_events`, `export_events`, `audio_watermarks`, `audio_package_jobs`, packaged storage columns.
- License routes under `/api/v1/web-music/licenses/` (geo-gated with other web-music paths).
- Ingest packages after B2 upload and nulls `audio_url_*` for web-music. Backfill: `POST /web-music/licenses/admin/backfill`.
- music_web player uses Web Crypto AES-GCM + MSE when `package_status=ready`; unpackaged rows still use the clamped B2 proxy.
- Admin decrypts encrypted originals for user-song play/download; Playback Audit page lists play/export events.
- Nginx Range + `proxy_buffering off` for `/api/v1/web-music/licenses/`.
- Secret: `PLATFORM_CONTENT_AUDIO_KEK` (falls back to encryption master key / derived local secret). Do not commit real values.
- Production leftover encrypt continues until unpackaged **Camxora Music** (`suno_tasks.source=web_music`) MP3s are gone. Studio catalog and Studio-generated `suno_tasks` are left plaintext. After each Music MP3 is packaged, the original `.mp3` object is overwritten with CXO1 so leftover plaintext is not left on B2.
- Owner download sidecars: WAV and LRC are encrypted at rest with the same content key (CXO1). SRT is not stored — it is derived from decrypted LRC on download. Decrypt happens in the API before the paid owner download.


## Files touched

- `platform_api/services/audio_packager.py`, `audio_package_service.py`, `content_license_service.py`, `forensic_watermark.py`
- `platform_api/routers/web_music_licenses.py`, `web_music.py`, `streaming_public.py`, `streaming_admin.py`, `admin_user_web_music.py`
- `platform_api/services/web_music_service.py`, `streaming_catalog_service.py`, `streaming_upload_service.py`, `batch_service.py`
- `platform_api/migrations/versions/107_protected_playback.py`
- `platform_api/tests/test_protected_playback_theft_vectors.py`
- `music_web/src/lib/camxora-decrypt.ts`, `content-license.ts`, `player-provider.tsx`
- `admin_portal/src/pages/streaming/playback-audit.tsx`
- `scripts/deploy/nginx-camxora-sandbox.conf`, `nginx-camxora-production.conf` (Range + buffering off for License API)
