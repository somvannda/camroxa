# Image Generation (Samples) — Tasks

Status legend: pending | in progress | completed | blocked | needs review

## Phase 0 — Decisions (completed)

- [x] (completed) Provider: SLAI
- [x] (completed) Thumbnail: derived from generated background (bg-only)
- [x] (completed) Output layout: by run date + pair
- [x] (completed) Per-channel output count: OK and ALT each get their own images (e.g., 3 OK + 3 ALT => 6/day)
- [x] (completed) Keep per-batch outputs: do not overwrite; use filename suffix

## Phase 1 — Data + Settings (pending)

Status: completed

- [x] (completed) Added DB schema for image generation jobs
  - image_jobs (background + thumbnail jobs)
  - image_prompt_presets (DB-backed presets)
  - image_random_history (avoid repeat sample/prompt picks)
- [x] (completed) Added DB migration + indexes
- [x] (completed) Added DB repository functions
  - create/list/update image jobs
  - retry/status transitions
  - preset list + least-used picker
  - preset CRUD (add/edit/delete)
- [x] (completed) Added Settings → Image configuration
  - BG samples dir and Thumb samples dir (separate folders; backward compatible with legacy imageSamplesDir)
  - resolution + style strength

## Phase 2 — UI/UX (pending)

Status: completed

- [x] (completed) Replaced the `"image"` placeholder page with the Image workspace
- [x] (completed) Samples layout updated per Boss request
  - Background Samples list (row 1) + 16:9 Background Preview aligned next to it
  - Thumbnail Samples list (row 2) + 16:9 Thumbnail Preview aligned next to it
- [x] (completed) Sample lists auto-load once sample dirs are configured; selection max 5 enforced
- [x] (completed) Job queue selection loads generated background + thumbnail previews
- [ ] (pending) Batch picker (multi-select) sourced from Music History; Generate Now runs selected batches
- [x] (completed) Batch picker (multi-select) sourced from Music History; Generate Now runs selected batches
- [x] (completed) Clear Job Queue (delete all image jobs) with confirmation
- [x] (completed) Footer progress summary (checked/completed/failed) and richer logs surfaced to UI/terminal
- [x] (completed) Prompt presets
  - preset dropdown + Pick Random (least-used)
  - Manage prompts dialog (add/edit/delete)

## Phase 3 — Image Generation Engine (pending)

Status: completed

- [x] (completed) Provider adapter (SLAI image client)
- [x] (completed) Align SLAI IMG request format to current docs (multipart/form-data + response_format=url), include Authorization on URL download, and improve retry/log detail
- [x] (completed) Background job runner (sample → SLAI → cover-crop → save)
- [x] (completed) Thumbnail job runner (generated background + thumb sample style blend → SLAI → cover-crop → save)
- [x] (completed) Concurrency control via DB polling batch size
- [x] (completed) Resume behavior: pending jobs are DB-backed and can continue on restart

## Phase 4 — Auto-Run During Music Generation (pending)

Status: completed

- [x] (completed) Auto-run trigger: enqueue image jobs when a song is created (per batch)
- [x] (completed) Does not block song generation; runs in background poll worker
- [x] (completed) Enforced invariant: one background + one thumbnail per channel per batch via DB unique key

## Phase 5 — Verification (pending)

- [ ] (pending) Manual QA checklist
  - selection max 5 enforced
  - empty states (no samples found)
  - invalid paths
  - provider error surfaced to footer
  - cancel stops new work and finishes safely
- [ ] (pending) Regression check
  - Music generation still works
  - Suno pipeline unaffected
  - no UI freezes during long image runs

## Phase 6 — Documentation (pending)

- [x] (completed) Updated DEVELOPMENT_LOG.md with:
  - schema changes
  - new UI page
  - provider config
  - migration notes
