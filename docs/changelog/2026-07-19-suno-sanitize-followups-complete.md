# Suno sanitize follow-ups complete

**Date:** 2026-07-19  
**Status:** implemented (sandbox pending deploy)

## Summary

Completed remaining Suno lyrics sanitization follow-ups: persisted sanitize metadata on songs, fixed stuck `suno_pending` reconciliation, one-pass auto-fix after AI rewrite, callback-path learned-term promotion with a single auto-retry, admin failure metrics + promote UI, desktop learned-term cache and online scan merge, and phase-4-lite channel-scoped blocklist filtering with post-sanitize submit gate.

## Product impact

- **Before:** Sanitize replacements were inferred heuristically on desktop; songs could stay `suno_pending` after failed tasks; sensitive Suno failures required manual retry; admin had no failure breakdown or quick promote form.
- **After:** History exposes stored sanitize metadata; reconcile fixes stuck pending rows; polish/rewrite and callback paths auto-sanitize once more; one automatic resubmit per song on producer-tag/sensitive failures; admin sees 30-day failure buckets and can promote learned terms; desktop caches learned terms and merges online `/lyrics-suno-check` hits when online.

## Technical impact

- **DB:** Migration `067_song_suno_sanitize_metadata` adds `songs.suno_last_sanitize`, `songs.suno_auto_retry_count`, and `suno_blocklist_terms.channel_profile_id`.
- **API:** Batch sanitize persists metadata; music history returns `suno_last_sanitize`; `GET /admin/suno-blocklist/failure-metrics`; reconcile includes stuck pending fix; callback promotes block terms and may auto-retry once.
- **Desktop:** `learnedSunoTerms` in music settings; history shows stored replacements; debounced online Suno check merged with local scan.
- **Admin:** Failure metrics cards + promote learned term quick form (supports `?term=` prefill).

## Files touched

- **Backend:** `platform_api/migrations/versions/067_song_suno_sanitize_metadata.py`, `platform_api/repositories/batch_repo.py`, `platform_api/repositories/suno_blocklist_repo.py`, `platform_api/services/batch_service.py`, `platform_api/services/generation_service.py`, `platform_api/services/suno_blocklist_service.py`, `platform_api/services/suno_lyrics_sanitize.py`, `platform_api/routers/music_history.py`, `platform_api/routers/suno_blocklist_admin.py`, `platform_api/models/domain.py`, `platform_api/models/schemas.py`
- **Admin:** `admin_portal/src/types/suno-blocklist.ts`, `admin_portal/src/hooks/use-suno-blocklist.ts`, `admin_portal/src/pages/settings/suno-blocklist-section.tsx`
- **Desktop:** `camxora_python/shared/lib/music_settings.py`, `camxora_python/shared/lib/suno_lyrics_sanitize.py`, `camxora_python/shared/models/platform.py`, `camxora_python/shared/services/platform_api.py`, `camxora_python/features/music/views/music_view.py`, `camxora_python/features/music/widgets/song_editor_card.py`
- **Tests:** `platform_api/tests/test_suno_sanitize_followups.py`, `platform_api/tests/test_batch_service.py`
- **Docs:** `docs/changelog/2026-07-18-suno-blocklist-registry.md`, this file

## Migration / deploy

1. Run Alembic through `067_song_suno_sanitize_metadata`.
2. Deploy platform API + admin portal + desktop build.
3. No new env vars.

## Tests

- `cd platform_api; python -m pytest tests/test_suno_sanitize_followups.py tests/test_batch_service.py::test_sanitize_suno_payload_uses_learned_terms_and_persists tests/test_suno_blocklist_admin.py tests/test_suno_lyrics_sanitize.py -q`

## Follow-ups

- Channel-specific blocklist terms can be seeded per profile in admin UI (column exists; admin create form does not expose channel picker yet).
- Fuzzy artist-name warn pattern is heuristic-only; monitor false positives before promoting to block.
