# API v3 RC — draft request fix + test-suite reconciliation

**Date:** 2026-09-22
**Branch:** `test/api-v3-suite-reconciliation` (fast-forwarded into `release/api-v3-cutover`, `main`, tag `api-v3-cutover-rc1`)
**Surfaces:** platform_api
**Status:** implemented; sandbox rehearsal pending

## Summary

While validating the v3 cutover RC (`release/api-v3-cutover`), the full `platform_api`
test suite was found to be red on `main`: **78 failed tests + 3 collection errors**. Two of
the failures were real code bugs; the rest were stale tests left behind by the v3
credits-only migration. This change fixes the bugs, reconciles the suite, and makes it green.

## Real bugs fixed

- **Draft generation 500** — `routers/generation.py` defines its own `DraftGenerationRequest`
  that omitted `mood_id` and `structure_mode`, but `generate_draft` reads
  `request.structure_mode` unconditionally, so every `POST /generation/draft` raised
  `AttributeError` (500). Added both fields to match `models.schemas.DraftGenerationRequest`.
- **`stream_playback_guard` unimportable** — `services/stream_playback_guard.py` imported
  `PLAY_CHUNK_BYTES` from `services/audio_origin_proxy.py`, where the symbol is
  `_PLAY_CHUNK_BYTES`. The module could not be imported at all. Corrected the name.

## Test reconciliation

- Suite result: **2946 passed, 0 failed, 0 collection errors** (was 78 failed + 3 errors).
- Fixed 3 broken collectors: dropped the removed `platform_api.data.music_genre_catalog`
  import, removed the removed `encrypted_chunk_record` test, corrected the
  `_PLAY_CHUNK_BYTES` import.
- Updated/removed ~68 stale tests across these clusters:
  - Removed model fields (`Plan.monthly_song_quota` → `monthly_song_limit`; clients no longer
    hold a single `_api_key`; lifetime bonus is now `included_wallet_credits`/`plan_purchase`).
  - HTTP harness drift (new `web_subscriptions` lookup, `get_current_user` override for logout,
    Suno callback HMAC secret, register echo, queued web-music generate).
  - v3 credits-only drift (daily quota bank/bypass, quota top-up period math, credit-pack
    micro-credit minimums, profile add-on quote requires `is_public`).
  - Behavior shifts (tz-aware audit/serialized timestamps, root-relative alt run dirs, v3 play
    URLs, tempfile download URLs, legacy-plaintext playability, sample-pack rotation).
  - Removed tests for intentionally deleted behavior (music-credit admin display, genre
    catalog seed, legacy MP3 watermarking, unpackaged-plaintext rejection).

## Migration/deploy

No schema change from this change itself. The RC already carries Alembic `120`/`121`.
Deploy `platform_api` (+ `admin_portal` streaming files) to sandbox, run migrations, restart
API and workers.

## Tests

- `platform_api/tests` — full suite (2946 passed).
