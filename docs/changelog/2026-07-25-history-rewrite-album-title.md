# History rewrite album 1 / album 2 / title

**Date:** 2026-07-25  
**Status:** implemented (API deploy + desktop restart)

## Summary

History right-click can regenerate **Album 1** (Primary), **Album 2** (Secondary), or a song **Title** at any time — including after Suno success — without rewriting lyrics or resetting song status.

## Product impact

**Before**
- Bad titles/albums required full draft retry (failed songs only) or manual editing.
- Successful songs had no rewrite path for metadata.

**After**
- Right-click History → **Rewrite album 1** / **Rewrite album 2** / **Rewrite title**.
- Each action bills one album or title draft slot and runs the garbage-name validator.
- Lyrics and Suno status stay unchanged; History refreshes with the new name.
- **Rewrite title** on `suno_failed` / `draft_ready` automatically queues **Retry Suno** with the new title.

## Technical impact

- `POST /batches/{batch_id}/rewrite-album` (`role=ok|alt`)
- `POST /batches/{batch_id}/songs/{song_id}/rewrite-title`
- Repo helpers update title/album without forcing `draft_ready`
- Desktop workers + History context menu

## Files touched

- `platform_api/services/batch_service.py`
- `platform_api/routers/batch.py`
- `platform_api/models/schemas.py`
- `platform_api/repositories/batch_repo.py`
- `platform_api/middleware/rate_limit.py`
- `platform_api/tests/test_metadata_rewrite_service.py`
- `camxora_python/features/music/widgets/history_card.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/shared/services/platform_api.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/shared/models/platform.py`
- `camxora_python/tests/test_history_metadata_rewrite.py`
- `platform_api/CHANGELOG.md`
- `CHANGELOG.md`
- `docs/changelog/2026-07-25-history-rewrite-album-title.md`

## Migration / deploy

1. Deploy `platform_api` / restart `camxora-api`.
2. Restart desktop app.

## Tests

- `pytest platform_api/tests/test_metadata_rewrite_service.py camxora_python/tests/test_history_metadata_rewrite.py -q`

## Follow-ups

- Optional: push rewritten album/title into streaming catalog metadata when tracks already uploaded.
- Optional: Progress row context menu parity.
