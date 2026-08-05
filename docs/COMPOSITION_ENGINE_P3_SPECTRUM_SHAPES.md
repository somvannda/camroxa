# Composition Engine P3 — spectrum shapes (15)

**Date:** 2026-08-05  
**Status:** Delivered  
**Code:**  
- [`composition_spectrum_shapes.py`](../camxora_python/features/video/lib/composition_spectrum_shapes.py)  
- path geometry in [`_spectrum_fast.py`](../camxora_python/visualizer/_spectrum_fast.py)

---

## Catalog (exactly 15)

### Canonical (12)

1. `circle` — Circle  
2. `double_circle` — Double Circle  
3. `wave` — Wave  
4. `bars` — Bars  
5. `hexagon` — Hexagon  
6. `diamond` — Diamond  
7. `triangle` — Triangle  
8. `infinity` — Infinity  
9. `heart` — Heart  
10. `audio_ribbon` — Audio Ribbon  
11. `spiral` — Spiral  
12. `tunnel` — Tunnel  

### Fill (3)

13. `ring` — Ring  
14. `starburst` — Starburst  
15. `pillars` — Pillars  

These are **geometry** ids (`composition.spectrum.shape`), not materials.

---

## Apply

`apply_spectrum_shape_to_template(template, shape_id)`:

- Sets `composition.spectrum.shape`
- Patches `layers[]` path/geometry only  
- **Preserves** `material`, `animation`, `colorPalette`, and existing layer colors  
- Maps legacy `style` to a compatible draw mode (`orbit-spikes` / `aurora-ribbon`)

New `pathMode` values for preview/export: `triangle`, `diamond`, `hexagon`, `heart`, `infinity`, `spiral`, `tunnel`.

---

## Verify

```text
pytest camxora_python/tests/test_composition_spectrum_shapes_p3.py -q
```
