# Music Moods + draft pipeline (album → title → lyric → Suno)

**Date:** 2026-07-25  
**Status:** implemented (sandbox deployed)

## Summary

Adds a first-class **Mood** catalog (admin + user CRUD, Music dropdown + shuffle) and rewires draft generation so album/title/lyric follow mood + pools + structure, while song **description stays Suno-only**. Seeds 22 system moods covering EDM energy and common feelings.

## Product impact

**Before**
- Music page: Description + Structure only; lyrics often echoed neon/description tropes.
- Draft order mixed title before album; lyric prompts included production description.

**After**
- Music page: Description + Structure + **Mood** (each with shuffle where applicable).
- Flow: album (pool + mood) → title (pool + mood) → lyric (polished title + opening + structure/AI structure + mood, **no description**) → Suno (lyrics + description style, **no mood**).
- Settings My Prompts and Admin Prompts include Moods tabs; 22 seeded system moods.

## Technical impact

- Migration `069_music_moods`: table, `songs.mood_id`, seed moods.
- Prompt service/repo/router moods CRUD; history `mood_name`.
- `generation_service` mood writing context; temperature capped; album-first split draft.
- Desktop automation + settings + history; admin Moods tab.

## Files touched

- `platform_api/migrations/versions/069_music_moods.py`
- `platform_api/services/{generation_service,batch_service,prompt_service}.py`
- `platform_api/repositories/{prompt_repo,batch_repo}.py`
- `platform_api/routers/{prompts,batch,generation,music_history}.py`
- `admin_portal/src/pages/prompts/index.tsx`, hooks, types
- `camxora_python/features/music/**`, `features/settings/**`, shared models/API/workers

## Migration / deploy

1. Deploy `platform_api` to sandbox.
2. `alembic upgrade head` (069).
3. Restart API.
4. Restart desktop app; rebuild admin portal if serving separately.

## Tests

- Smoke import mood helpers.
- Update `test_suno_lyrics_client` for new suno lyric prompt shape.
- Run focused generation/prompt tests after deploy prep.

## Follow-ups

- Optional: require mood_id on batch create (currently optional if catalog empty).
- Optional: harden lyric corruption gates further (separate from mood).
