# Export GLSL noise2 crash, refund reason clamp, preflight date guard

**Date:** 2026-08-04  
**Status:** implemented (pending desktop rebuild + sandbox API)  
**Surfaces:** `camxora_python` installer, `platform_api`

## Summary

User logs (`camxora-20260803`, `camxora-20260804`) showed every auto-video
export dying at OpenGL shader compile with:

`ERROR: 0:30: 'noise2' : overloaded functions must have the same return type`

Follow-on `POST /generation/video/refund` then returned **422** because the
client posted the full traceback as `reason` (API `max_length=500`), so failed
exports did not restore allowance. Separately, inverted music date ranges hit
`POST /batches/preflight` with `to_date must be on or after from_date`.

## Fix

1. **GLSL:** rename smoke helper `noise2` → `smoke_hash_noise2` so it does not
   collide with driver-reserved `noise2` overloads (`camxora_python` +
   `python_app` visualizer).
2. **Refund:** clamp reason to ≤500 chars on desktop (`video_billing`) and on
   API (`LocalVideoRefundRequest`) so old builds still refund.
3. **Preflight:** skip the API call when From/To are inverted; show a clear
   local reason instead of a 422.

## Files

- `camxora_python/visualizer/gpu_render.py`
- `python_app/visualizer/gpu_render.py`
- `camxora_python/features/video/lib/video_billing.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/tests/test_video_billing_refund_reason.py`
- `platform_api/routers/generation.py`
- `platform_api/tests/test_local_video_refund_reason.py`
