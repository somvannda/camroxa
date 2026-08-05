# Composition Engine P5 — animation behaviors (12)

**Date:** 2026-08-05  
**Status:** Delivered  
**Code:** [`composition_animations.py`](../camxora_python/features/video/lib/composition_animations.py)

---

## Catalog (exactly 12 — Layer 4)

1. `pulse` — Pulse  
2. `bounce` — Bounce  
3. `rotate` — Rotate  
4. `expand` — Expand  
5. `contract` — Contract  
6. `ripple` — Ripple  
7. `wave` — Wave  
8. `twist` — Twist  
9. `elastic` — Elastic  
10. `fade` — Fade  
11. `flash` — Flash  
12. `breathing` — Breathing  

Shared vocabulary — the same id attaches to Spectrum, Logo, Overlay, and Particles.

---

## Axes

| Object | Field |
|--------|--------|
| Spectrum | `composition.spectrum.animation` |
| Logo | `composition.logo.animation` |
| Overlay | `composition.overlay.animation` |
| Particles | `composition.particles.behavior` (same ids) |

---

## Apply

`apply_animation_behavior_to_template(template, behavior_id, targets=…)`

- Default targets: spectrum + logo + overlay + particles  
- Spectrum recipe patches audio dials only (not shape / material / path)  
- Logo recipe patches `logoSettings` motion / spin  
- Overlay / particles store the shared id on authoring + legacy stub fields  

`apply_spectrum_animation_to_template(template, behavior_id)` — spectrum-only convenience.

---

## Verify

```text
pytest camxora_python/tests/test_composition_animations_p5.py -q
```
