# App-owned run paths + Progress download missing MP3s

**Date:** 2026-08-06  
**Surfaces:** `camxora_python` (desktop)  
**Branch:** `fix/app-owned-run-paths-and-missing-mp3`

## Summary

Desktop is the authority for where MP3s land on disk. API absolute `run_dir`
values are treated as relative keys (`channel/date_album`) under this machine's
Suno root. Progress gains **Download missing MP3s (N)** for the row's role only.

## Product

- Open Run Folder / Progress local overlays always use the remapped local folder.
- Right-click **Download missing MP3s (N)** when URL-ready tracks are absent on disk.
- Reuses `POST /music/downloads/batch-redownload-plan` (Suno URL + Backblaze fallback).
- Does not re-draft or re-request Suno; **Retry Failed Suno** stays for real failures.
- Change Run Folder rebuilds `{channel}/{date_album}` via `run_key_from_path`.
- Category image samples = VPS packs only (no local settings folder fallback).
- Done/Completed/YouTube Progress rows: no Continue/Stop; keep Open + Change Run Folder;
  Force Regenerate/Rebuild remain for explicit re-run.
- Progress Music % / counters: disk role MP3 count when run folder is scannable (not
  API `downloaded_*` flags alone).

## Technical

### Desktop
- `run_key_from_path` + overlay `local_run_dir_for_disk` rewrite of `meta.run_dir`
- `shared/lib/missing_mp3.py` — count/filter helpers (disk-first)
- `MissingMp3DownloadWorker` — missing-only download + `sync_music_downloads`
- Stop pushing absolute media roots into account settings (`ensure_workspace_defaults` /
  `hydrate_local_suno_output_dir`)
- Change Run Folder sends `persist_batch_run_dir=true`; missing-MP3 sync does not
- Progress overlay: when run folder is scannable, `meta.saved` / Music % = role MP3
  count on disk; API `downloaded_*` is ignored for those counters (terminal /
  pipeline_complete / missing folder still preserved)

### Platform API (permanent)
- `normalize_run_key` / `plan_relative_run_directories` — store only `channel\date_album`
- Batch create / assign / download sync / local progress sync normalize before write
- Legacy absolute rows still work: key is stripped from trailing segments; desktop joins
  local Suno root
- No DB migration (same `ok_run_dir` columns, portable values)
- Category sample rotation: VPS packs only (no `imageBgSamples` fallback)
- Soft-heal of `batches.ok_run_dir` gated on `persist_batch_run_dir` (role-scoped)

## Tests

- `pytest camxora_python/tests/test_missing_mp3.py -q`
- `pytest camxora_python/tests/test_missing_mp3_download_worker.py -q`
- `pytest camxora_python/tests/test_device_workspace_paths.py -q`
- `pytest camxora_python/tests/test_progress_local_overlay.py -q`
- `pytest platform_api/tests/test_run_directory_planner.py -q`
- `pytest platform_api/tests/test_batch_service.py -k run_dir -q`
