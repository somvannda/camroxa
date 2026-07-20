# Desktop video pipeline bidirectional sync + export validation

**Date:** 2026-07-19  
**Status:** implemented (local desktop + platform API sync endpoint)

## Summary

Desktop video automation now trusts local run-folder state to start exports while pushing completed local work back to platform progress metadata. Progress shows consolidated export readiness failures and a visible **Start Export** button on pending export rows.

## Product impact

- **Before:** Stale API music/image metadata could block auto-video even when local files existed; completed local work did not update server progress; export prerequisites failed silently.
- **After:** Local disk truth gates export start; a background sync pushes channel asset manifests back to `/progress/sync-local`; selected rows show all blocking issues; pending export rows expose **Start Export** (same path as Rebuild MP4).

## Technical impact

- New API: `POST /progress/sync-local` upserts `batch_channel_assets` from desktop-reported run folders.
- Desktop coordinators: `ProgressLocalSyncCoordinator` (20s poll + hooks after image download / export / merge).
- `local_audio_downloads_ready()` prefers local MP3 count before API counters.
- MP3 naming unified via `mp3_naming.py` (`_OK.mp3` / `_Alt.mp3`).

## Files touched

**platform_api**
- `services/batch_service.py` — `sync_local_progress_from_desktop`
- `routers/progress.py` — sync endpoint + schemas
- `wire_dependencies.py` — batch service wiring

**camxora_python**
- `shared/lib/mp3_naming.py`, `progress_local_sync.py`
- `shared/lib/channel_asset_paths.py`, `progress_local_overlay` consumers
- `features/video/lib/pipeline_inputs.py`, `export_readiness.py`
- `shared/services/progress_local_sync_coordinator.py`, `platform_api.py`
- `shared/workers/data_workers.py` — `ProgressLocalSyncWorker`
- `shared/services/image_output_sync_coordinator.py`, `video_pipeline_coordinator.py`
- `features/video/services/pipeline_automation_service.py`
- `features/progress/views/progress_view.py`, `widgets/operational_rows_card.py`
- `app/application.py`, `app/router.py`
- Tests: `test_mp3_naming.py`, `test_progress_local_sync.py`, `test_export_readiness.py`

## Migration / deploy

1. Deploy `platform_api` with the new `/progress/sync-local` route.
2. Rebuild CAMXORA desktop (`camxora_python`).

## Tests

- `pytest camxora_python/tests/test_mp3_naming.py camxora_python/tests/test_progress_local_sync.py camxora_python/tests/test_export_readiness.py camxora_python/tests/test_pipeline_inputs.py`

## Follow-ups

- Server-side MP4/export counters are still inferred from run-dir scans on progress list (no explicit export completion POST).
- Remote API hosts cannot scan desktop paths unless manifests are synced via this endpoint.
- Billing/auth block reasons depend on live coordinator state at validation time.
