# Image Generation (Samples) — Requirements

## Goal

Provide a simple, production-quality workflow to generate:
- One **background image** per channel per batch/run-date.
- One **thumbnail image** per channel per batch/run-date, derived from that channel’s generated background image.

This workflow must support many dates, many channel pairs, multiple batches, and long-running polling/downloading until all images are finished.

## Key Definitions

- **Channel**: one selected profile from either the OK list or the ALT list.
- **Channel Pair**: one OK channel and one ALT channel at the same index (still used by Music generation). Image generation produces assets for both channels (2 channels per pair).
- **Run Date**: the date the batch was requested for (already used by Music generation).
- **Batch**: a generation run identified by `batchId` (e.g. `batch-YYYY-MM-DD-...`).
- **Samples**: local image files selected from disk to guide the image generation style.

## User Stories

1) As Boss, I can pick **background samples** from a folder and select up to **5** files.
2) As Boss, I can pick **thumbnail samples** from a folder and select up to **5** files.
3) As Boss, I can type a prompt manually or pick one from a preset list.
4) As Boss, I can enable **Auto** mode so images generate automatically during song generation.
5) As Boss, I can run many days and channel pairs; the app continues generating/polling/downloading until all images are complete.
6) As Boss, I can manually generate images by selecting one or more existing **Music batches** from History (not by creating new batch ids).
7) As Boss, I can clear the entire image job queue when I want to restart testing.

## Scope (Phase 1)

### UI

- Add a dedicated **Image** workspace (use existing primary page key `"image"`).
- Provide two simple file lists:
  - Background Samples (multi-select, max 5)
  - Thumbnail Samples (multi-select, max 5)
- Provide prompt controls:
  - Prompt textbox
  - Preset prompt dropdown/list + “Pick Random” button
  - Optional “Smart Prompt” button (AI-assisted prompt expansion)
- Provide execution controls:
  - Batch picker (multi-select) sourced from **Music History** (songs table batches)
  - Generate Now (manual run for the selected batches)
  - Auto-run toggle (used by Music generation flow)
  - Clear Job Queue (delete all image jobs)
  - Status/Progress area (queue count, success/fail counts, last error)
  - Footer summary should show `completed / checked / failed` and update after each poll.

### Generation Behavior

- Manual run uses:
  - Selected batches from Music History (one or more `batchId`)
  - Prompt + selected sample lists
- Required outputs per **run date**:
  - `N = number_of_OK_channels + number_of_ALT_channels` (i.e., total channels)
  - Background images: `N`
  - Thumbnails: `N`
- Example (Boss requirement):
  - 3 dates × (3 OK + 3 ALT) => 18 backgrounds + 18 thumbnails.

### Randomization & Non-Repetition

- Support random selection of:
  - sample images (from selected lists) and/or
  - prompt presets
- Avoid repeating the same random selection frequently by storing:
  - used order / used counts
  - last-used timestamps
- If the pool is exhausted, cycle safely (least-recently-used strategy).

## Non-Goals (Phase 1)

- No remote “media library” database; samples are **file system listed** only.
- No heavy image editor inside the app.
- No multi-user / sharing workflows.

## Constraints

- Background sample selection: maximum 5 items.
- Thumbnail sample selection: maximum 5 items.
- Sample listing: list only images directly inside the configured folder (ignore subfolders).
- Random mode (per list): when enabled, selection is optional and the system will pick 1 sample per job using least-used history across the folder (best-effort: cycles through all samples before repeating).
- Must not block the UI thread; long jobs run in background threads with UI updates.
- Must be resilient for long runs (many dates/batches): continue until completion or explicit stop.

## Configuration

Use existing settings keys already present in the app defaults:
- `imageBackgroundSamplesDir`: background samples folder
- `imageThumbnailSamplesDir`: thumbnail samples folder
- `imageSamplesDir`: legacy base folder fallback (`{base}/background`, `{base}/thumbnail`)
- `imageOutputDir`: optional base output folder (Phase 1 will primarily write into the same run folders as downloaded songs)
- `autoGenImage`: enable auto-run during Music generation
- `slaiImgApiKey`, `slaiImgModel` (or alternative provider, decision needed)

## Decisions (Boss)

Confirmed:
- Provider: **SLAI**
- Thumbnail rule: **generated from the generated background image**
- Output layout: **same folders as downloaded songs (by run date + pair)**

Extra note:
- Thumbnail generation should support preset “text style” prompts (typography/art-direction instructions applied on top of the background).
- Thumbnail samples are used as an embedded visual reference to guide typography style (AI-driven) and should not be blended into the background.
- The generated background must remain pixel-identical in the thumbnail; thumbnail is produced by compositing a text-only overlay onto the background (and the overlay may be scaled down to achieve the desired text size).

## Output Location (Boss)

- Background + thumbnail images must be saved into the **same per-channel run folders** where Suno audio files are downloaded.
- For each channel (OK and ALT) + batch + run-date, the system generates one background and one thumbnail, then saves them into that channel’s run folder (same folder as that channel’s audio).
- Keep images per batch (do not overwrite):
  - `background_<batch_suffix>.png`
  - `thumbnail_<batch_suffix>.png`

## Job Queue UX (Boss update)

- Job queue should present **one row per channel per batch** with both:
  - Background status + file
  - Thumbnail status + file
- Background must be generated before thumbnail (thumbnail depends on that channel’s background).

## AI Implementation Prompt (for a coding AI)

Copy/paste and fill the placeholders:

"""
You are a senior engineer. Implement an Image Generation feature in the existing Python PyQt6 app at `python_app/`.

Requirements:
- Add an Image workspace (replace the existing placeholder primary page key `image`) with:
  - Background Samples file list (file-system based) with multi-select max 5
  - Thumbnail Samples file list (file-system based) with multi-select max 5
  - Prompt input + preset prompt list + random pick (avoid repeats via DB usage history)
  - Optional Smart Prompt (SLAI/OpenAI text expansion is acceptable if key exists)
  - Generate Now + Stop, plus job queue table with batch separators and dot status
- Image jobs must be DB-backed so long runs can resume after restart:
  - Create `image_jobs` table (background + thumbnail jobs) and required indexes via migration.
  - Implement DB functions to enqueue/list/update jobs and to mark downloaded outputs.
- Auto-run integration:
  - When Music generation runs and `autoGenImage=true`, enqueue image jobs per channel:
    - one background job per (batchId, OK profile)
    - one background job per (batchId, ALT profile)
    - thumbnails for each channel depend on that channel’s background output
- Provider:
  - Use SLAI as the image generation provider (keys: `slaiImgApiKey`, model: `slaiImgModel`).
  - Thumbnail must be generated from the generated background image and use a preset “text style” prompt template.
- Output layout:
  - Save into the same per-channel run folders where Suno songs are downloaded.
  - Keep per-batch outputs using filename suffix (do not overwrite):
    - `background_<batch_suffix>.png`
    - `thumbnail_<batch_suffix>.png`
- Do not block the UI thread. Use background threads and emit UI events.
- Follow existing architecture patterns and styles in `python_app/main.py`, `views/*.py`, `controllers/music_controller.py`, `database/music_migrate.py`.

Deliverables:
- Code changes + DB migration
- Updated DEVELOPMENT_LOG.md describing changes and migration steps
"""
