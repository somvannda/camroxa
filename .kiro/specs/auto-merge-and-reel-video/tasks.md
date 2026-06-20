# Implementation Plan: Auto Merge and Reel Video

## Overview

This plan implements two new automation pipeline gates — Auto Merge and Auto Reel — as toggled steps in the auto-video workflow. The implementation proceeds from database schema changes, through data layer and pipeline logic, to UI integration and progress tracking. Each task builds incrementally on the previous, ensuring no orphaned code.

## Tasks

- [x] 1. Database migrations and data layer
  - [x] 1.1 Add `kind` column to video_templates table and `reel_template_id` column to profiles table
    - Add migration in `python_app/database/music_migrate.py` to ALTER TABLE video_templates ADD COLUMN kind text NOT NULL DEFAULT 'video'
    - Add index: CREATE INDEX IF NOT EXISTS idx_video_templates_kind ON video_templates(kind)
    - Add migration to ALTER TABLE profiles ADD COLUMN reel_template_id text NOT NULL DEFAULT ''
    - Ensure migration runs via `ensure_database_and_migrate`
    - _Requirements: 6.1, 6.4, 9.1_

  - [x] 1.2 Add template kind filtering to template DB functions
    - Modify `db_list_video_templates` in `python_app/database/music_db.py` (or templates coordinator) to accept a `kind` parameter defaulting to `"video"`
    - Filter query with `WHERE kind = ?`
    - Ensure backward compatibility: existing calls without `kind` param still get video templates
    - _Requirements: 6.2, 6.3, 6.4_

  - [x] 1.3 Add `reelTemplateId` field to Profile data model and persistence
    - Update Profile model/dataclass to include `reelTemplateId` field mapped to `reel_template_id` column
    - Update profile save logic to persist `reelTemplateId`
    - Update profile load logic to read `reelTemplateId`
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 1.4 Write property tests for template kind filtering (Property 6)
    - **Property 6: Template kind filtering**
    - Generate random sets of templates with mixed kind values, verify filtering by kind="video" returns only video templates and kind="reel" returns only reel templates with no overlap
    - **Validates: Requirements 6.2, 6.3**

  - [ ]* 1.5 Write property test for reel template CRUD isolation (Property 7)
    - **Property 7: Reel template CRUD isolation**
    - Perform CRUD operations on reel templates and verify video templates remain unchanged in content, count, and field values
    - **Validates: Requirements 8.2, 8.3**

- [x] 2. Settings persistence and toggle UI
  - [x] 2.1 Add `autoMergeAfterVideo` and `autoReelAfterVideo` settings persistence
    - Add both boolean keys to the Music_Settings persistence layer (likely `python_app/features/persistence/`)
    - Both default to `false` when not present or when read fails
    - _Requirements: 1.2, 1.3, 1.4, 3.2, 3.3_

  - [x] 2.2 Add Auto Merge and Auto Reel toggle buttons to Automation Card
    - In `python_app/views/music_view.py` (or the Automation Card UI component), add "Auto Merge" toggle after "Auto-Video" and before "Auto-Upload"
    - Add "Auto Reel" toggle after "Auto Merge"
    - Use existing `_create_music_inline_toggle(label, callback)` pattern
    - Wire callbacks to `_update_music_settings({"autoMergeAfterVideo": bool})` and `_update_music_settings({"autoReelAfterVideo": bool})`
    - Restore toggle state from persisted settings on page load
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 3.1, 3.2, 3.3_

  - [ ]* 2.3 Write unit tests for toggle persistence and restore
    - Test `autoMergeAfterVideo` persists on toggle click
    - Test `autoReelAfterVideo` persists on toggle click
    - Test toggles restore from settings on page load, default to false
    - _Requirements: 1.2, 1.3, 1.4, 3.2, 3.3_

- [x] 3. Reel template CRUD and profile selector
  - [x] 3.1 Implement reel template CRUD operations
    - Add create/update/delete support for templates with `kind="reel"` in `python_app/features/templates/management.py`
    - Ensure create stores uid, name, source, template JSON, kind="reel", and timestamp
    - Verify delete/update of reel templates does not affect video templates
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 3.2 Add Reel Template combo box to Profile Editor
    - In the profile editor UI, add "Reel template" combo box adjacent to existing "Video template" combo
    - Populate with templates from `db_list_video_templates(cfg, kind="reel")`
    - Wire selection to persist `reelTemplateId` on profile save
    - Restore selection on profile load
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 4. Checkpoint - Verify data layer and UI toggles
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Auto-Video Pipeline — Merge gating
  - [x] 5.1 Gate the existing merge step with `autoMergeAfterVideo` setting
    - In `python_app/app/auto_video_handlers.py`, wrap the existing merge block in `if settings.get("autoMergeAfterVideo"):`
    - When false, set merged_path to "" and skip merge entirely
    - Ensure `autoMergeAfterVideo` is the sole toggle controlling this (NOT `videoAutoMergeMp4`)
    - On merge failure: set output to "", emit status with failure reason, proceed to reel merge if applicable
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 5.2 Write property test for merge gating (Property 1)
    - **Property 1: Merge gating depends solely on autoMergeAfterVideo**
    - For any combination of settings, verify merge is invoked iff `autoMergeAfterVideo` is true. When false, done event `output` is empty string.
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [x] 6. Auto-Video Pipeline — Reel export phase
  - [x] 6.1 Create `AutoVideoReelPlan` dataclass
    - Add dataclass in `python_app/features/auto_video/coordinator.py` (or a new models file)
    - Fields: reel_template, width (1080), height (1920), mp3s, bg_path, logo_path, output_dir, ffmpeg_path, speed_mode, export_workers
    - _Requirements: 4.2, 4.3_

  - [x] 6.2 Implement `resolve_reel_plan` method on AutoVideoCoordinator
    - Resolve reel template from profile's `reelTemplateId`
    - Return `AutoVideoReelPlan` with width=1080, height=1920, same bg_path and output_dir as standard plan
    - Return None if `reelTemplateId` is empty or template is missing, emit warning status
    - _Requirements: 4.4, 4.5_

  - [x] 6.3 Implement `_export_reel_videos` in auto_video_handlers
    - After standard 16:9 export completes, when `autoReelAfterVideo` is true, resolve reel plan
    - Render one 9:16 MP4 per MP3 track with `_REEL` suffix naming (e.g., `{trackname}_REEL.mp4`)
    - Write reel MP4 files to same output directory as standard videos
    - On individual track failure: log, skip that reel, continue remaining tracks
    - When `autoReelAfterVideo` is false, skip entirely
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6, 4.7, 12.1, 12.2_

  - [ ]* 6.4 Write property test for reel export count (Property 2)
    - **Property 2: Reel export count matches MP3 count when enabled**
    - For N MP3 tracks with valid reel template and autoReelAfterVideo=true, exactly N reel exports initiated. When false, zero reel exports.
    - **Validates: Requirements 4.1, 4.6**

  - [ ]* 6.5 Write property test for reel plan invariants (Property 3)
    - **Property 3: Reel plan invariants**
    - Verify resolved reel plan always has width=1080, height=1920, same bg_path and output_dir as standard plan.
    - **Validates: Requirements 4.2, 4.3, 12.1**

  - [ ]* 6.6 Write property test for reel file naming (Property 12)
    - **Property 12: Reel file naming conventions**
    - For any track stem S, individual reel is `{S}_REEL.mp4`. For role R and suffix X, merged reel is `MERGED_REEL_{R}_{X}.mp4`. Verify patterns are consistent and invertible.
    - **Validates: Requirements 12.2, 12.3**

- [x] 7. Auto-Video Pipeline — Reel merge
  - [x] 7.1 Implement reel merge logic in auto_video_handlers
    - When `autoMergeAfterVideo` is true AND `autoReelAfterVideo` is true AND ≥2 reel MP4 files exist: invoke Merge_Worker for reel files with output name `MERGED_REEL_{role}_{suffix}.mp4`
    - When <2 reel files exist, skip reel merge and keep single file as-is
    - When `autoMergeAfterVideo` is false, skip reel merge entirely
    - Execute reel merge as separate operation from standard merge (failure of one does not prevent the other)
    - On reel merge failure: emit warning, preserve individual reel files, set reel_merged_path to ""
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 12.3_

  - [ ]* 7.2 Write property test for reel merge gating (Property 4)
    - **Property 4: Reel merge gating**
    - Reel merge invoked iff autoMergeAfterVideo=true AND autoReelAfterVideo=true AND ≥2 reel files. Otherwise no reel merge.
    - **Validates: Requirements 5.1, 5.3**

  - [ ]* 7.3 Write property test for merge operation isolation (Property 5)
    - **Property 5: Merge operation isolation**
    - Verify failure of standard merge does not prevent reel merge and vice versa. Each merge runs independently.
    - **Validates: Requirements 5.4**

- [x] 8. Done event schema and YouTube exclusion
  - [x] 8.1 Update done event to include `reelOutput` field
    - Modify the `auto_video_done` event emission to include `reelOutput` field (merged reel path or "")
    - Ensure event always contains: type, ok, output, reelOutput, role, batchId, profileId
    - _Requirements: 11.1, 11.3_

  - [x] 8.2 Ensure YouTube upload handler ignores `reelOutput`
    - In `python_app/app/youtube_upload_handlers.py`, verify handler only reads `output` field
    - Confirm reel outputs (individual and merged) are excluded from YouTube upload regardless of `autoUploadYouTube` setting
    - _Requirements: 11.2, 11.4_

  - [ ]* 8.3 Write property test for done event and YouTube exclusion (Property 11)
    - **Property 11: Done event reelOutput field and YouTube exclusion**
    - Verify done event always contains `reelOutput` field. YouTube handler processes only `output`, never triggers for `reelOutput`.
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.4**

- [x] 9. Checkpoint - Verify pipeline logic
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Progress page updates
  - [x] 10.1 Update `_scan_progress_output_dir` for reel file classification
    - Modify scan in `python_app/features/progress/coordinator.py` to classify files:
      - Standard MP4: ends in `.mp4`, NOT `_REEL.mp4`, NOT prefixed `MERGED_`
      - Reel MP4: ends in `_REEL.mp4`, NOT prefixed `MERGED_REEL_`
      - Standard merged: prefixed `MERGED_`, NOT `MERGED_REEL_`
      - Reel merged: prefixed `MERGED_REEL_`
    - Every `.mp4` file belongs to exactly one category
    - _Requirements: 10.5, 12.4_

  - [x] 10.2 Update converter column to show reel counts
    - When `autoReelAfterVideo` is true, display format: "MP4 {x}/{y} · Reel {a}/{b}"
    - _Requirements: 10.1_

  - [x] 10.3 Update merge column for reel merged status
    - When both toggles active, display both standard and reel merge filenames
    - _Requirements: 10.2_

  - [x] 10.4 Update stage detection for reel awareness
    - Stage SHALL NOT advance past "Converter" until all expected reel MP4s are produced (when Auto Reel enabled)
    - Stage SHALL NOT advance past "Merge" until reel merge completes (when both toggles enabled)
    - _Requirements: 10.3, 10.4_

  - [ ]* 10.5 Write property test for file classification (Property 8)
    - **Property 8: Progress page file classification by naming convention**
    - For arbitrary filenames, verify scan classifies each .mp4 into exactly one of 4 categories based on naming convention.
    - **Validates: Requirements 10.5, 12.4**

  - [ ]* 10.6 Write property test for progress stage detection (Property 9)
    - **Property 9: Progress stage detection with reel awareness**
    - When autoReelAfterVideo=true, stage does not advance past Converter until all reel MP4s produced. With autoMergeAfterVideo=true, stage does not advance past Merge until reel merge completes.
    - **Validates: Requirements 10.3, 10.4**

  - [ ]* 10.7 Write property test for converter column display (Property 10)
    - **Property 10: Progress converter column includes reel counts**
    - When autoReelAfterVideo=true, converter column text includes both standard and reel MP4 counts.
    - **Validates: Requirements 10.1**

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation language is Python, matching the existing codebase
- All reel pipeline logic runs sequentially after standard export within the same worker thread to avoid doubling subprocess concurrency

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.1"] },
    { "id": 2, "tasks": ["1.4", "1.5", "2.2", "3.1"] },
    { "id": 3, "tasks": ["2.3", "3.2"] },
    { "id": 4, "tasks": ["5.1", "6.1"] },
    { "id": 5, "tasks": ["5.2", "6.2"] },
    { "id": 6, "tasks": ["6.3"] },
    { "id": 7, "tasks": ["6.4", "6.5", "6.6", "7.1"] },
    { "id": 8, "tasks": ["7.2", "7.3", "8.1"] },
    { "id": 9, "tasks": ["8.2", "8.3"] },
    { "id": 10, "tasks": ["10.1"] },
    { "id": 11, "tasks": ["10.2", "10.3", "10.4"] },
    { "id": 12, "tasks": ["10.5", "10.6", "10.7"] }
  ]
}
```
