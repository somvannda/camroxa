# "Change Run Folder & Resume" dumped files flat into the picked folder instead of recreating the channel/date-album structure

**Date:** 2026-08-01
**Status:** implemented (fix built into desktop v1.0.12, pending user install)

## Summary

After picking a new folder in "Change Run Folder & Resume," the app immediately
started writing MP3s and background/thumbnail images **directly into the
picked folder**, flat — not into a `{channel}/{date}_{album}` structure like
every other part of the pipeline (drafting, Suno submission, Continue
Progress) creates and expects. The folder picker was treating the user's
pick as if it were already the exact leaf run folder, when the rest of the
app treats a "run folder" as `{base}/{channel profile folder}/{date}_{album
slug}`.

## Product impact

**Before:** Picking, say, `D:\NewMusic` as the new folder for a `bass-drive`
row put `1. Some Song_OK.mp3`, `background-16x9-ok.png`, etc. straight into
`D:\NewMusic\`, with no `bass-drive` or date/album subfolder — inconsistent
with every folder the normal Generate pipeline creates, and confusing/messy
once a user has multiple channels or batches recovering into the same base
drive.

**After:** Picking `D:\NewMusic` for that same row now creates
`D:\NewMusic\bass-drive\2026-08-02_Grateful-Hearts-Rest\` and downloads
everything there — reusing the row's *existing* channel-folder and
date-album-folder names, so the new location mirrors exactly what the
pipeline would have created there in the first place. The success banner
and the row's tracked run_dir reflect this full recreated path, not the
picked base folder.

## Technical impact

The picked folder is now treated as a **base directory**, not the final
run folder. `ProgressView._change_run_folder()` derives the channel-folder
and date-album-folder names from the row's *existing* `run_dir` (its parent
and leaf path segments, respectively — these were already built correctly
by the pipeline when the batch was first generated, via
`platform_api.services.run_directory_planner.plan_run_directories()` /
`build_run_folder_label()`) and re-parents them under the newly picked
folder before calling `RunFolderRecoveryWorker`. No server-side change was
needed — `RunFolderRecoveryWorker` already treats whatever full path it's
given as the exact `run_dir` to create/download into (via `ensure_directory`,
which `mkdir(parents=True)`s the whole nested path), so passing it the fully
reconstructed path was sufficient. The "already this row's run folder"
duplicate check now also compares against the *reconstructed* path, not the
raw picked folder, so picking the row's own parent-of-parent folder is
correctly still treated as a real move (not a same-folder no-op), while
picking a folder whose recreated path resolves to the exact current run_dir
is still a no-op.

## Files touched

- `camxora_python/features/progress/views/progress_view.py` —
  `_change_run_folder()` now reconstructs `{picked}/{channel}/{date_album}`
  from the row's existing `run_dir` before invoking `RunFolderRecoveryWorker`;
  updated file-picker dialog copy to set the right "base folder" expectation.
- `camxora_python/tests/test_progress_view.py` — new
  `test_change_run_folder_recreates_channel_and_album_subfolders` and
  `test_change_run_folder_rejects_when_recreated_path_matches_current`.
- `camxora_python/pyproject.toml`, `camxora_python/resources/app-version.txt`,
  `camxora_python/tests/test_app_version.py` — version bump to 1.0.12.
- `CHANGELOG.md` (root, desktop) — `[1.0.12]` entry.

## Migration / deploy

Desktop-only fix; no platform_api or database changes. Ships in the v1.0.12
production installer. No sandbox/production backend deploy needed.

## Tests

- `pytest camxora_python/tests/test_progress_view.py -v` — 12 passed (2 new).
- `pytest camxora_python/tests/test_run_folder_recovery_worker.py -v` — 5
  passed (unaffected; that worker already treated its input path as the
  exact target, which is now correct given the caller fix).

## Follow-ups

- This was found immediately after the v1.0.11 fix (stale per-song
  output_dir) was verified working — the two bugs compounded: v1.0.11 fixed
  the endless-retry-on-old-path symptom, this v1.0.12 fixes the flat/wrong
  folder structure the recovery flow was writing the *new* files into. Both
  are needed together for the feature to behave like the rest of the
  pipeline.
- No server-side change was required this round, but if a second desktop
  entry point ever needs the same "pick a base, recreate the channel/album
  structure" behavior, consider moving the reconstruction logic into a
  small shared helper instead of duplicating it inline.
