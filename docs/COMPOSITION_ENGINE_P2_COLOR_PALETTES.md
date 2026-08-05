# Composition Engine P2 — color palettes (20)

**Date:** 2026-08-05  
**Status:** Delivered  
**Code:** [`composition_color_palettes.py`](../camxora_python/features/video/lib/composition_color_palettes.py)  
**Depends on:** P0 schema (`composition.colorPalette`), P1 axes

---

## Catalog (exactly 20)

### Canonical (12)

1. `cyberpunk` — Cyberpunk  
2. `synthwave` — Synthwave  
3. `festival` — Festival  
4. `edm` — EDM  
5. `dubstep` — Dubstep  
6. `future_bass` — Future Bass  
7. `sunset` — Sunset  
8. `aurora` — Aurora  
9. `galaxy` — Galaxy  
10. `fire` — Fire  
11. `ocean` — Ocean  
12. `monochrome` — Monochrome  

### Fill slots (8) → target 20

13. `midnight` — Midnight  
14. `neon_pink` — Neon Pink  
15. `tropical` — Tropical  
16. `industrial` — Industrial  
17. `candy` — Candy  
18. `blood_moon` — Blood Moon  
19. `arctic` — Arctic  
20. `gold_rush` — Gold Rush  

Each palette has `stops` (4 hex), `solid`, `accent`.

---

## Apply behavior

`apply_color_palette_to_template(template, palette_id)`:

| Domain | Written fields |
|--------|----------------|
| Spectrum | `layers[].color` gradient (+ `spectrumInstances`) |
| Particles | `color`, `reactColor`, `paletteColors`, `colorMode=palette` |
| Lighting | `lightningLayers[].color` |
| Text | `textOverlays`, `albumText` / `titleText` style |
| Overlay | `overlaySettings.items[].color` when present |
| Composition | `composition.colorPalette = id` |

Presets should reference palette **ids**, not one-off hex.

---

## Verify

```text
pytest camxora_python/tests/test_composition_color_palettes_p2.py camxora_python/tests/test_composition_axes_p1.py -q
```
