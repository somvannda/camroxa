# Export spectrum glow matches preview (WYSIWYG)

**Date:** 2026-08-11  
**Status:** implemented (desktop)  
**Branch:** `bugfix/preview-export-parity-gate`

## Summary

Live preview always draws up to two additive spectrum glow passes when a layer
has Glow &gt; 0. Export used to skip those passes on Fast/Balance for speed, so
Bass Drive–style wings looked shorter/tighter in the MP4 than on stage.

## Fix

- `export_glow_pass_limit`: Fast / Balance / Quality / Best Quality → **2**
  (same as preview).
- Only `very_fast` / `draft` still skip glow.
- Preview FFT frame indexing uses `analyzer.fps` (not a hardcoded 60) so seek
  catch-up stays aligned with the loaded analysis cache.

## Files

- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/tests/test_export_speed_quality.py`
- `docs/changelog/2026-08-11-export-spectrum-glow-wysiwyg.md`
- `CHANGELOG.md`
