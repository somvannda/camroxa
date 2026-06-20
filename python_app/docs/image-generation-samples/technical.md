# Image Generation (Samples) — Technical Plan

## Codebase Reality Check (Current State)

### Existing Settings Keys (already in defaults)

In [music_model.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/models/music_model.py#L17-L91), these keys already exist but are not wired to a real feature:
- `imageOutputDir`
- `imageBackgroundSamplesDir`
- `imageThumbnailSamplesDir`
- `imageSamplesDir` (legacy; used as fallback to `{base}/background` and `{base}/thumbnail`)
- `thumbnailOverlayMode`
- `backgroundSourceMode`
- `imageResolution`
- `styleStrength`
- `autoGenImage`
- `slaiImgApiKey`, `slaiImgModel`

### Existing UI Slot

There is an `"Image"` primary page key in the app shell, but it’s currently a placeholder:
- [main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L3199-L3206)

### Existing Music generation pairing rule

The Python app requires **equal OK/ALT channel counts** and pairs them by index:
- [main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L1692-L1696)
- Batch id is generated per `run-date + channel-pair`:
  - [music_controller.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/controllers/music_controller.py#L232-L241)

Image generation will still reuse the same OK/ALT selection source, but **outputs are per channel**:
- 3 OK + 3 ALT => 6 channels => 6 backgrounds + 6 thumbnails per day.

## Architecture Overview

### High-level flow

UI (Image page) → Job enqueue (DB) → Worker loop (background thread) → Provider API calls → Poll/download → DB update → UI refresh.

### Why DB-backed jobs

Long runs (many dates/batches) must be resilient:
- app restart should resume pending jobs
- avoid “lost work” when downloads fail
- support “keep running until everything finishes”

This is the same reliability goal we implemented for Suno via DB-backed pending tasks.

## Confirmed Decisions (Boss)

- Provider: **SLAI**
- Thumbnail derivation: **background-only**
- Output layout: **same folders as downloaded songs (by run date + pair)**
  - Use the same per-channel run folders used by Suno downloads for that channel/run-date.
  - Keep per-batch outputs (do not overwrite):
    - `background_<batch_suffix>.png`
    - `thumbnail_<batch_suffix>.png`

## Proposed DB Schema

Add the following to the existing migration file [music_migrate.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/music_migrate.py):

### `image_jobs`

One row per output image job.

Columns (proposal):
- `id serial primary key`
- `job_uid text unique` (stable id like `img-...`)
- `batch_id text not null`
- `run_date date` (derived from `ymd` like `2026-05-26`)
- `pair_index int not null` (0-based channel pair index; copied from Music generation for grouping)
- `profile_id text not null` (the channel that owns the output folder)
- `channel_role text not null` (`OK` | `ALT`)
- `kind text not null` (`background` | `thumbnail`)
- `status text not null` (`PENDING` | `RUNNING` | `READY` | `FAILED`)
- `prompt text not null default ''`
- `prompt_source text not null default ''` (manual | preset | smart)
- `sample_paths jsonb not null default '[]'` (selected sample file paths)
- `input_image_path text not null default ''` (for thumbnail jobs: background output)
- `output_image_path text not null default ''`
- `error text not null default ''`
- `attempt_count int not null default 0`
- `created_at timestamp default now()`
- `updated_at timestamp default now()`

Indexes:
- `(batch_id)`
- `(status, updated_at)`
- `(run_date desc)`

### `image_prompt_presets` (optional)

If Boss wants presets persisted (recommended for reuse):
- `id serial primary key`
- `name text not null`
- `prompt text not null`
- `used_count int not null default 0`
- `last_used_at timestamp`
- unique index on `(name)`

### `image_random_history` (optional)

If we want strict “avoid repeats” across runs:
- `id serial primary key`
- `kind text not null` (background_sample | thumbnail_sample | prompt_preset)
- `value text not null` (file path or preset name)
- `used_count int not null default 0`
- `last_used_at timestamp`
- unique index on `(kind, value)`

Decision: we can start with just `used_count/last_used_at` in the presets table and a minimal history table for sample paths.

## Python Modules / Placement

### DB layer

Add `python_app/database/image_db.py` for image job CRUD to avoid bloating `music_db.py`.
- `upsert_image_job(cfg, job)`
- `list_image_jobs(cfg, from_ymd, to_ymd, limit)`
- `list_pending_image_jobs(cfg, limit)`
- `mark_image_job_ready(cfg, job_uid, output_path)`
- `mark_image_job_failed(cfg, job_uid, error)`
- `bump_random_usage(cfg, kind, value)`

### Service layer

Add `python_app/services/image_generation.py`:
- `enqueue_image_jobs_for_batch(cfg, batch_id, run_date, pair_index, profile_ok_id, profile_alt_id, selections, prompt_cfg)`
- `poll_and_download_pending_images(cfg, provider_cfg, limit) -> dict`

### Provider adapter

Add one provider interface, with concrete adapter(s):
- `python_app/services/image_provider.py` (interface)
- `python_app/services/image_provider_slai.py`

This keeps provider changes isolated without touching UI/business logic.

## UI Implementation Plan

### New Image page UI

Replace the `"image"` placeholder in [main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L3199-L3206) with a real page built from `views/image_view.py`.

UI elements:
- Two QListWidget file lists (background + thumbnail), sourced from configured dirs
  - enforce max 5 selection
  - quick preview
- Prompt area:
  - prompt input
  - preset dropdown
  - random pick
  - smart prompt (optional)
- Batch picker (Boss update):
  - list batches from Music History (songs table) and allow multi-select
  - manual run uses the selected batch ids (no new batch ids created)
- Job queue table:
  - batch separators (reuse pattern from Music History)
  - one row per channel per batch (BG+TH in the same row)
  - background dot + thumbnail dot + output paths

### Configuration placement (Boss request)

Put Image configuration into Settings (as tabs) instead of the Image workspace:
- Add a new Settings tab (recommended location: Music → Settings tabs) named `Image`
- Settings fields live there:
  - `imageBackgroundSamplesDir`, `imageThumbnailSamplesDir`, `imageOutputDir`
  - `slaiImgApiKey`, `slaiImgModel`
  - `imageResolution`, `styleStrength`
  - `autoGenImage`

### Prompt preset management (Boss request)

- Prompt presets are stored in `image_prompt_presets` and are manageable from the Image workspace:
  - add / edit / delete presets
  - random pick uses least-used selection (`used_count`, `used_at`)

### Preview behavior (Boss request)

- Image workspace uses 16:9 preview panes for consistent browsing.
- Selecting a Job Queue row loads the generated Background + Thumbnail outputs (when READY) into the preview panes.

### Performance considerations

- Avoid per-row SVG rendering; reuse the SVG icon cache already implemented in [main.py:_render_svg_icon](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L861-L889).
- Disable table updates during bulk fill.

## Auto-Run Integration (During Music Generation)

Best insertion point is inside Music generation loop, where `batch_id`, `ymd`, and channel pair ids are known:
- [music_controller.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/controllers/music_controller.py#L232-L241)

Proposed behavior:
- If `settings["autoGenImage"] == True` and DB is configured:
  - enqueue per-channel jobs (2 channels per pair):
    - OK channel:
      - background job for `(batch_id, profile_ok_id)`
      - thumbnail job for `(batch_id, profile_ok_id)` with dependency on that background output
    - ALT channel:
      - background job for `(batch_id, profile_alt_id)`
      - thumbnail job for `(batch_id, profile_alt_id)` with dependency on that background output
- Start/continue an Image poll timer similar to Suno polling.

Invariant:
- For each `(batch_id, profile_id, kind)` there is at most one job (idempotent upsert).

## Thumbnail “Text Style” Presets

Boss requirement: thumbnail generation uses the generated background image plus preset “text style” prompt instructions.

Implementation direction:
- Maintain a separate preset list for thumbnail prompts (DB-backed recommended) that can include placeholders:
  - `{title}`, `{album}`, `{channel}`, `{run_date}`
- When enqueuing thumbnail jobs, render the final thumbnail prompt by substituting placeholders from the batch/song context (when available).

## Error Handling Strategy

- Any provider/poll/download error:
  - store the full error string into `image_jobs.error`
  - set `status = FAILED`
  - UI displays red dot, footer shows full error
- Retry:
  - clears error, increments attempt_count, returns to PENDING

## Job Queue Maintenance (Boss update)

- Add DB helper to clear all jobs:
  - `truncate image_jobs`
- UI exposes “Clear Job Queue” (danger) with confirmation.

## Testing Strategy (Practical)

- Unit-ish tests for:
  - selection limit enforcement (max 5)
  - job enqueue idempotency
  - pending job query and transitions
- Manual QA:
  - long-run with 3 days × 3 pairs
  - restart app mid-run and verify resume

## Risks

- Provider API differences (async vs sync) require adapter abstraction.
- File download 403/blocked (similar to Suno) needs stable headers and/or signed URL timing management.
- Very large job sets (hundreds) need queue throttling and non-blocking UI updates.
