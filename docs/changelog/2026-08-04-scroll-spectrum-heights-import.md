# Fix export NameError: scroll_spectrum_heights not defined

**Date:** 2026-08-04  
**Status:** implemented (desktop production installer 1.0.20)  
**Branch:** `fix/scroll-spectrum-heights-import`  
**Surfaces:** `camxora_python` (GPU export / visualizer)

## Summary

GPU export crashed with `NameError: name 'scroll_spectrum_heights' is not defined`
because `gpu_render.py` called Raise Scroll’s helper without importing it. The
1.0.19 ship-cut revert of playlist glass dropped the import while leaving the
call sites. Restored the import (matching 1.0.18 / `latest-main-branch`) and
added a P5 ship-safety gate so P0–P4 merges cannot lose it again.

## Product impact

- **Before:** Spectrum-enabled export/preview worker aborted immediately
  (`Unhandled exception in script` / `run_entry` → `run_gpu_render`).
- **After:** Export proceeds; Raise Scroll (`frequencyScroll`) works when set.

## Technical impact

- Top-level and `run_gpu_render` local imports now include `scroll_spectrum_heights`.
- Regression test binds the symbol on `visualizer.gpu_render` and asserts call sites remain.
- `docs/PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md` gains **P5**
  (REQ-P5.1 / P5.2) — not a Vulkan/RHI phase.

## Files touched

- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/tests/test_spectrum_frequency_scroll.py`
- `docs/PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md`
- `docs/changelog/2026-08-04-scroll-spectrum-heights-import.md`
- `CHANGELOG.md`
- `camxora_python/pyproject.toml` (1.0.20)

## Migration / deploy

Desktop-only. Ship `CamxoraSetup-1.0.20.exe` production installer. No API / DB /
sandbox deploy.

## Tests

- `pytest camxora_python/tests/test_spectrum_frequency_scroll.py`

## Follow-ups

- Before merging `bugfix/preview-p0`…`p4` to a release line, re-check REQ-P5.1
  (those branches currently lack the import).
