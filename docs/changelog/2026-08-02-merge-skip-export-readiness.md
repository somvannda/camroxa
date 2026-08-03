# Continue merge: do not re-gate on export BG/template

**Date:** 2026-08-02  
**Status:** implemented  
**Branch:** `fix/merge-skip-export-readiness`

## Problem

Continue → merge showed “missing MP4s, image assets, or a catalog template” even when the run folder had `_Alt.mp3`s and images. Progress already treated merge as “valid MP4s only,” but the video coordinator rebuilt an **export** candidate (requires `background-16x9[-alt]` + catalog template). Folders with names like `background-1-left.jpg` failed that gate. “API recovered — resuming…” often toasted while pause/no-candidate meant nothing started.

## Fix

- Merge action builds a merge-only candidate (run_dir + branch); skips BG/template checks
- Export failures surface the specific readiness reason
- API-recovery toast only claims “resuming” when a candidate actually starts; otherwise explains pause / no ready run

## Files

- `camxora_python/features/video/lib/desktop_video_automation.py`
- `camxora_python/shared/services/video_pipeline_coordinator.py`
- `camxora_python/tests/test_desktop_video_automation.py`
