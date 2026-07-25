# Lyric rewrite aligned with mood draft flow

**Date:** 2026-07-25  
**Status:** implemented (sandbox API deploy + desktop restart)

## Summary

Manual rewrite, Recover failed rewrite→Suno, and server auto-rewrite after Suno content-policy rejects still fed **song description** into the lyric LLM (or only title). That fought the album→title→lyric mood pipeline. Rewrite now uses the same context as draft lyrics: **mood + title + structure**, never production description. Description stays Suno style-only.

## Product impact

**Before**
- Rewrite could echo genre/production tropes from Description.
- Auto-rewrite after Suno reject often ignored the song’s Mood/Structure catalog entries.

**After**
- Rewrite prompts follow Mood (+ title + structure headers).
- When `song_id`/`batch_id` are present, API resolves mood/structure content from the song’s catalog IDs.
- Desktop rewrite/recovery send `mood_id` / `structure_id` instead of description text.

## Technical impact

- `build_lyric_rewrite_*` helpers; `polish_lyrics_text` ignores `description`.
- `BatchService.resolve_lyric_rewrite_context` / `lyric_rewrite_context_for_user_song`.
- `POST /generation/polish-lyrics` accepts `mood`, `mood_id`, `structure_id`; resolves from song when linked.
- Desktop `LyricsPolishRequest` + recovery targets updated.

## Files touched

- `platform_api/services/generation_service.py`
- `platform_api/services/batch_service.py`
- `platform_api/routers/generation.py`
- `platform_api/tests/test_generation_service.py`
- `platform_api/tests/test_generation_router.py`
- `camxora_python/shared/models/platform.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/features/music/lib/pipeline_recovery.py`
- `platform_api/CHANGELOG.md`
- `CHANGELOG.md`
- `docs/changelog/2026-07-25-lyric-rewrite-mood-align.md`

## Migration / deploy

1. Deploy `platform_api` to sandbox.
2. Restart desktop app.

## Tests

- `pytest platform_api/tests/test_generation_service.py::TestTwoStepLyricPrompts::test_lyric_rewrite_prompt_uses_mood_not_description platform_api/tests/test_generation_router.py::TestPolishLyrics -q`
- `pytest camxora_python/tests/test_pipeline_recovery.py -q`

## Follow-ups

- Optional: surface mood name in rewrite status toast for support clarity.
