# Export spectrum wing / reactivity parity (60 Hz analysis)

**Date:** 2026-08-11  
**Status:** implemented (desktop)  
**Branch:** `bugfix/preview-export-parity-gate`

## Summary

Export spectrum “wings” opened wider than live preview because export analyzed
audio at **30 Hz** while preview uses **60 Hz** (`load_audio_analyzer(..., fps=60)`).
Different STFT hops plus half as many `smooth_fft_envelope` steps made bars read
hotter/wider even when JSON matched.

## Fix

- Default export `ANALYSIS_FPS` is **60** (same as preview).
- Reused preview analyzers force indexing from `analyzer.fps`.
- Template react gain prefers `inputGain` then `sensitivity` (matches preview).
- Optional escape hatch: `CAMXORA_EXPORT_ANALYSIS_FPS=30` for faster cold analysis
  (accepts WYSIWYG drift).

## Files

- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/tests/test_export_spectrum_analysis_fps.py`
- `docs/changelog/2026-08-11-export-spectrum-60hz-analysis.md`
- `CHANGELOG.md`
