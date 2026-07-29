# Spectrum rabbit ears (Inward) fix

**Date:** 2026-07-29  
**Status:** implemented (desktop)  
**Branch:** `fix/spectrum-vivid-position-audio`

## Summary

Inward (rabbit ears) Bar Growth was being overwritten back to Outward whenever the workspace hydrated or a style session preset was applied, because style geometry alignment forced `gravity` from the recipe (always `normal`). Selecting Inward on a linear layer also looked broken because rabbit ears need a semicircle.

## Product impact

- **Before:** Choosing Inward often snapped back to Outward, or did nothing useful on Linear form.
- **After:** Inward sticks. On Linear, picking Inward auto-switches that layer to Circle Raise (180°) so the classic rabbit-ears look appears.

## Technical impact

- `align_spectrum_layers_to_style_geometry` no longer overwrites user gravity.
- Layer editor emits `gravity` + `curved`/`mirrored` together for rabbit ears.
- Structural layer patches rebind inspectors immediately so Circle Form updates.

## Files touched

- `camxora_python/features/video/lib/spectrum_style_registry.py`
- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/tests/test_spectrum_gravity.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-spectrum-rabbit-ears-fix.md`

## Migration / deploy

- Desktop-only. Restart app. Re-select **Inward (rabbit ears)** on the layer if needed.

## Tests

- `pytest camxora_python/tests/test_spectrum_gravity.py`

## Incident

- **Video page crash:** `NameError: name 'style' is not defined` in `spectrum_inspector.bind_draft` after rabbit-ears UI cleanup removed the local `style` assignment but left `findData(style)`.
- **Fix:** restore `style = str(draft.get("style") or "orbit-spikes")` at the start of `bind_draft`.
- **Verification:** Video workspace can bind inspectors / patch layers without traceback.
