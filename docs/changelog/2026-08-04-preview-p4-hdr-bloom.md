# Preview P4.2 — real HDR bloom + tonemap (preview)

**Date:** 2026-08-04  
**Status:** implemented (desktop; flag default **off**)  
**Branch:** `bugfix/preview-p4-hdr-bloom`  
**Spec:** [`docs/PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md`](../PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md) REQ-P4.2  
**Design:** [`docs/PREVIEW_HDR_BLOOM_DESIGN.md`](../PREVIEW_HDR_BLOOM_DESIGN.md)

## Summary

Preview can draw the scene into an offscreen float (or RGBA8 fallback) target,
run threshold → blur pyramid → upsample composite → Reinhard tonemap, then blit
SDR RGB into the Qt `QOpenGLWidget` FBO with **alpha = 1**. Soft-alpha glow
strokes remain; this is the CapCut-style bloom path behind a flag.

Default is unchanged look (`CAMXORA_PREVIEW_HDR_BLOOM` unset / `0`). Interactive
scrub (P2) skips the bloom pyramid and draws straight to the Qt FBO.

## Enable

```text
CAMXORA_PREVIEW_HDR_BLOOM=1
```

Optional template knobs under `effects.bloom` (`strength`, `opacity`, `threshold`,
`enabled`) tune the pass when the flag is on.

## Acceptance

| # | Criterion | Status |
|---|-----------|--------|
| A1 | Flag off → parity with pre-P4 | Code path skipped (default) |
| A2 | Flag on → brighter bloom, no See_Through | Tonemap writes alpha=1; P0 Alpha_Lock still runs |
| A3 | paintGL median &lt; 40ms mid GPU | Hitch logs; bloom skipped while scrubbing |

## Files

- `camxora_python/visualizer/hdr_bloom.py` (new)
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/tests/test_preview_hdr_bloom.py`
- `docs/changelog/2026-08-04-preview-p4-hdr-bloom.md`
- `CHANGELOG.md`

## Not included

- Export WYSIWYG parity (REQ-P4.3)
- Playlist glass / DistroKid / Qt RHI
