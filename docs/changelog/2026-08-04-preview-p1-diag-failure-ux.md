# Preview P1 — GL diagnostics + opaque failure UX

**Date:** 2026-08-04  
**Status:** implemented (desktop; restart required)  
**Branch:** `bugfix/preview-p1-diag-failure-ux` (on top of P0 opaque-alpha)  
**Spec:** [`docs/PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md`](../PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md) P1

## Summary

Support can diagnose see-through / missing-preview reports via AppData logs.
When OpenGL init or repeated FBO bind fails, the preview shows an **opaque**
error panel (never a transparent hole through the frameless window).

## REQ coverage

| REQ | Delivery |
|-----|----------|
| P1.1 | `preview_diag.py` → `%LOCALAPPDATA%\Camxora\logs\preview-gl-diag.log`; mirrors to `camxora-*.log` as `[preview-gl]` |
| P1.2 | Opaque `#0a0e27` failure label + message pointing at diag log; stage disables transport |
| P1.3 | `_use_qt_framebuffer()` returns bool; logs bind failures; after **30** consecutive failures shows same opaque overlay |
| P1.4 | Support pack + QA checklist below |

## Support pack (send with bug reports)

1. Camxora **app version** (footer badge / About)
2. `%LOCALAPPDATA%\Camxora\logs\preview-gl-diag.log`
3. `%LOCALAPPDATA%\Camxora\logs\camxora-*.log` (same day)
4. **dxdiag** → Display tabs (GPU name + driver version)
5. Windowed vs maximized when the issue happens
6. Template features on: spectrum glow / particles / lightning / text overlays

## QA checklist (includes P0 matrix)

| Case | Window | Template | Expected |
|------|--------|----------|----------|
| M1 | Windowed | Spectrum glow high | Opaque preview; glow visible |
| M2 | Maximized | Same | Opaque |
| M3 | Windowed | Glow + particles + lightning | Opaque |
| M4 | Windowed | Glow/particles off | Opaque content |
| M5 | Windowed | Text overlays | Opaque to desktop |
| F1 | Any | Force GL init failure (dev) | Opaque error panel + log lines; no desktop hole |
| F2 | Any | Healthy GPU | `preview-gl-diag.log` contains `initializeGL ok` after opening Video |

## Files

- `camxora_python/visualizer/preview_diag.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/features/video/widgets/stage_panel.py`
- `camxora_python/features/video/lib/video_workspace_diagnostics.py`
- `camxora_python/tests/test_preview_gl_diag.py`
- `camxora_python/tests/test_video_workspace_diagnostics.py`
- `docs/changelog/2026-08-03-preview-gl-diag-logging.md`
- `docs/changelog/2026-08-04-preview-p1-diag-failure-ux.md`
- `CHANGELOG.md`

## Tests

```bash
pytest camxora_python/tests/test_preview_gl_diag.py camxora_python/tests/test_preview_opaque_alpha.py -q
```
