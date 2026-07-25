# Quiet Qt signal disconnect on coordinator stop

**Date:** 2026-07-25  
**Status:** implemented (desktop restart required)

## Summary

Closing the app logged `RuntimeWarning: libpyside: Failed to disconnect (None) from signal "succeeded(int)"` (and similar for `failed`) from `progress_local_sync_coordinator.stop`. Quit-safety code called `signal.disconnect()` on every of `succeeded` / `failed` / `finished`, including signals that were never connected on that worker.

## Product impact

- **Before:** Harmless but noisy PySide warnings on quit.
- **After:** Coordinators disconnect only the slots they connected (or use a quiet helper); no disconnect warnings.

## Technical impact

- New `shared/lib/qt_signals.py` (`disconnect_quietly` / `disconnect_worker_signals`).
- Updated stop paths: progress sync, music download, image sync, pipeline recovery, video pipeline.

## Files touched

- `camxora_python/shared/lib/qt_signals.py`
- `camxora_python/shared/services/progress_local_sync_coordinator.py`
- `camxora_python/shared/services/music_download_coordinator.py`
- `camxora_python/shared/services/image_output_sync_coordinator.py`
- `camxora_python/shared/services/pipeline_recovery_coordinator.py`
- `camxora_python/shared/services/video_pipeline_coordinator.py`
- `camxora_python/tests/test_qt_signals.py`
- `CHANGELOG.md`

## Migration / deploy

- Desktop restart only.

## Tests

- `pytest camxora_python/tests/test_qt_signals.py`

## Follow-ups

- None.
