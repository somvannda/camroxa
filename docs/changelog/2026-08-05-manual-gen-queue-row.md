# Manual Generation creates a Not available Image queue row

**Date:** 2026-08-05  
**Branch:** `feature/image-prompt-categories-and-replace`  
**Surfaces:** `platform_api`, `camxora_python`  
**Spec:** Image page Manual Generation (deselected) creates a real queue row

## Summary

Deselected **Manual Generation** no longer uses the `/generation/image` playground preview. It creates a lightweight today-dated batch labeled **Not available**, attaches BG+TH album-slot jobs, runs only the clicked kind through the normal billed image-job path, and selects the new Image queue row.

## Changes

- `POST /api/v1/image-jobs/manual-generate` — synthetic `manual_image` batch (`song_count=0`, `ok_album="Not available"`, planned dates = UTC today), BG+TH jobs, run clicked kind only
- Migration `082_batch_song_count_allow_zero` — allow `batches.song_count = 0`
- Enqueue worker drain for the clicked kind only (BG), or BG+TH when Thumbnail is clicked so composite still uses Background like the pipeline
- HTTP returns after create/enqueue (no inline wait) so desktop clients do not hit the ~30s timeout
- Queue Channel/Role for `manual_image` rows show **Not available** / **N/A**
