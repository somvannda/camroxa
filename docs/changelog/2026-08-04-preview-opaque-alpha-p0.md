# Preview opaque alpha (REQ-P0) — see-through hotfix

**Date:** 2026-08-04  
**Status:** implemented (desktop; restart required)  
**Branch:** `bugfix/preview-p0-opaque-alpha`  
**Spec:** [`docs/PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md`](../PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md) P0  
**Playlist glass:** **not** restored (standalone call-site / alpha-lock only)

## Summary

On some GPUs (AMD iGPU / NVIDIA desktop GL), soft glow and additive draws wrote
framebuffer **alpha &lt; 1** into the `QOpenGLWidget` FBO. With the frameless
window’s `WA_TranslucentBackground`, Windows composited those pixels as real
transparency — users saw the **desktop through the preview**.

This hotfix restores Alpha_Lock on preview spectrum / particles / lightning and
forces opaque alpha at the end of each `paintGL`. It does **not** reintroduce
playlist glass polish that was excluded in the 1.0.19 ship cut (`1a68a91`).

## Changes

| REQ | Change |
|-----|--------|
| P0.1 | Spectrum glow/additive/normal call sites → `_blend_additive()` / `_blend_normal()` |
| P0.2 | Particle styled quads use `blend_rgb_*_opaque_alpha` |
| P0.3 | Lightning preview path uses opaque-alpha blends (`opaque_framebuffer_alpha=True` default) |
| P0.4 | End of `paintGL`: clear alpha only to 1 (RGB untouched); no `grabFramebuffer` |
| P0.5 | Verification matrix below (fill GPU results when available) |
| P0.6 | This changelog + Unreleased note; playlist excluded |

## Files

- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/features/video/lib/lightning_render.py`
- `camxora_python/tests/test_preview_opaque_alpha.py`
- `docs/changelog/2026-08-04-preview-opaque-alpha-p0.md`
- `CHANGELOG.md`

## Verification matrix (REQ-P0.5)

| Case | Window | Template | Expected | Result |
|------|--------|----------|----------|--------|
| M1 | Windowed (rounded) | Spectrum glow high | Opaque preview; glow visible | _pending local/GPU_ |
| M2 | Maximized | Same | Opaque | _pending_ |
| M3 | Windowed | Glow + particles + lightning | Opaque | _pending_ |
| M4 | Windowed | Glow/particles off | Opaque clear/dark content | _pending_ |
| M5 | Windowed | Text overlays present | Opaque to desktop (overlays may look translucent *in* the video) | _pending_ |

Record GPU/driver strings when filling results.

## Tests

```bash
pytest camxora_python/tests/test_preview_opaque_alpha.py -q
```

## Support note

If see-through persists after this build, collect
`%LOCALAPPDATA%\Camxora\logs\` (and `preview-gl-diag.log` once P1 lands) plus
dxdiag Display tabs. P1 diagnostics are a separate follow-up.
