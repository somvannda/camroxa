# Admin-managed Suno blocklist term registry

**Date:** 2026-07-18  
**Status:** deployed

## Summary

Added a DB-backed Suno lyrics blocklist that admins manage from Settings. Runtime sanitize/scan paths merge static defaults, enabled DB terms, and per-song learned terms. Desktop Music workspace fetches the enabled blocklist on load for consistent local highlighting and auto-fix.

## Product impact

- **Before:** Only hardcoded `lowlight → afterglow` plus per-song learned terms from Suno failures.
- **After:** Admins can add/edit/enable block and warn terms with optional replacements. Server submit/sanitize and desktop scan use the same enabled registry; static defaults remain offline fallback.

## Technical impact

- New table `suno_blocklist_terms` with migration `066_suno_blocklist_terms`.
- Admin CRUD at `/api/v1/admin/suno-blocklist` (+ `/promote` for learned terms).
- Read-only runtime config at `/api/v1/generation/suno-blocklist`.
- `SunoBlocklistService.get_runtime_config()` cached (60s TTL) and wired into batch sanitize, generation submit, and lyrics Suno check.
- Admin portal Settings tab **Suno Blocklist**; desktop workspace fetch on load.

## Files touched

- **Backend:** `platform_api/migrations/versions/066_suno_blocklist_terms.py`, `platform_api/repositories/suno_blocklist_repo.py`, `platform_api/services/suno_blocklist_service.py`, `platform_api/services/suno_lyrics_sanitize.py`, `platform_api/routers/suno_blocklist_admin.py`, `platform_api/routers/suno_blocklist.py`, `platform_api/dependencies.py`, `platform_api/main.py`, `platform_api/services/batch_service.py`, `platform_api/services/generation_service.py`, `platform_api/routers/generation.py`
- **Admin:** `admin_portal/src/types/suno-blocklist.ts`, `admin_portal/src/hooks/use-suno-blocklist.ts`, `admin_portal/src/pages/settings/suno-blocklist-section.tsx`, `admin_portal/src/pages/settings/index.tsx`
- **Desktop:** `camxora_python/shared/lib/suno_lyrics_sanitize.py`, `camxora_python/shared/models/platform.py`, `camxora_python/shared/services/platform_api.py`, `camxora_python/shared/workers/data_workers.py`, `camxora_python/features/music/widgets/song_editor_card.py`, `camxora_python/features/music/views/music_view.py`
- **Tests:** `platform_api/tests/test_suno_blocklist_service.py`, `platform_api/tests/test_suno_blocklist_admin.py`, `platform_api/tests/test_suno_lyrics_sanitize.py`

## Migration / deploy

1. Run Alembic through `066_suno_blocklist_terms`.
2. Deploy platform API + admin portal.
3. Optional: verify seed row `lowlight → afterglow` in admin UI.
4. No new env vars.

## Tests

- `cd platform_api; python -m pytest tests/test_suno_blocklist*.py tests/test_suno_lyrics_sanitize.py -q`
- `cd camxora_python; python -m pytest tests/test_suno_lyrics_sanitize.py -q`

## Follow-ups

- Phase 4 fuzzy detection not included.
- Consider admin UI action to promote learned terms directly from failure review screens.
