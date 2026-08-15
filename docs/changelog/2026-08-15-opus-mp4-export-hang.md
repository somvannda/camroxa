# Opus-in-MP4 `.mp3` no longer hangs the export queue

**Date:** 2026-08-15  
**Surfaces:** `camxora_python` (desktop)  
**Branch:** `bugfix/opus-mp4-export-queue`

## Summary

A playable Suno file saved as `.mp3` can be **Opus audio inside an MP4/M4A
container** (`ftyp isom`, handler `soun`). Windows Explorer still shows
“MP3 File” and media players play it to the end. Camxora’s analyzer used
mpg123/soundfile (MPEG-only) then **librosa with no timeout**, which hung
overnight and kept `PipelineAutomationService.is_busy()` true so every later
Start Export showed “Video pipeline is already running.”

## Product impact

- Those tracks export instead of freezing the app (ffmpeg decode).
- One bad track is retried **3 times**, then skipped; the rest of the album
  continues.
- After retries are exhausted, auto-video **starts the next ready album**
  instead of blocking the whole queue. Manual Start Export still works.

## Technical impact

- `sniff_audio_container` reads magic bytes; ISO-BMFF never calls librosa.
- `_load_mono_waveform` / duration probe use ffmpeg/ffprobe for that container.
- Librosa fallback has a 45s timeout.
- `export_one_track_with_retries` (3 attempts) then skip.
- `defer_export_run` + `select_next_auto_video_candidate(skip_keys=…)` so
  auto-video moves to the next run.

## Files touched

- `camxora_python/visualizer/audio.py`
- `camxora_python/features/video/workers/pipeline_export_worker.py`
- `camxora_python/features/video/lib/export_run_defer.py`
- `camxora_python/features/video/lib/desktop_video_automation.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/shared/services/video_pipeline_coordinator.py`
- `camxora_python/tests/test_audio_iso_bmff_decode.py`
- `camxora_python/tests/test_export_track_retries.py`
- `camxora_python/tests/test_desktop_video_automation.py`
- Root `CHANGELOG.md`

## Migration / deploy

Ships in the rebuilt **1.3.0** installer (`CamxoraSetup-1.3.0.exe`). Same
version stamp — already-installed 1.3.0 does not force-update itself; run
Setup again. Until then: Quit Camxora (end both `Camxora.exe` if hung).
Existing Opus-named `.mp3` files are real audio; export can decode them.

Library scan (2026-08-15): 3,327 `.mp3` files under `F:\Suno`, `E:\SUNO`,
`F:\Bass Ignition`, and AppData `Media\Suno`. **3,313 MPEG/ID3**, **8 Opus-in-MP4**
(4 unique tracks × F: + AppData copy), **6 pytest stubs**. No Ogg/FLAC/WebM/AAC
`.mp3` names in this library. Downloads always write CDN bytes to a `.mp3` path.

## Tests

- `pytest camxora_python/tests/test_audio_iso_bmff_decode.py camxora_python/tests/test_export_track_retries.py camxora_python/tests/test_desktop_video_automation.py camxora_python/tests/test_audio_duration_probe.py camxora_python/tests/test_audio_analyzer_progress.py -q`

## Follow-ups

- Optional: persist skipped-track sidecars across app restarts (defer is
  in-memory for 6 hours).
- Download path now prefers `{id}.mp3` and refuses to save Opus-in-MP4
  (see `docs/changelog/2026-08-15-suno-prefer-real-mp3.md`).
