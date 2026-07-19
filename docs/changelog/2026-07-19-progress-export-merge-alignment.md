# Progress page export/merge alignment + status vocabulary

**Date:** 2026-07-19  
**Status:** implemented (desktop rebuild required)

## Summary

Fixed Progress page misalignment where Stage, Progress %, Export, and Merge could disagree — especially when a long merge (`MERGED_*.mp4`) existed while reel exports were still at 0/N or when stale export workspace state kept the row on Export. Standardized pipeline status terms to **Not started**, **Pending**, **In Progress**, and **Completed**, and renamed the stage label **Converter → Export** (Merge for merger).

## Product impact

- **Before:** A beattok long-only run could show Stage **Converter** at 50%, Export **L 3/3 · R 0/3**, and Merge **Long merged · Reel pending** even when `MERGED_PRIMARY_*.mp4` was already on disk.
- **After:** Local filesystem truth drives stage promotion (merge on disk wins over stale export-running), long-only runs ignore reel branch for percent/completion, and all four columns use the same vocabulary.

## Technical impact

- `shared/lib/video_runtime_inspection.py`: merge detection priority, reel-aware percent/completion, standardized status strings, `run_includes_reel()` moved here.
- `shared/lib/progress_presentation.py`: Export/Merge stage labels and compact column formatters.
- `shared/lib/progress_local_overlay.py`: Export stage promotion + pending copy.
- `features/progress/views/progress_view.py`: stage filter aliases.
- `features/workflow/lib/workflow_steps.py`: imports shared reel helper + Export/Merge stage normalization.

## Files touched

- `camxora_python/shared/lib/video_runtime_inspection.py`
- `camxora_python/shared/lib/progress_presentation.py`
- `camxora_python/shared/lib/progress_local_overlay.py`
- `camxora_python/features/progress/views/progress_view.py`
- `camxora_python/features/progress/widgets/operational_rows_card.py`
- `camxora_python/features/progress/widgets/stats_row.py`
- `camxora_python/features/workflow/lib/workflow_steps.py`
- `camxora_python/tests/test_video_runtime_inspection.py`
- `camxora_python/tests/test_progress_presentation.py`
- `camxora_python/tests/test_progress_local_overlay.py`
- `camxora_python/tests/test_workflow_steps.py`

## Migration / deploy

- Rebuild/restart the desktop app only. No API or DB migration.

## Tests

- `python -m pytest tests/test_video_runtime_inspection.py tests/test_progress_presentation.py tests/test_progress_local_overlay.py tests/test_workflow_steps.py tests/test_badge_pills.py tests/test_progress_view.py tests/test_desktop_video_automation.py` — 56 passed.

## Follow-ups

- Port the same merge-priority fix to `camxora/src/renderer/src/shared/lib/videoRuntimeInspection.ts` for Electron parity.
- Platform API `build_video_run_presentation` still marks partial merge as `Completed`; align if API-driven Progress rows are shown elsewhere.
