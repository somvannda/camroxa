# Composition Engine + Studio — P0–P11

**Date:** 2026-08-05  
**Branch:** `feature/composition-engine-v1`  
**Status:** Engine-true catalogs + Composition Studio UI for P0–P11  

---

## Locked decisions

1. **Hard cut** — old video template bags (`style`, bundled preset recipes, `particlesSettings` as catalog authority, etc.) are **not** the scene contract.
2. **Authority** — saved scenes are `schema: camxora.composition` with `composition` + `assets` only.
3. **Renderer** — preview and export load via `visualizer.scene.load_scene` → `compile_scene`. Documents without `composition` **fail closed**.
4. **Studio UI** — architecture-tree left rail + single inspector host (not legacy domain-tab chrome as primary UX).
5. **Session B** — Atmosphere = weather/fog/sky; Particles = emitters; Lighting = bolts/aura/beams; Post = whole-frame.
6. **Session C** — Vocals / Melody / Snare are **v1 FFT heuristics** (smoothed band proxies), labeled in Audio Mapping UI.

---

## Document shape

```json
{
  "schema": "camxora.composition",
  "version": 1,
  "composition": {
    "colorPalette": "cyberpunk",
    "background": { "image": null, "motion": "ken_burns", "atmosphere": "fog" },
    "spectrum": { "shape": "circle", "material": "neon", "animation": "pulse" },
    "logo": { "enabled": true, "animation": "pulse" },
    "text": { "enabled": false },
    "overlay": { "enabled": false, "animation": "none", "items": [] },
    "particles": { "type": "sparkles", "behavior": "pulse" },
    "lighting": { "effect": "lightning", "trigger": "bass" },
    "camera": { "behavior": "shake" },
    "postProcessing": { "effects": ["bloom", "vignette"] },
    "audio": {
      "mapping": {
        "lighting": "bass",
        "particles": "kick",
        "camera": "bass",
        "logo": "vocals"
      }
    }
  },
  "assets": {
    "backgroundImage": null,
    "logo": null,
    "audio": null
  }
}
```

---

## Catalog counts

| Catalog | Count |
|---------|------:|
| Spectrum shapes | 15 |
| Materials | 20 |
| Animations | 12 |
| Particle types | 20 |
| Color palettes | 20 |
| Lighting effects | 15 |
| Camera behaviors | 15 |
| Atmosphere | 15 |
| Background motions | 10 |
| Post effects | 20 |
| Audio buses | 8 |

---

## Packages

```text
camxora_python/visualizer/
  scene/                  # load + Scene + compile (P0–P11 passes)
  presets/                # pure catalogs (shapes … audio_buses)
  materials/ animations/
  composition_effects/    # particles, lighting, camera, atmosphere, post, audio_mapping
  composition_renderer/   # bridge to preview/export

camxora_python/features/video/widgets/
  studio_shell.py / scene_tree.py / left_rail.py
  *_inspector.py          # palette … audio_mapping
```

---

## Studio navigation

Left rail scene tree: Color Palette · Background · Spectrum · Logo · Text · Overlay · Particles · Lighting · Camera · Post · Audio Mapping.

Center: preview stage (compiled scene).  
Right: Album / Title typography (Layer 1 text domains).

---

## Verify

```text
cd camxora_python
python -m pytest tests/test_composition_engine_v1.py tests/test_composition_studio_p0_p11.py -q
```

---

## Out of scope

- P13 AI authoring  
- Marketplace effect-pack rebinding as scene authority  
- True UE/C++ / full PBR  
