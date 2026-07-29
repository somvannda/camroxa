# Export video when background is ready (don't wait for thumbnail)

**Date:** 2026-07-28  
**Status:** implemented (API deployed sandbox + production; included in consolidated desktop **1.0.1** installer)

## Summary

Video export / auto-export previously waited until **both** background and thumbnail existed (`compute_long_ready` / `compute_reel_ready`). Thumbnails are only used for YouTube upload, not for MP4 render. Export now starts as soon as the branch **background** is ready; thumbnail generation can finish in parallel.

## Product impact

- **Before:** Progress stayed on Image / blocked Start Export until BG and TH were both done.
- **After:** Once the background image is ready (and music is downloaded), the row can move to Export/Converter and video generation can start. Thumbnail may still show as pending in the Images column and is resolved at YouTube upload time.

## Technical impact

- `compute_long_ready` / `compute_reel_ready` = background path only (desktop + API).
- Added `compute_youtube_long_ready` / `compute_youtube_reel_ready` for full upload-asset checks (bg + thumb).
- Export readiness, local pipeline inputs, Progress overlay promotion, and API `image_complete` no longer require thumbnail jobs/files.
- YouTube upload still resolves `thumbnail_*` independently.

## Files touched

### Desktop (`camxora_python`)

- `shared/lib/channel_asset_paths.py`
- `features/video/lib/export_readiness.py`
- `features/video/lib/pipeline_inputs.py`
- `shared/lib/progress_local_overlay.py`
- `features/workflow/lib/workflow_steps.py`
- `tests/test_export_readiness.py`
- `tests/test_pipeline_inputs.py`
- `tests/test_desktop_video_automation.py`
- `tests/test_progress_local_overlay.py`

### Platform API

- `platform_api/services/channel_asset_service.py`
- `platform_api/routers/progress.py`
- `platform_api/tests/test_channel_asset_service.py`
- `platform_api/CHANGELOG.md`

## Migration / deploy

- No DB migration.
- Deploy `platform_api` to sandbox then production.
- Rebuild/reinstall desktop so local overlay + auto-export match (old desktop would rewind Converter→Image without a thumbnail).

## Tests

- `test_compute_long_ready_is_background_only`
- `test_evaluate_video_export_readiness_passes_with_background_only`
- `test_resolve_local_video_pipeline_inputs_ready_with_background_only`
- `test_overlay_promotes_image_stage_when_background_only`
- `test_select_next_auto_video_candidate_with_background_only`

## Follow-ups

- Optional: show an explicit “Thumbnail pending (YouTube)” note on Export rows while TH is still rendering.
