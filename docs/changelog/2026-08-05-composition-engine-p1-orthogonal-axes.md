# Composition Engine P1 — orthogonal axes

**Branch:** `feature/composition-engine-p0-schema`  
**Date:** 2026-08-05

## Summary

Spectrum / particles / lighting / background axes are independently applyable.
Preset buttons set shape (or type) as convenience patches without clearing
material / animation / behavior. Legacy `style` still aliases to
`composition.spectrum.shape`.

## Changes

- `camxora_python/features/video/lib/composition_axes.py` — axis + convenience APIs
- `composition_scene_contract.py` — preserve orthogonal axes on legacy re-project
- `spectrum_style_registry.py` — preset apply attaches composition shape
- `docs/COMPOSITION_ENGINE_P1_ORTHOGONAL_AXES.md`

## Verify

```text
pytest camxora_python/tests/test_composition_scene_contract.py camxora_python/tests/test_composition_axes_p1.py camxora_python/tests/test_spectrum_inspector.py -q
```
