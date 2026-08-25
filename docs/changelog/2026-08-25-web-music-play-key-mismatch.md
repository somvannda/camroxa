# Play Ready but Chrome “no supported source”

**Date:** 2026-08-25  
**Branch:** `bugfix/web-music-finishing-b2-retry`  
**Surfaces:** platform_api (music.camxora.com Create play)

## Summary

Create can show **Ready** while play fails. Concurrent packaging (several API workers) wrote a new CXA1 file under a new content key, then a slower worker updated `content_key_id` to an older key. MediaSource decrypts with the DB key and gets `OperationError`. If packaging is still in flight, the HTML fallback hits `/generations/.../stream/...`, which refuses packaged audio as plaintext MP3 — Chrome then logs “no supported source”.

## Product impact

- Point `content_key_id` at the key id embedded in the CXA1 header (Duke + other multi-key web songs).
- `package_plaintext` takes a Postgres advisory lock and skips if that variant is already ready, so workers cannot clobber the key.

## Files touched

- `platform_api/services/audio_package_service.py`
- `platform_api/tests/test_audio_packager.py`
- `platform_api/CHANGELOG.md`

## Migration / deploy

API only. File-scoped `audio_package_service.py` (fill-gaps tree + lock, not
`main`'s v3 modules). Restart `camxora-api` on sandbox then production. Then
repair `content_key_id` from CXA1 headers. Restart logs users out. No migration.

## Tests

- `package_plaintext` returns skipped when package_status is already ready.

## Follow-ups

- One Khmer alt `.cxo` still decrypts with an older key than the CXA1 file.
  Create play uses the package, not the original, so this does not block MSE.
