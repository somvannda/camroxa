# Restore admin Pipeline Ops sidebar + board API

**Date:** 2026-08-02  
**Status:** implemented  
**Branch:** `fix/admin-restore-pipeline-ops`

## Problem

Admin **Pipeline Ops** (`/pipeline`) — the live multi-user board for monitoring who is running music → image → export → YouTube/streaming — disappeared from the left sidebar after later admin hotfixes. The page sources still existed on the VPS, but:

1. Sidebar / `App.tsx` no longer linked `/pipeline`
2. `admin_pipeline` router was not registered in `main.py` (board API 404)
3. Orphaned helpers (`_retry_song_*_with_logging`, `aggregate_streaming_groups`) no longer matched the job-queue worker path

## Fix

- Restore admin UI: route, sidebar **Pipeline Ops**, top-bar title
- Re-register `platform_api.routers.admin_pipeline` + wire dependencies
- Adapt board service to current `_build_row` (inline streaming aggregate)
- Admin retries enqueue via `job_queue` (draft / Suno / images / YouTube)
- Platform-paid waive retries return 501 until dual-control waive is rewired

## Follow-up (same day): board stage/status were wrong

Chips (music / image / streaming) were mostly right, but **stage**, **status**, and **stuck** counters were not.

**Cause:** the board reused desktop progress logic that requires local filesystem paths (`E:\SUNO\...`). The API host cannot see those paths, so `merge_channel_asset_paths()` dropped them, `long_ready` never flipped, and rows stayed at **Image / Rendering** even when image jobs and streaming were done.

**Correction:**
- Trust DB-persisted asset paths without `Path.is_file` on the API host
- Treat BG/TH image-job success as image-ready when paths are empty
- Promote Image → Converter / Streaming / Done from stream + image job state

## Surfaces

| Surface | Change |
|---------|--------|
| admin_portal | `/pipeline` page + nav |
| platform_api | board + retry endpoints live again; stage promotion without desktop FS |
