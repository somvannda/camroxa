# Protected playback — start sound on the first chunk

**Date:** 2026-08-21  
**Branch:** `feature/protected-playback-fast-start`  
**Surfaces:** `music_web`, `platform_api`  
**Plan:** [`docs/PROTECTED_PLAYBACK_FAST_START.md`](../PROTECTED_PLAYBACK_FAST_START.md)

## Summary

Packaged Play no longer waits for the whole CXA1 file before making sound. Safari, iOS browsers, and Firefox start Web Audio after decrypted chunk 0. Chrome/Edge keep MSE and prefetch later chunks in parallel. Storage reads the packaged blob once per process (short ciphertext cache), not once per chunk.

Protection is unchanged: no Suno/B2 URLs, no `blob:`/`data:` `audio/mpeg` as `audio.src`, ciphertext only on the wire, PCM stays in RAM.

## Product impact

- First sound should land in about 1–3 seconds on a normal connection instead of 30–90 seconds on Web Audio.
- The player duration is the clip’s known `duration_seconds`. It does not jump as later chunks load.
- Replaying the same track in the same tab (Web Audio) uses the in-memory PCM graph. Hard refresh still re-downloads ciphertext.
- Firefox is on the same progressive Web Audio path as iOS; it is not left on full-file decode.

## Technical impact

- `GET /licenses/segments/{token}?chunk=` serves from an in-process CXA1 cache keyed by `packaged_storage_key` (90s, 8 packages). Still `Cache-Control: private, no-store` on the session URL.
- Player fetches chunk 0, starts playback, then loads later chunks with concurrency 3 and appends in order.
- Web Audio keeps one mpg123 decoder across chunks and schedules PCM buffers instead of concatenating the full MP3.
- Traces include `first_audio_ms=` on `play_ok`.

## Files touched

- `platform_api/services/encrypted_package_cache.py`
- `platform_api/services/audio_packager.py`
- `platform_api/routers/web_music_licenses.py`
- `platform_api/tests/test_encrypted_package_cache.py`
- `music_web/src/lib/mp3-software-decode.ts`
- `music_web/src/lib/mpeg-playback.ts`
- `music_web/src/components/player-provider.tsx`

## Migration / deploy

No Alembic. Sandbox `platform_api` + file-scoped `music_web` hotfix after QA. Production only on explicit request.

## Tests

- `pytest platform_api/tests/test_encrypted_package_cache.py platform_api/tests/test_protected_playback_theft_vectors.py`
- Manual: Windows Chrome + Firefox, iPhone Safari; `first_audio_ms` well under full-file download time.
