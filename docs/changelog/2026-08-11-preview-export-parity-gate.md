# Preview vs export parity gate

**Date:** 2026-08-11  
**Status:** implemented (desktop)  
**Branch:** `bugfix/preview-export-parity-gate`

## Summary

Manual (and warm-preview pipeline) export now **hard-blocks** when live preview
renderer JSON and export renderer JSON diverge on visual focus keys. Export also
samples lightning on a fixed ~60 Hz timeline with **per-layer** flash floors so
encode FPS no longer forces every bolt on when only one layer peaked. Empty
spectrum instance layers fall back to top-level `layers` only (never factory
default rings).

## Behavior

1. Before Manual Export encode: flush deferred preview timer + spectrum instance
   layers, rebuild export scene, compare `preview.template` vs export template.
2. On mismatch: one automatic resync (`set_template` from export dict) and
   re-compare; if still unequal → block track, notify, write
   `%client_logs%/video_parity/parity-mismatch-*.json`.
3. No warm GPU preview → warn and continue (draft JSON only).
4. Lightning export: `sample_lightning_layer_peaks_over_interval` +
   `flash_overrides_by_layer` (sparse).

## Files

- `camxora_python/features/video/lib/preview_export_parity.py`
- `camxora_python/features/video/services/in_process_export.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/features/video/lib/lightning_render.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/tests/test_preview_export_parity.py`
- `docs/changelog/2026-08-11-preview-export-parity-gate.md`
- `CHANGELOG.md`
