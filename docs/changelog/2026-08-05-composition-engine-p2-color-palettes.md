# Composition Engine P2 — color palettes (20)

**Branch:** `feature/composition-engine-p0-schema`  
**Date:** 2026-08-05

## Summary

Adds 20 named color palettes (12 canonical + 8 fill) and
`apply_color_palette_to_template` which paints Spectrum, Particles, Lighting,
Text, and Overlay colors while setting `composition.colorPalette`.

## Verify

```text
pytest camxora_python/tests/test_composition_color_palettes_p2.py -q
```
