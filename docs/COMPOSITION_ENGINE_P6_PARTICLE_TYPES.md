# Composition Engine P6 — particle types (20)

**Date:** 2026-08-05  
**Status:** Delivered  
**Code:** [`composition_particles.py`](../camxora_python/features/video/lib/composition_particles.py)

---

## Catalog (exactly 20)

### Canonical (13)

1. `dust` — Dust  
2. `snow` — Snow  
3. `rain` — Rain  
4. `fire` — Fire  
5. `smoke` — Smoke  
6. `magic` — Magic  
7. `electric` — Electric  
8. `stars` — Stars  
9. `bubbles` — Bubbles  
10. `ash` — Ash  
11. `confetti` — Confetti  
12. `leaves` — Leaves  
13. `sparkles` — Sparkles  

### Fill (7)

14. `embers` — Embers  
15. `petals` — Petals  
16. `glitter` — Glitter  
17. `smoke_rings` — Smoke Rings  
18. `energy_orbs` — Energy Orbs  
19. `pixel_dust` — Pixel Dust  
20. `feather_drift` — Feather Drift  

Each type is a **recipe** (GPU-safe `variant` ∈ classic/bokeh/soap/dust + style/travel/spawn dials).  
`composition.particles.type` stays the semantic id; `particlesSettings.variant` is the GPU draw mode.

---

## Axes

| Field | Role |
|-------|------|
| `composition.particles.type` | Catalog id (this phase) |
| `composition.particles.behavior` | Shared Layer 4 id (P5) — independent |

---

## Apply

`apply_particle_type_to_template(template, type_id)`:

- Sets `composition.particles.type`  
- Patches `particlesSettings` recipe  
- **Does not** clear `behavior`  
- Preserves existing colors when already painted  

---

## Verify

```text
pytest camxora_python/tests/test_composition_particles_p6.py -q
```
