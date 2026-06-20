# Progress Page (Tasks)

## Phase 1 — Foundations
- [ ] Add a new primary navigation item: Progress.
- [ ] Create a new Progress workspace page layout (header + filters + table + status).

## Phase 2 — Data Model
- [ ] Define a unified progress row model per `batchId` × channel role (OK/ALT):
  - Music: songs saved / expected
  - Image: background status, thumbnail status
  - Converter: mp3 count / expected, mp4 count / expected
  - Merge: merged output status + filename
- [ ] Add efficient DB helpers for fetching image job statuses per batch/profile.

## Phase 3 — UI/UX (Professional Reporting)
- [ ] Implement a compact summary header (current pipeline status + last refresh time).
- [ ] Implement a readable table with:
  - Batch, Run Date
  - Channel (Profile name + OK/ALT)
  - Music/Image/Converter/Merge progress fields
  - Overall stage + error preview
- [ ] Add Refresh action and optional auto-refresh timer.
- [ ] Add date-range filters (From/To) to limit the displayed batches.
- [ ] Add right-click row actions to restart stages (Image/Converter/Merge) and open the output folder.

## Phase 4 — Verification
- [ ] Run generation with `songs_per_batch=10` and validate:
  - music rows increment up to 10/10
  - image statuses update BG→TH correctly
  - converter shows mp3/mp4 counts progressing to 10/10
  - merge shows “waiting” until mp4=10/10, then “ready” with MERGED filename

## Regression Checklist
- [ ] Sidebar navigation still works for existing pages.
- [ ] App startup does not break when Postgres is not configured (Progress should show a helpful message).
