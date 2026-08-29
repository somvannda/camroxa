# 2026-08-28 — Desktop Image studio restyle

Local desktop only. Sandbox and production were not deployed.

## Summary

The live `camxora_python` Image page keeps the existing information architecture (controls + queue on the left, background/thumbnail previews on the right) and the same widget positions. Only the visual chrome now matches the Create studio design system.

Queue filters, prompts, manual generation, retry/regenerate, and preview bindings stay in place.

## Product impact

- Same studio look as Create / Music: `#071426` canvas, `#0D1B2E` panels, 6px radii, 28px dates and combos
- In-page `CreateHeader` replaces the generic shell page header
- Compact Secondary buttons with Lucide icons
- Queue table uses Create table chrome

## Technical impact

- Image QSS is `studio_workspace_qss("image_workspace")` plus a thin extras sheet
- `StudioDateEdit` / `StudioComboBox` replace shell controls in the same slots
- Existing test hooks (`_loading_card`, `_controls_card`, `_background_preview`) are unchanged

## Files touched

- `camxora_python/features/image/`
- `camxora_python/app/application.py`
- `camxora_python/tests/test_image_view.py`
- `camxora_python/tests/test_application.py`
- `CHANGELOG.md`
- `docs/changelog/2026-08-28-desktop-image-studio-ui.md`

## Migration/deploy

None. Desktop UI only.

## Tests

- `python -m pytest camxora_python/tests/test_image_view.py camxora_python/tests/test_application.py::test_profile_hides_generic_shell_page_header -q`
