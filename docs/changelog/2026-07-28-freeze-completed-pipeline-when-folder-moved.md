# Freeze completed Progress pipelines when run folders are moved

**Date:** 2026-07-28  
**Status:** implemented (desktop + API; sandbox/prod migrate+deploy pending)

## Summary

Moving a finished run folder to another drive made Progress treat the row as incomplete (Music 0/N, re-download/re-export). Local overlays were rewriting API download counters from missing files, and local sync could clear channel-asset readiness. We now preserve API progress when the folder is archived, and persist a conclusive **Completed** flag when desktop export/merge finishes so status survives missing files.

## Product impact

- Before: moved folders → stage fell back to Music / Export not ready → automation could rebuild.
- After: finished pipelines stay completed; Active only hides **Completed** and **Done**; Update time freezes for Completed.
- New stage: **Completed** = desktop pipeline finished (export/merge). **Done** remains YouTube success.

## Technical impact

- `progress_local_overlay`: never rewind completed music; never reopen post-music stages when folder missing.
- `progress_local_sync` + API upsert: never clear asset paths with empty scans; `pipeline_complete` is sticky.
- Migration `075_batch_channel_pipeline_complete` on `batch_channel_assets`.
- Desktop marks `pipeline_complete` after merge success (and single-track export without merge).

## Files touched

- `camxora_python/shared/lib/progress_local_overlay.py`
- `camxora_python/shared/lib/progress_local_sync.py`
- `camxora_python/shared/lib/pipeline_completion.py`
- `camxora_python/shared/models/platform.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/features/progress/**`
- `platform_api/migrations/versions/075_batch_channel_pipeline_complete.py`
- `platform_api/repositories/batch_repo.py`, `services/batch_service.py`, `routers/progress.py`, `models/*`

## Migration / deploy

1. `alembic upgrade head` (local, sandbox, production)
2. Sync `platform_api` sandbox + production
3. Ship desktop build with overlay + mark-complete (v1.0.3 recommended)

## Tests

- Updated `test_progress_local_overlay.py` for archive preservation.

## Follow-ups

- Optional backfill: mark `pipeline_complete` for historical rows that already have YouTube Done or known merge telemetry.
