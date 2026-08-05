# Composition Engine P1 — orthogonal axes

**Date:** 2026-08-05  
**Status:** Delivered on `feature/composition-engine-p0-schema`  
**Depends on:** P0 [`COMPOSITION_ENGINE_P0_SCENE_SCHEMA.md`](COMPOSITION_ENGINE_P0_SCENE_SCHEMA.md)  
**Code:** [`composition_axes.py`](../camxora_python/features/video/lib/composition_axes.py)

---

## 1. Goal

Split bundled presets into **independent JSON axes** so applying one field does not force another.

| Domain | Axes |
|--------|------|
| Spectrum | `shape` · `material` · `animation` |
| Particles | `type` · `behavior` |
| Lighting | `effect` · `trigger` |
| Background | `image` · `motion` · `atmosphere` |

Spectrum library entries are **geometry** (`shape`), not full effects.

---

## 2. Rules (exit criteria)

1. **Applying shape does not force a material** — `apply_spectrum_axes(..., shape=)` leaves `material` / `animation` unchanged.  
2. **Applying material does not change geometry id** — `apply_spectrum_axes(..., material=)` leaves `shape` unchanged.  
3. **Preset buttons are convenience patches** — `apply_spectrum_preset_convenience` / `build_spectrum_preset_template` set `shape` (from legacy style id / aliases) and **do not clear** existing material/animation.  
4. **Old templates load via aliases** — `style` → `composition.spectrum.shape`; re-project preserves material/animation/behavior already on `composition`.

---

## 3. API

```python
from features.video.lib.composition_axes import (
    apply_spectrum_axes,
    apply_particles_axes,
    apply_lighting_axes,
    apply_background_axes,
    apply_spectrum_preset_convenience,
    sync_legacy_aliases_from_composition,
)
```

Legacy sync (authoring → GPU aliases available today):

- `composition.spectrum.shape` → `style`  
- `composition.particles.type` → `particlesSettings.variant`  
- material / animation / behavior still authoring-only until P4/P5/P6

---

## 4. Verify

```text
pytest camxora_python/tests/test_composition_scene_contract.py camxora_python/tests/test_composition_axes_p1.py camxora_python/tests/test_spectrum_inspector.py -q
```
