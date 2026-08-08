# Image page prompt character cap (UI)

## Summary

Desktop Image page Background / Thumbnail prompt boxes enforce the same **5000**-character hard allowance as the platform API, with a live `current / 5000` counter.

## Product impact

- Typing or pasting past 5000 characters is truncated in the prompt editors.
- Counter turns red at the limit so users see why input stops growing.
- Matches API error: `Image prompt exceeds maximum length of 5000 characters.`

## Files touched

- `camxora_python/shared/lib/image_workspace.py`
- `camxora_python/features/image/widgets/controls_queue_card.py`
- `camxora_python/features/image/views/image_view.py`
- `camxora_python/tests/test_image_workspace.py`
