# Spectrum Glow Strength/Softness preview↔export parity

**Date:** 2026-08-11  
**Status:** implemented (desktop)  
**Branch:** `bugfix/preview-export-parity-gate`

## Summary

With Glow Strength/Softness at **0**, preview and export already matched. With glow
on, export wings looked much larger because export used
`moderngl.ADDITIVE_BLENDING` (`ONE, ONE`), which ignores source alpha, while live
preview uses alpha-weighted additive (`SRC_ALPHA, ONE`). Glow passes intentionally
use low alpha — full `ONE, ONE` made the extended glow tips read as opaque wings.

## Fix

- Export spectrum glow/screen blend uses `apply_spectrum_pass_blend` → same
  `SRC_ALPHA, ONE` (+ opaque alpha lock) as preview.
- Shared `build_spectrum_glow_pass_specs()` for Glow Strength/Softness tip
  extras on preview + export (and GPU bar prepass).

## Retest

1. Restart sandbox from the parity worktree (kill visualizer daemon too).
2. Set Glow Strength / Softness back above 0 on Bass Drive.
3. Manual Export and compare at the same timestamp.

## Files

- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/tests/test_spectrum_glow_preview_export_parity.py`
- `docs/changelog/2026-08-11-spectrum-glow-blend-parity.md`
- `CHANGELOG.md`
