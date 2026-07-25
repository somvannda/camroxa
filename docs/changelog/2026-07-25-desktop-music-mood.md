# Desktop Music Mood wiring

**Date:** 2026-07-25  
**Status:** implemented

## Summary

Wired Music Mood into the Camxora desktop app (`camxora_python`) to match the existing Description/Structure prompt flow. Mood options load from the workspace API, appear on the Music automation card with Shuffle, persist as `defaultMoodId` / `shuffleMood`, and show in History. Settings gains a Moods library tab for Camxora + user-owned moods.

## Product impact

- **Before:** Desktop could not select or send moods on batch create; History had no mood column; Settings had no Moods library.
- **After:** Users pick Mood (+ Shuffle) on Music, defaults save like Structure, History shows Mood per song, and Settings → Moods manages custom moods.

## Technical impact

- `BatchCreateRequest` / `MusicHistorySong` gain `mood_id`, `shuffle_mood`, `mood_name`.
- Platform client: workspace moods + `/prompts/me/moods` CRUD.
- `MusicWorkspacePayload` / `SettingsWorkspacePayload` / `WorkspaceCache` include mood options and my-mood items.
- Automation card: third dropdown + `mood_shuffle_changed`.
- Settings prompt helpers generalized to `kind` (`description` | `structure` | `mood`).

## Files touched

- `camxora_python/shared/models/platform.py`
- `camxora_python/shared/services/platform_api.py`
- `camxora_python/shared/services/workspace_cache.py`
- `camxora_python/shared/lib/music_settings.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/shared/workers/shell_warmup_worker.py`
- `camxora_python/features/music/widgets/automation_card.py`
- `camxora_python/features/music/widgets/history_card.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/features/music/services/music_local_store.py`
- `camxora_python/features/settings/views/settings_view.py`
- `camxora_python/features/image/views/image_view.py` (snapshot_core unpack)
- `camxora_python/features/video/views/video_view.py` (snapshot_core unpack)
- `camxora_python/tests/test_music_*.py`, `test_settings_view.py`, `test_workspace_cache.py`
- `CHANGELOG.md` (desktop)

## Migration / deploy

- Requires platform API mood endpoints already deployed (`/prompts/moods/workspace`, `/prompts/me/moods`, batch + history mood fields).
- No desktop DB migration. Settings keys `defaultMoodId` and `shuffleMood` are written into user settings JSON.

## Tests

- `pytest tests/test_music_settings.py tests/test_music_local_store.py tests/test_music_view.py tests/test_settings_view.py tests/test_workspace_cache.py`

## Follow-ups

- Draft generation still does not send `mood_id` (API draft request has no mood field yet).
- Optional: Descriptions tab “Default mood” companion combo (mirrors Default structure).
- Empty mood catalog: dropdown stays empty; batch `mood_id` is omitted (`None`).
