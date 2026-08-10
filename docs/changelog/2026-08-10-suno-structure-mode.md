# Suno Structure mode

**Date:** 2026-08-10  
**Surfaces:** `platform_api`, `camxora_python`

## Summary

Music Automation Structure dropdown now includes **Suno Structure** alongside **AI Structure** and Music Structure templates. With admin lyric routing set to Suno, all three remain selectable: templates still hint/remap sections, AI Structure keeps genre soft-seeds, and Suno Structure asks Suno for a native free layout with no preferred seed.

## Product impact

- New Structure option: **Suno Structure** (`structure_mode=suno`)
- Shuffle stays disabled for AI Structure and Suno Structure
- Shuffle hardening: settings restore cannot re-check Shuffle under free modes; selecting AI/Suno clears persisted `shuffleStructure`; batch create ignores saved shuffle settings for free modes
- History labels show `Suno Structure` for `structure_mode=suno`
- Structure control is **not** hidden when lyric provider is Suno

## Technical impact

- `STRUCTURE_MODE_SUNO` + `is_free_structure_mode()` in generation service
- Free-structure validation shared by `ai_free` and `suno`; preferred layout seeds only for `ai_free`
- Suno lyrics prompt for `suno` always uses `use your own section headers`
- Desktop `AutomationCard` sentinel `__suno_structure__`; batch/draft payloads pass `structure_mode`

## Remix / lyrics API note (docs only)

Dedicated lyrics remain `POST /api/v1/lyrics`. There is no separate “remix lyrics” endpoint; remix/cover music can return clip `prompt` lyrics in non-custom mode, and timestamped lyrics use `get-timestamped-lyrics` after music generation.

## Files touched

- `platform_api/services/generation_service.py`
- `platform_api/services/batch_service.py`
- `platform_api/routers/generation.py`
- `platform_api/routers/music_history.py`
- `platform_api/models/schemas.py`
- `platform_api/tests/test_suno_lyrics_client.py`
- `platform_api/tests/test_batch_service.py`
- `camxora_python/features/music/widgets/automation_card.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/shared/models/platform.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/tests/test_automation_card.py`
