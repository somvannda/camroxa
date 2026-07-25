# MusicMood CRUD API (mirrors MusicStructure)

**Date:** 2026-07-25  
**Status:** implemented

## Summary

Exposes full MusicMood CRUD on the Platform API, mirroring the existing MusicStructure surface. Admin catalog, user-owned moods, workspace selectors, public name list, usage analytics, and music-history/batch persistence now include mood. Admin portal Prompts page adds a Music Moods tab with the same Camxora/user scope CRUD and usage UX as Structures.

## Product impact

**Before:** Moods existed in DB/domain/repo only; no HTTP API and songs did not round-trip `mood_id` through batch/history reads. Admins had no UI to manage moods.  
**After:** Admins and users can manage moods like structures; history responses show `mood_id` / `mood_name`; new songs persist `mood_id`. Admins manage Camxora moods and inspect user-owned moods/usage from Prompts → Music Moods.

## Technical impact

- `PromptService` protocol + CRUD + `assign_moods_shuffle`
- Admin `/moods`, workspace `/moods/workspace`, user `/me/moods`, public `/moods/public`
- `MusicHistorySongResponse` + history SQL LEFT JOIN `music_moods`
- `batch_repo` song INSERT/SELECT/`_row_to_song` include `mood_id`
- Admin portal: `MusicMood` type, mood React Query hooks, Prompts `MoodsTab`

Related prior work: migration `069_music_moods.py`, domain `MusicMood`, repo mood methods.

## Files touched

### Platform API
- `platform_api/services/prompt_service.py`
- `platform_api/routers/prompts.py`
- `platform_api/models/schemas.py`
- `platform_api/routers/music_history.py`
- `platform_api/repositories/batch_repo.py`
- `platform_api/CHANGELOG.md`

### Admin portal
- `admin_portal/src/types/models.ts`
- `admin_portal/src/hooks/use-prompts.ts`
- `admin_portal/src/pages/prompts/index.tsx`
- `admin_portal/CHANGELOG.md`

### Docs
- `docs/changelog/2026-07-25-music-mood-crud-api.md`

## Migration / deploy

- Ensure migration `069_music_moods` is applied (table + `songs.mood_id` + seeds).
- Redeploy `platform_api` and `admin_portal`. No new env vars.

## Tests

- Python import check of changed modules.
- Admin UI mirrors Structures patterns (manual smoke: open Music Moods tab, create/edit/hide/delete, usage dialog).

## Follow-ups

- Wire `generation_service` / `batch_service.create_batch` to resolve and assign moods (parent).
- Desktop Settings UI for mood selectors (if not already in flight).
