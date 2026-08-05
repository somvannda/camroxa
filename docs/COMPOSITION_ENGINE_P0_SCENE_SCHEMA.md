# Composition Engine — P0 Scene Schema Freeze

**Date:** 2026-08-05  
**Status:** Frozen for P0 (authoring contract)  
**Branch:** `feature/composition-engine-p0-schema`  
**Code:** [`camxora_python/features/video/lib/composition_scene_contract.py`](../camxora_python/features/video/lib/composition_scene_contract.py)  
**Parent:** [`VISUALIZER_COMPOSITION_ENGINE_ALIGNMENT.md`](VISUALIZER_COMPOSITION_ENGINE_ALIGNMENT.md)

---

## 1. Purpose

Lock **exact JSON keys** for the composition architecture tree so later phases (shapes, materials, palettes, …) do not invent conflicting field names.

- **Authoring source of truth (new):** top-level `composition` on saved templates  
- **GPU source of truth (unchanged):** legacy fields (`backgroundSettings`, `style`, `layers`, `particlesSettings`, `effects`, …)  
- P0 **projects** legacy → `composition` and normalizes stubs. P0 does **not** require the GPU to read `composition`.

---

## 2. Layer 1 — Scene objects (never change)

| Object | `composition` path | Notes |
|--------|-------------------|--------|
| Background | `composition.background` | Image + motion + atmosphere |
| Spectrum | `composition.spectrum` | Shape + material + animation |
| Logo | `composition.logo` | Enabled + animation |
| Text | `composition.text` | Typography only (album / title / captions) |
| Overlay | `composition.overlay` | Top composites (frames / stickers / watermarks) — **not** Text |
| Particles | `composition.particles` | Type + behavior |
| Lighting | `composition.lighting` | Effect + trigger |
| Camera | `composition.camera` | Behavior |
| Audio | `composition.audio` | Mapping façade (filled in P11) |

---

## 3. Frozen architecture tree (exact keys)

```json
{
  "composition": {
    "version": 1,
    "colorPalette": null,
    "background": {
      "image": null,
      "motion": "static",
      "atmosphere": "none"
    },
    "spectrum": {
      "shape": "none",
      "material": "none",
      "animation": "none"
    },
    "logo": {
      "enabled": true,
      "animation": "none"
    },
    "text": {
      "enabled": false
    },
    "overlay": {
      "enabled": false,
      "animation": "none",
      "items": []
    },
    "particles": {
      "type": "none",
      "behavior": "none"
    },
    "lighting": {
      "effect": "none",
      "trigger": "none"
    },
    "camera": {
      "behavior": "none"
    },
    "postProcessing": {
      "effects": []
    },
    "audio": {
      "mapping": {}
    }
  }
}
```

Stub sentinel for “not set / not chosen yet”: string `"none"` (or `null` only for `colorPalette` and `background.image`).

---

## 4. Legacy key map (GPU / today’s template)

| Composition path | Legacy path |
|------------------|-------------|
| `composition.background.image` | `previewBackground` / workspace background / CLI `--background` |
| `composition.background.motion` | `backgroundSettings.motionMode` (`none`↔`static`, `zoom`↔`slow_zoom`, `vibrate` retained) |
| `composition.background.atmosphere` | `effects.smoke` (+ future atmosphere presets in P9) |
| `composition.spectrum.shape` | `style` (+ `layers[]`) |
| `composition.spectrum.material` | **new** (P4) — stub `none` |
| `composition.spectrum.animation` | **P5** Layer 4 behaviors (+ spectrum audio dial recipes) |
| `composition.logo.enabled` | `logoSettings.enabled` |
| `composition.logo.animation` | **P5** Layer 4 + `logoSettings.spinEnabled` / motion |
| `composition.text.enabled` | `albumText` / `titleText` / `textOverlays` |
| `composition.overlay.*` | `overlaySettings` (**stub domain**; `animation` added in P5) |
| `composition.particles.type` | `particlesSettings.variant` / `style` |
| `composition.particles.behavior` | **P5** shared Layer 4 id (particle types expand in P6) |
| `composition.lighting.effect` | `lightningLayers[].style` |
| `composition.lighting.trigger` | `lightningLayers[].trigger` |
| `composition.camera.behavior` | `effects.camera_shake` (+ P8 camera library) |
| `composition.postProcessing.effects[]` | `effects.vignette` / `bloom` / `rgb_split` / … |
| `composition.audio.mapping` | **new** (P11) |
| `composition.colorPalette` | **new** (P2) |

---

## 5. Text vs Overlay (locked)

| Domain | Meaning | Legacy |
|--------|---------|--------|
| **Text** | Typography content | `albumText`, `titleText`, `textOverlays` |
| **Overlay** | Top-of-frame composites (frames, stickers, watermarks, badges) | `overlaySettings` (stub in P0) |

Do not fold Overlay into Spectrum or Logo.

---

## 6. Renderer rule (P0)

`TemplateNormalizer.to_renderer_dict` **strips** `composition` before returning the GPU dict so preview/export golden fixtures and ModernGL stay on legacy fields only. Authoring tools may call `ensure_composition_on_template` when loading/saving templates.

---

## 7. P0 exit criteria

- [x] All 9 Layer 1 objects in schema  
- [x] Architecture tree typed keys (stubs allowed)  
- [x] Logo, Text, Overlay explicit and distinct  
- [x] Legacy map documented + coded  
- [x] Golden fixture + unit tests  
- [x] Preview/export path unchanged (composition stripped from renderer dict)
