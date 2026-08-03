# Preview drag: flush top/bottom edges for spectrum/logo/lightning

**Date:** 2026-08-03
**Status:** implemented (desktop v1.0.15)

## Summary

Preview drag clamped object centers with `margin_frac=0.06` (~6% inset on
each edge), so the spectrum bar could not reach the very top or bottom of
the preview. The flush-edge fix (`margin_frac=0.0`) already existed on
`feat/lightning-layers` (2026-07-30) but never landed on the desktop release
line — users still saw leftover space above/below the bar.

## Fix

In `camxora_python/visualizer/preview_widget.py`,
`clamp_template_offset_to_preview` default `margin_frac` is `0.0` so the
anchor center can sit flush on the frame edge. Export inherits whatever Y
drag saves — no separate export clamp.

## Files

- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/tests/test_preview_drag_clamp.py`
