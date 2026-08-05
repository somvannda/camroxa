# Composition Engine V1 — Hard Cut

**Date:** 2026-08-05  
**Branch:** `feature/composition-engine-v1`  
**Status:** Engine-true P0–P6 milestone  

---

## Locked decisions

1. **Hard cut** — old video template bags (`style`, bundled preset recipes, `particlesSettings` as catalog authority, etc.) are **not** the scene contract.
2. **Authority** — saved scenes are `schema: camxora.composition` with `composition` + `assets` only.
3. **Renderer** — preview and export load via `visualizer.scene.load_scene` → `compile_scene`. Documents without `composition` **fail closed**.
4. **Catalogs (E1)** — 20 palettes, 15 shapes, 20 materials, 12 behaviors, 20 particle types are engine modules under `visualizer/`.

---

## Document shape

```json
{
  "schema": "camxora.composition",
  "version": 1,
  "composition": { },
  "assets": {
    "backgroundImage": null,
    "logo": null,
    "audio": null
  }
}
```

Media paths live under `assets` (workspace), not inside legacy domain bags.

---

## Packages

```text
camxora_python/visualizer/
  engine/                 # pass order
  scene/                  # load + Scene + compile
  materials/              # 20 materials
  animations/             # 12 shared drivers
  composition_effects/    # particles (+ later lighting/post)
  presets/                # pure catalogs
  composition_renderer/   # bridge to preview/export
  rules/                  # stubs (P12)
```

Existing modules `audio.py`, `effects.py`, `renderer.py` keep their names (GPU stack).

---

## Exit criteria (engine-true)

- Neon Circle Pulse / Glass Hexagon Bounce / Fire Bars Flash / Plasma Spiral Breathing compile from composition alone
- Same behavior id on spectrum + logo
- Rain ≠ Snow particle emitters under same behavior
- Material change does not change shape; type change does not clear behavior
- Missing `composition` raises `CompositionContractError`
- Render path does not treat `style` / old particle preset keys as authority
