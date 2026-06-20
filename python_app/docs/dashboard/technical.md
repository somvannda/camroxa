# Dashboard (Technical)

## Existing Systems (Codebase-Aware)
- Progress aggregation exists in `MainWindow._collect_progress_rows()` and is already optimized with batched DB reads and directory scan caching: [main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py)
- Credits display exists for Suno via `services/suno_credits.py` and cached refresh logic in `MainWindow`: [suno_credits.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/suno_credits.py)
- YouTube upload jobs are persisted in `youtube_upload_jobs` and displayed in the YouTube page.

## Dashboard Data Model

### A) KPI Inputs (No New DB Needed)
- Active/Failed counts: derived from Progress rows (stage/status + notes).
- Songs generated: count `songs` rows by date or by `batch_id` range.
- Images generated: count `image_jobs` with `status=READY` by date.
- MP4 converted / merged: derived by scanning output directories (cached) or by adding conversion job records (recommended later).
- YouTube uploaded: count `youtube_upload_jobs` with terminal success status by date.
- Suno credits remaining: from existing credits cache.

### B) Cost Tracking (New DB Recommended)
Reason: costs should be auditable and not inferred from filesystem.

Add a small append-only table:

`cost_events` (new)
- `id` (pk)
- `created_at` (timestamp)
- `provider` (text: suno/slai/deepseek/youtube/ffmpeg/other)
- `kind` (text: music_generate, lyric_generate, image_generate, mp4_convert, merge, youtube_upload)
- `batch_id` (text, nullable)
- `profile_id` (text, nullable)
- `role` (text, nullable: OK/ALT)
- `units` (numeric) — e.g. credits, images, requests, minutes
- `unit_name` (text) — credits, images, requests, minutes
- `estimated_cost` (numeric) — optional, if money mapping known
- `currency` (text) — optional
- `meta_json` (jsonb) — error/status/request IDs

How to populate:
- Suno: record `credits_used = credits_before - credits_after` per batch (or per request) where possible.
- SLAI: record image generation calls (units=1 per image).
- LLM: record request count; if token usage not available, treat as “requests”.
- YouTube: record uploads count; optional bandwidth/time.

## UI Implementation Plan
- Dashboard lives on the primary `home` page (left-nav label `Dashboard`, key `home`).
- Implement as a QWidget with:
  - KPI cards row (existing card components used in other pages)
  - Two columns: Cost/Usage (left) and Pipeline Health (right)
  - Recent Activity table (bottom)
- Refresh model:
  - Use background-thread collection (same pattern as Progress) and UI signal apply.
  - Cache scan results by directory mtime (reuse existing scan helper).

## Performance Considerations
- Use batched SQL for all KPI counts (group by batch_id/date).
- Avoid scanning thousands of files every refresh; reuse the existing directory mtime cache.
- Keep refresh interval modest (2–5s) and only auto-refresh when Dashboard tab is active.

## Security
- Never log API keys or tokens into cost_events meta.
- cost_events stores only derived cost/units and safe identifiers.
