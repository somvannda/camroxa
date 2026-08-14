# Regenerate missing / broken / selected MP4s

**Date:** 2026-08-14  
**Surfaces:** `camxora_python` (desktop)  
**Branch:** `release/desktop-1.2.6` (version stamp **1.3.0**)

## Summary

Users no longer restart the whole pipeline when one MP3 was late, one MP4 is a
stub, or an export is corrupt. Progress can re-export only the bad track(s) from
existing MP3s, and merge helpers inspect the run folder first so a broken file is
rebuilt before concat.

MP4s live on the user’s Windows disk. This is a **desktop helper**, not a
platform_api re-encode endpoint.

## Product impact

- **Regenerate missing/broken MP4s** — re-exports only tracks whose MP4 is
  missing, tiny (&lt;50KB), corrupt, or truncated. Bills those tracks only.
  Album titles stay complete.
- **Regenerate one track** — deletes that track’s MP4 and re-exports it even if
  it already looks healthy.
- **Force Regenerate MP4** — still wipes every branch export and re-does all
  tracks (unchanged).
- **Start Merging / Continue Progress** — if any track needs re-export, those
  MP4s are rebuilt first, then merge runs. Missing audio tells the user to
  **Download missing MP3s** instead of billing an export.
- Start Export on a half-finished album no longer bills the tracks that already
  have a usable MP4.

## Technical impact

- `inspect_run_export_health` classifies each MP3 → MP4 as
  `ok | missing_mp3 | missing_mp4 | tiny | corrupt | truncated | spec_mismatch`
- Repair export passes only unhealthy paths to the worker; `album_mp3_paths`
  keeps the full title list
- Merge inspects without current FPS/resolution filters (same as 1.2.6 concat
  hardening). Spec mismatch is not auto-repaired; use Force Regenerate or
  Regenerate one track
- `start_manual_merge(..., skip_repair=True)` avoids a repair↔merge loop when
  health is already clean
- Partial repair sets `match_export_specs=False` so the other album files are
  not dropped from concat

## Files touched

- `camxora_python/features/video/lib/export_track_health.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/features/video/workers/pipeline_export_worker.py`
- `camxora_python/shared/services/video_pipeline_coordinator.py`
- `camxora_python/features/progress/lib/continue_progress.py`
- `camxora_python/features/progress/views/progress_view.py`
- `camxora_python/features/progress/widgets/operational_rows_card.py`
- `camxora_python/tests/test_export_track_health.py`
- `camxora_python/tests/test_continue_progress.py`

## Migration / deploy

Desktop-only. Ship `CamxoraSetup-1.3.0.exe` with Force update. No API/sandbox
deploy. No production deploy unless asked.

## Tests

Automated:

- `camxora_python/tests/test_export_track_health.py`
- `camxora_python/tests/test_continue_progress.py`
- `camxora_python/tests/test_pipeline_merge.py`
- `camxora_python/tests/test_app_version.py` (expects 1.3.0)

### Smoke scenarios (manual, before publishing 1.3.0)

Use a 10-track album with Auto Merge on, custom Suno folder, and a known-good
background + template.

| # | Setup | Action | Expect |
|---|-----|-----|-----|
| 1 | 9 good MP4s, 1 MP3 with no MP4 | Regenerate missing/broken MP4s | Exports **1** track; bills 1; other MP4s untouched |
| 2 | Same as 1 | Continue Progress | Same as 1, then merge if Auto Merge on |
| 3 | Same as 1 | Start Merging Video | Regenerates the missing MP4, then writes `MERGED_*.mp4` |
| 4 | 10 MP4s, one is a 0–20KB stub | Regenerate missing/broken | Replaces only the stub |
| 5 | 10 MP4s, one renamed/truncated (plays but shorter than MP3) | Regenerate missing/broken | Re-exports that track |
| 6 | 10 MP4s, one is random bytes / unreadable | Regenerate missing/broken | Re-exports that track |
| 7 | All 10 MP4s healthy | Regenerate missing/broken | Status: nothing to regenerate; no bill |
| 8 | All 10 healthy | Regenerate one track → pick track 4 | Deletes track 4 MP4, re-exports only that file; titles still list 10 songs |
| 9 | All 10 healthy | Force Regenerate MP4 | Deletes all branch MP4s + MERGED; re-exports all 10; bills 10 |
| 10 | 10 MP3s, **0** MP4s | Start Export | Exports all 10 (all are missing) |
| 11 | 10 MP3s, 0 MP4s | Start Merging | Regenerates all missing MP4s, then merge (needs ≥2 usable files) |
| 12 | 9 MP3s on disk, 1 MP3 missing | Regenerate missing/broken / Merge | Does not bill the missing audio; prompt to **Download missing MP3s** |
| 13 | Nested `channel/album/channel/album` with the real MP4s inside | Merge / repair | Uses the nested folder (1.2.7 hardening) |
| 14 | Reel branch (`*_REEL.mp4`) with one missing reel | Repair on reel | Writes `*_REEL.mp4`, does not clobber long MP4 |
| 15 | Repair 1 track then merge | After export succeeds | Concat uses **all** album MP4s, not only the repaired one |
| 16 | Pipeline already exporting | Repair / Merge / one-track | “already running”; Cancel then retry |
| 17 | Cancel mid-repair | Cancel Active Export/Merge | Stops; remaining bad files still flagged; retry repair only those |
| 18 | Merge of 9/10 then repair #10 | Continue after failed merge | Re-exports #10, then `MERGED_*.mp4` exists |
| 19 | Older FPS album, all files healthy vs each other | Start Merging | Merges without re-exporting for today’s FPS (spec mismatch is not auto-repair) |
| 20 | Custom Suno dir after install | Preferences | Path still custom (1.2.6 installer regression) |
| 21 | Footer / update | Install 1.3.0 over 1.2.6 | Footer **1.3.0**; Force update from 1.2.6 |
| 22 | Billing | Repair 1 of 10 | Video credit count is **1**, not 10; merge still 1 merge credit |

## Follow-ups

- Progress Replace/Export (P3) image-replace → re-export is a separate initiative.
- No server-side MP4 rewrite; helpers cannot fix files that are not on this PC.
