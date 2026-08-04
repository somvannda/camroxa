# Preview P4.3 — export HDR bloom parity

**Date:** 2026-08-04  
**Status:** implemented (desktop; same flag as P4.2, default **off**)  
**Branch:** `bugfix/preview-p4-export-parity`  
**Spec:** [`docs/PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md`](../PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md) REQ-P4.3  
**Depends on:** P4.2 (`bugfix/preview-p4-hdr-bloom`)

## Summary

Video export (`run_gpu_render`) and `render_preview_png` share the preview HDR
bloom/tonemap path when `CAMXORA_PREVIEW_HDR_BLOOM=1`. Flag off keeps the legacy
`prog_post` bloom/RGB-split look (golden behavior preserved).

Tolerance: with the flag on, preview and export use the same
`PreviewHdrBloomPass` + `bloom_params_from_template` contract (Reinhard + opaque
alpha). Soft-alpha glow geometry still differs slightly by path; bloom post is
aligned.

## Acceptance

| # | Criterion | Status |
|---|-----------|--------|
| A1 | Flag on → preview vs export same bloom contract | Shared `hdr_bloom` + compose helper |
| A2 | Flag off → prior export `prog_post` path | `_compose_scene_post_to_out` legacy branch |

## Files

- `camxora_python/visualizer/hdr_bloom.py` (`scene_tex` + `bloom_params_from_template`)
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/preview_widget.py` (shared params helper)
- `camxora_python/tests/test_preview_hdr_bloom.py`
- `docs/changelog/2026-08-04-preview-p4-export-parity.md`
- `CHANGELOG.md`
