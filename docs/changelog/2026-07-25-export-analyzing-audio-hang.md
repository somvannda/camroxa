# Fix export hang on Analyzing audio (dual-Xeon / 1050 Ti)

**Date:** 2026-07-25  
**Status:** implemented in v0.4.3 build; **hardware validation HELD** (see [`docs/FOLLOWUPS_DESKTOP_GPU_EXPORT.md`](../FOLLOWUPS_DESKTOP_GPU_EXPORT.md)) — prioritize production platform cutover first.

## Summary

On GTX 1050 Ti + dual Xeon E5 machines, Progress export reached “Creating OpenGL context” then stuck forever on “Analyzing audio” (GPU idle). Root cause: full-rate `librosa` STFT/beat_track with OpenBLAS spawning huge thread pools on dual-socket CPUs (livelock / multi-minute stall). Analysis now caps BLAS threads, uses 22.05 kHz, reports sub-steps, and low-tier GPUs force 1 export worker.

## Product impact

- **Before:** Export hangs at Analyzing audio; cancel only shows pygame banner noise.
- **After:** Status advances Loading → Spectrum → Onset → Beats → encoder; 1050 Ti cannot run 2 parallel GL exporters.

## Technical impact

- `visualizer/audio.py`: `ANALYSIS_SAMPLE_RATE=22050`, `threadpoolctl`/`OMP` caps, progress callback, beat_track via onset envelope.
- Audio analysis cache version → **2** (invalidates old native-rate caches).
- `resolve_pipeline_export_workers()` forces 1 on `low` GPU tier.

## Files touched

- `camxora_python/visualizer/audio.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/export_gpu_tier.py`
- `camxora_python/shared/services/audio_analysis_cache.py`
- `camxora_python/features/video/workers/pipeline_export_worker.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/features/video/lib/export_failure_log.py`
- Tests + version/changelog for **0.4.3**

## Migration / deploy

1. Build `CamxoraSetup-0.4.3.exe`
2. Install on 1050 Ti PC; footer **v0.4.3**
3. Start one Progress export; confirm Analyzing audio sub-steps then encoding

## Tests

- `pytest tests/test_audio_analyzer_progress.py tests/test_audio_analysis_cache.py tests/test_export_gpu_tier.py tests/test_export_failure_log.py`

## Follow-ups

- If still slow on very long tracks, consider analyzing before GL context create, or optional beat skip.
