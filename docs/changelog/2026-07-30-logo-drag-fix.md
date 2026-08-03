# Logo drag on Logo tab

**Date:** 2026-07-30  
**Status:** implemented (desktop local; full app restart required)

## Summary

Logo tab previously disabled all preview canvas edit modes, so dragging did nothing. Detached logos were also hard-pinned to frame center. Logo tab now enables logo position drag; attached mode still moves the shared spectrum+logo position, and detached mode uses `logoSettings.position` for free logo placement.

## Product impact

- **Before:** On Logo tab, drag did nothing; with Attach off the logo could not leave center.
- **After:** Open Logo → drag the logo on the preview. Attach on = logo+spectrum move together. Attach off = logo moves freely; spectrum stays on Spectrum-tab position.

## Technical impact

- `resolve_preview_edit_modes` returns a 5th `logo` flag.
- Preview mouse path + `logo_position_changed` signal.
- `resolve_spectrum_logo_centers` honors `logo_position` when detached.
- Draft/save: `logoPositionX` / `logoPositionY` → `logoSettings.position`.

## Files touched

- `camxora_python/features/video/lib/preview_edit_modes.py`
- `camxora_python/features/video/lib/logo_spectrum_bindings.py`
- `camxora_python/features/video/lib/video_template_draft.py`
- `camxora_python/features/video/lib/video_template_save.py`
- `camxora_python/features/video/lib/template_draft_domains.py`
- `camxora_python/features/video/widgets/stage_panel.py`
- `camxora_python/features/video/widgets/logo_inspector.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/tests/test_preview_edit_modes.py`
- `camxora_python/tests/test_spectrum_vivid_and_position.py`
- `docs/changelog/2026-07-30-logo-drag-fix.md`
- `CHANGELOG.md`

## Migration / deploy

Desktop-only. Fully restart the app.

## Tests

- `pytest camxora_python/tests/test_preview_edit_modes.py camxora_python/tests/test_spectrum_vivid_and_position.py`

## Follow-ups

- Optional Reset Center button on Logo inspector (spectrum already has one).
