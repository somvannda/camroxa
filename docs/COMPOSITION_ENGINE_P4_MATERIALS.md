# Composition Engine P4 — spectrum materials (20)

**Date:** 2026-08-05  
**Status:** Delivered  
**Code:** [`composition_materials.py`](../camxora_python/features/video/lib/composition_materials.py)

---

## Catalog (exactly 20)

### Canonical (12)

1. `neon` — Neon  
2. `glass` — Glass  
3. `crystal` — Crystal  
4. `electric` — Electric  
5. `fire` — Fire  
6. `ice` — Ice  
7. `metal` — Metal  
8. `liquid` — Liquid  
9. `plasma` — Plasma  
10. `gold` — Gold  
11. `hologram` — Hologram  
12. `carbon` — Carbon  

### Fill (8)

13. `chrome` — Chrome  
14. `matte` — Matte  
15. `velvet` — Velvet  
16. `obsidian` — Obsidian  
17. `iridescent` — Iridescent  
18. `latex` — Latex  
19. `frosted_glass` — Frosted Glass  
20. `wireframe` — Wireframe  

Materials are **look packs** (`glow`, `blur`, `blend_mode`, `opacity`, `fillCircle`, optional `barWidth`) — not separate shape assets.

---

## Apply

`apply_spectrum_material_to_template(template, material_id)`:

- Sets `composition.spectrum.material`
- Patches layer look keys only  
- **Does not** change `shape`, `pathMode`, `curved`, `mirrored`, or palette colors  

Proved: Neon Circle / Glass Circle / Fire Circle / Plasma Circle share shape `circle`.

---

## Verify

```text
pytest camxora_python/tests/test_composition_materials_p4.py -q
```
