# Video — Domain Schema Appendix (Electron ↔ Renderer)

> **Document ID:** CAMXORA-PAGE-09-VIDEO-SCHEMA  
> **Version:** 1.0.0  
> **Parent:** [`09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md`](09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md)  
> **Electron sources:** `videoTemplateDraft.ts`, `domains/**/**Settings.ts`, `effectPackContracts.ts`  
> **Renderer source:** `python_app/visualizer/gpu_render.py`  
> **Fixtures:** [`../../tests/fixtures/video/`](../../tests/fixtures/video/)  
> **Last updated:** 2026-07-08

---

# 1. Purpose

Field-by-field reference for **three representations** of the same video template:

| Representation | Where it lives | Shape |
|----------------|----------------|-------|
| **Saved template JSON** | `{userData}/video/*.json`, platform API | Nested Electron keys (`audioSettings`, `layers`, …) |
| **Flat draft (`VideoTemplateDraft`)** | In-memory editor state | Flat camelCase fields (`audioInputGain`, `backgroundEnabled`, …) |
| **Renderer dict** | Passed to ModernGL (`--templateB64`) | Saved JSON + merge patch + renderer aliases |

**Rule:** Disk and API use **saved template JSON**. UI uses **flat draft**. GPU uses **renderer dict** produced by `TemplateNormalizer.to_renderer_dict()`.

---

# 2. Top-level saved template keys

Keys present on a typical saved template (from `video_templates_local.json` + save patch):

| Key | Type | Written by | Notes |
|-----|------|------------|-------|
| `templateName` | string | Save | Display name |
| `style` | string | Spectrum patch | Preset key, e.g. `straight-bars`, `liquid`, `flying-glow` |
| `spectrumEnabled` | boolean | Spectrum patch | Master spectrum toggle |
| `layers` | array | Save (spectrum editor) | Spectrum layer records (see §3) |
| `audioSettings` | object | Spectrum patch | Nested audio react fields (see §4) |
| `position` | object | Spectrum patch | Canvas anchor + offset (see §5) |
| `previewBindings` | object | Spectrum patch | Logo attachment (see §6) |
| `backgroundSettings` | object | Background patch | Background presentation (see §7) |
| `logoSettings` | object | Logo patch | Logo presentation (see §8) |
| `logoPath` | string | Logo patch | Workspace-relative logo file path |
| `previewLogo` | string | Logo patch | Same as `logoPath` on save |
| `particlesSettings` | object | Particles patch | Particle system (see §9) |
| `effects` | object | Atmosphere patch | Vignette + smoke (+ legacy bloom/rgb) (see §10) |
| `textOverlays` | array | Text patch | Timed text layers (see §11) |
| `effectPacks` | object | Save | Pack refs per domain (see §12) |
| `globalColor` | object | Legacy / optional | Global color model; layers may override |
| `previewBackground` | string | Legacy / optional | Background path hint (assets resolved externally) |
| `renderBaseHeight` | number | Legacy / optional | Layout hint; pass through |
| `automations` | array | Legacy / optional | Audio automation curves; pass through |

Keys **not** stored on disk but present on flat draft: all `*Draft` flat fields (§13 summary table).

---

# 3. Spectrum layers (`layers[]`)

Each layer object (Electron editor + gpu_render):

| Field | Type | Default | Draft source | gpu_render |
|-------|------|---------|--------------|------------|
| `id` | string | generated | layer editor | yes |
| `name` | string | optional | layer editor | no |
| `enabled` | boolean | `true` | layer editor | skipped if false |
| `blur` | number | `0` | layer editor | yes |
| `glow` | number | `18` | layer editor | yes |
| `opacity` | number | `1` | layer editor | yes |
| `thickness` | number | `42` | layer editor | yes |
| `barWidth` | number | `3` | layer editor | yes |
| `radiusOffset` | number | index×18 | layer editor | yes |
| `curved` | boolean | `true` | layer editor | yes |
| `mirrored` | boolean | `true` | layer editor | yes |
| `fillCircle` | boolean | `false` | layer editor | yes |
| `gravity` | string | `bottom` | layer editor | yes |
| `blend_mode` | string | `normal` | layer editor | yes |
| `rotation` | number | `0` | layer editor | pass through |
| `color` | object | see below | layer editor | yes |

### 3.1 Layer color object

| Field | Type | Values |
|-------|------|--------|
| `mode` | string | `solid`, `gradient` |
| `solidColor` | string | `#rrggbb` |
| `gradientColors` | string[] | 2+ hex colors |
| `gradientDirection` | string | `diagonal`, `radial`, `left-to-right`, … |

**Style key normalization** (Electron `normalizeSpectrumStyleKey` — apply in Python normalizer):

| Input alias | Canonical |
|-------------|-----------|
| `symmetrical` | `symmetrical-bars` |
| `triple-neon-halo` | `halo-stack` |
| `bass-vortex-stack` | `liquid` |
| `soft-aura-stack` | `soft-waveform` |

---

# 4. Spectrum domain — flat draft ↔ saved JSON

### 4.1 Flat draft fields (`SpectrumSettingsState`)

| Flat draft field | Saved JSON path | Default | Legacy fallback read |
|------------------|-----------------|---------|----------------------|
| `spectrumEnabled` | `spectrumEnabled` | `true` | — |
| `style` | `style` | `straight-bars` | — |
| `audioInputGain` | `audioSettings.inputGain` | `1` | `audioSettings.sensitivity` |
| `audioBarHeight` | `audioSettings.barHeight` | `1` | — |
| `audioBandContrast` | `audioSettings.bandContrast` | `1` | `audioSettings.heightBoost` |
| `audioTransientFocus` | `audioSettings.transientFocus` | `1` | — |
| `audioKickImpact` | `audioSettings.kickImpact` | `0` | `audioSettings.kickDrop` |
| `audioBassEmphasis` | `audioSettings.bassEmphasis` | `1` | — |
| `audioTrebleShimmer` | `audioSettings.trebleShimmer` | `1` | — |
| `audioPeakHoldBlend` | `audioSettings.peakHoldBlend` | `0` | — |
| `audioMotionSmoothing` | `audioSettings.motionSmoothing` | `0.8` | `audioSettings.smoothing` |
| `flyingGlowWingMotionSpeed` | `audioSettings.flyingGlowWingMotionSpeed` | `1` | `audioSettings.wingMotionSpeed` |
| `flyingGlowWingRelease` | `audioSettings.flyingGlowWingRelease` | `0.9` | `audioSettings.wingRelease` |
| `spectrumAttachToLogo` | `previewBindings.spectrumAttachToLogo` | `false` | — |
| `spectrumLogoGap` | `previewBindings.spectrumLogoGap` | computed | `getRecommendedSpectrumLogoGap()` |
| `anchor` | `position.anchor` | `center` | — |
| `positionX` | `position.x` | `0` | — |
| `positionY` | `position.y` | `0` | — |

### 4.2 Save patch behavior

`buildSpectrumTemplatePatch` **strips legacy keys** from `audioSettings` on save:

- Removes: `sensitivity`, `heightBoost`, `kickDrop`, `smoothing`, `wingMotionSpeed`, `wingRelease`

### 4.3 Renderer alias (critical)

`gpu_render.py` reads **`audioSettings.sensitivity`** only (not `inputGain`).

| Normalizer step | Action |
|-----------------|--------|
| R-1 | After merge, set `audioSettings.sensitivity = audioSettings.inputGain` if `inputGain` present |
| R-2 | If legacy file has only `sensitivity`, set `inputGain = sensitivity` for draft hydration |
| R-3 | Pass through all other `audioSettings` keys for forward compatibility |

---

# 5. Position object (`position`)

| Field | Type | Default | gpu_render |
|-------|------|---------|------------|
| `anchor` | string | `center` | yes (logo + spectrum offset) |
| `x` | number | `0` | yes (scaled by `sf`) |
| `y` | number | `0` | yes (scaled by `sf`) |

Anchor values: `center`, `top`, `bottom`, `left`, `right`, corners as Electron supports.

---

# 6. Preview bindings (`previewBindings`)

| Field | Type | Default | gpu_render |
|-------|------|---------|------------|
| `spectrumAttachToLogo` | boolean | `false` in draft builder; **`true` default in gpu_render if missing** | yes |
| `spectrumLogoGap` | number | computed from logo shape/size | yes (× scale factor) |

**Normalizer note:** When building renderer dict, prefer explicit draft values over gpu defaults.

---

# 7. Background domain

### 7.1 Flat draft ↔ `backgroundSettings`

| Flat draft field | Saved path | Default | gpu_render |
|------------------|------------|---------|------------|
| `backgroundEnabled` | `backgroundSettings.enabled` | `true` | implied by asset path |
| `backgroundFitMode` | `backgroundSettings.fitMode` | `cover` | yes (`cover`/`contain`/`original`) |
| `backgroundUserScale` | `backgroundSettings.userScale` | `1` | yes |
| `backgroundBrightness` | `backgroundSettings.brightness` | `1` | yes |
| `backgroundContrast` | `backgroundSettings.contrast` | `1` | yes (`bg_contrast`) |
| `backgroundSaturation` | `backgroundSettings.saturation` | `1` | yes (`bg_saturation`) |
| `backgroundHue` | `backgroundSettings.hue` | `0` | yes (`bg_hue`, degrees −180…180) |
| `backgroundReactivity` | `backgroundSettings.reactivity` | `0` | yes (`react_bass`; brightness only) |
| `backgroundSmoothing` | `backgroundSettings.smoothing` | `0.8` | yes |
| `backgroundMotionMode` | `backgroundSettings.motionMode` | `none` | yes |
| `backgroundMotionZoomStrength` | `backgroundSettings.motionZoomStrength` | `1` | yes |
| `backgroundMotionVibrateStrength` | `backgroundSettings.motionVibrateStrength` | `1` | yes |
| `backgroundMotionSpeed` | `backgroundSettings.motionSpeed` | `1` | partial |

### 7.2 Drag-edit fields (saved, not in flat draft slice)

| Saved path | Default | Notes |
|------------|---------|-------|
| `backgroundSettings.userOffsetX` | `0` | Canvas drag; preserved on background patch |
| `backgroundSettings.userOffsetY` | `0` | Canvas drag |

Background **image path** is not in template JSON — resolved from workspace / export assets (`--background` CLI arg).

---

# 8. Logo domain

### 8.1 Flat draft ↔ saved JSON

| Flat draft field | Saved path | Default | gpu_render |
|------------------|------------|---------|------------|
| `logoEnabled` | `logoSettings.enabled` | `true` | yes |
| `logoSpinEnabled` | `logoSettings.spinEnabled` | `false` | yes |
| `logoSpinDirection` | `logoSettings.spinDirection` | `cw` | yes (`cw`/`ccw`) |
| `logoSpinSpeed` | `logoSettings.spinSpeed` | `0` | yes (deg/s) |
| `logoPath` | `logoPath` + `previewLogo` | workspace | CLI `--logo` + template |
| `logoShape` | `logoSettings.circleMask` | `circle` → `true` | yes |
| `logoSizeStep` | `logoSettings.size` | slider 1–10 → `size = step×100` | yes (`size` px) |
| `logoOpacity` | `logoSettings.opacity` | `1` | yes |
| `logoReactivity` | `logoSettings.reactivity` | `0` | yes |
| `logoSmoothing` | `logoSettings.smoothing` | `0.75` | preview reactive path |
| `logoMotionMode` | `logoSettings.motionMode` | `none` | partial |
| `logoMotionZoomStrength` | `logoSettings.motionZoomStrength` | `1` | partial |
| `logoMotionVibrateStrength` | `logoSettings.motionVibrateStrength` | `1` | partial |
| `logoMotionSpeed` | `logoSettings.motionSpeed` | `1` | partial |

### 8.2 Size conversion

```text
draft.logoSizeStep = clamp(realSize / 100, 1, 10)
save: logoSettings.size = logoSizeStep * 100
```

---

# 9. Particles domain

### 9.1 Flat draft ↔ `particlesSettings`

Electron saves **camelCase** keys. `gpu_render` reads camelCase with snake_case legacy fallback.

| Flat draft field | Saved path | Default | gpu_render key |
|------------------|------------|---------|----------------|
| `particlesEnabled` | `enabled` | `true` | `enabled` |
| `particlesMaxCount` | `maxCount` | `200` | `maxCount` / `count` |
| `particlesSpawnRate` | `spawnRate` | `100` | `spawnRate` / `spawn_rate` |
| `particlesLifetimeSec` | `lifetimeSec` | `1.6` | `lifetimeSec` / `lifetime_sec` |
| `particlesSpeed` | `speed` | `1` | `speed` (× scale) |
| `particlesReactivity` | `reactivity` | `0.1` | used in particle logic |
| `particlesAudioTravelBoost` | `audioTravelBoost` | `1` | pass through |
| `particlesAudioMotionMode` | `audioMotionMode` | `both` | pass through |
| `particlesSmoothing` | `smoothing` | `0.65` | pass through |
| `particlesSpawnMode` | `spawnMode` | `always` | pass through |
| `particlesSpawnTrigger` | `spawnTrigger` | `both` | pass through |
| `particlesSpawnThreshold` | `spawnThreshold` | `0.15` | pass through |
| `particlesVariant` | `variant` | `classic` | pass through |
| `particlesSpawnArea` | `spawnArea` | `centerRing` | pass through |
| `particlesSizeJitter` | `sizeJitter` | `0` | pass through |
| `particlesDrift` | `drift` | `0` | pass through |
| `particlesSwirl` | `swirl` | `0` | pass through |
| `particlesStyle` | `style` | `dot` | pass through |
| `particlesSize` | `size` | `2` | yes (× scale) |
| `particlesOpacity` | `opacity` | `0.35` | yes |
| `particlesColor` | `color` | `#ffffff` | yes |
| `particlesReactColor` | `reactColor` | `#ffffff` | pass through |
| `particlesReactStrength` | `reactStrength` | `0.65` | pass through |

**Legacy:** root `particles` object (snake_case) — normalizer may map to `particlesSettings` for renderer.

---

# 10. Atmosphere domain (`effects`)

Vignette and smoke are edited in the **Background** inspector tab but saved under `effects`.

### 10.1 Vignette (`effects.vignette`)

| Flat draft field | Saved path | Default |
|------------------|------------|---------|
| `vignetteEnabled` | `enabled` | `false` |
| `vignetteStrength` | `strength` | `0.35` |
| `vignetteFeather` | `feather` | `0.65` |
| `vignetteOpacity` | `opacity` | `0.65` |
| `vignetteColor` | `color` | `#000000` |

### 10.2 Smoke (`effects.smoke`)

| Flat draft field | Saved path | Default |
|------------------|------------|---------|
| `smokeEnabled` | `enabled` | `false` |
| `smokeStrength` | `strength` | `0.35` |
| `smokeBlur` | `blur` | `0.55` |
| `smokeNoise` | `noise` | `0.55` |
| `smokeSpeed` | `speed` | `0.35` |
| `smokeOpacity` | `opacity` | `0.55` |
| `smokeColor` | `color` | `#000000` |

### 10.3 Legacy post-FX (pass through)

| Path | gpu_render |
|------|------------|
| `effects.bloom` | yes |
| `effects.rgb_split` | yes |
| `effects.camera_shake` | yes |

---

# 11. Text overlays (`textOverlays[]`) + Album/Title domains

### 11.0 Album / Title domains (`albumText` / `titleText`)

Expanded into `textOverlays` by `inject_text_domains_into_template` before GPU draw.

| Flat draft (prefix `album` / `title`) | Saved path | Notes |
|---------------------------------------|------------|-------|
| `*Enabled` | `*.enabled` | |
| `*StylePreset` | `*.stylePreset` | 10 CapCut-like presets (`neon_glow` … `glass_outline`) |
| `*FillMode` | `*.style.fillMode` | `solid` / `gradient` / `neon` |
| `*GradientColors` | `*.style.gradientColors` | |
| `*GradientDirection` | `*.style.gradientDirection` | `vertical` / `horizontal` / `diagonal` |
| `*Glow` / `*GlowBlur` / `*GlowColor` | `*.style.glow*` | Soft outer glow |
| `*ExtrudeDepth` / `*ExtrudeColor` | `*.style.extrude*` | 3D extrusion stack |
| `*ShadowBlur` | `*.style.shadowBlur` | |
| `titleListColor` | `titleText.listColor` | Normal row color |
| `titleListActiveColor` | `titleText.listActiveColor` | Highlighted row |
| `titleListActiveIndex` | `titleText.listActiveIndex` | `-1` = none |

Effect packs: `effectPacks.album` / `effectPacks.title`.

### 11.1 Flat draft (`TemplateTextOverlayDraft`)

| Draft field | Saved field | Default | gpu_render |
|-------------|-------------|---------|------------|
| `enabled` | `enabled` | `false` | yes |
| `text` | `text` | `''` | yes |
| `startSec` | `startSec` | `0` | yes |
| `durationSec` | `durationSec` | `3` | yes |
| `anchor` | `anchor` | `center` | yes |
| `x` | `x` | `24` | yes |
| `y` | `y` | `24` | yes |
| `fontSize` | **`sizePx`** | `46` | **`sizePx` only** |
| `color` | `color` | `#ffffff` | yes |
| `strokeColor` | `strokeColor` | `#000000` | yes |
| `strokeWidth` | `strokeWidth` | `2` | yes |
| `shadow` | `shadow` | `0.4` | yes |
| `fillMode` / `glow*` / `extrude*` | same | optional | yes (PIL text path) |
| `animation` | `animation` | `fade` | yes |

**Save patch writes `sizePx`, not `fontSize`.** Renderer reads `sizePx`. Normalizer must convert draft → saved shape before GPU.

---

# 12. Effect packs (`effectPacks`)

| Domain key | Saved shape | Draft source |
|------------|-------------|--------------|
| `spectrum` | `{ packId, version }` or omitted | `draft.effectPacks.spectrum` |
| `background` | same | `draft.effectPacks.background` |
| `logo` | same | `draft.effectPacks.logo` |
| `particles` | same | `draft.effectPacks.particles` |
| `album` | same | `draft.effectPacks.album` |
| `title` | same | `draft.effectPacks.title` |

On save, `null` domain entries are written explicitly when cleared.

**Renderer:** `effectPacks` is ignored by `gpu_render.py` — pack overlays must already be merged into template fields before `to_renderer_dict()`.

---

# 13. Complete flat draft field index

`VideoTemplateDraft` = all domains below + `effectPacks` + `textOverlays`.

| Domain | Field count | Inspector tab |
|--------|-------------|---------------|
| Spectrum | 17 | Left — Spectrum |
| Background | 10 | Left — Background |
| Atmosphere | 12 | Left — Background (same tab) |
| Logo | 14 | Left — Logo |
| Particles | 22 | Left — Particles |
| Text | `textOverlays[]` | Right — Text |
| Effect packs | 4 domain refs | Per-domain selector |

---

# 14. TemplateNormalizer algorithm

```text
INPUT:
  base_template   — saved JSON (currentTemplate)
  draft           — VideoTemplateDraft (flat)
  layers          — editable spectrum layers array
  workspace       — { logoPath }

STEPS:
  1. patch ← buildVideoWorkspaceTemplateSavePatch({
       template: base_template,
       draft,
       templateName: (unchanged for renderer),
       layers
     })
  2. merged ← deep_merge(base_template, patch)
  3. Apply renderer aliases (§4.3, §11 sizePx already in patch)
  4. Optionally resolve effect pack patches into merged (pre-step 1 if packs active)
  5. RETURN merged
```

### 14.1 Export vs preview

| Use case | `base_template` | `draft` |
|----------|-----------------|---------|
| Live preview | `previewTemplate` (saved + style + layers overlay) | current `templateDraft` |
| Manual export | same as preview | live draft (`draftSource: live`) |
| Pipeline export | saved workspace template | rebuilt via `buildVideoTemplateDraft` (`draftSource: saved`) |

### 14.2 Electron vs camxora_python export path

| | Electron today | camxora_python |
|--|----------------|----------------|
| Manual export | WebGPU hidden host | ModernGL subprocess (same as pipeline) |
| Pipeline export | Python `visualizer.main` | Same ported module |
| Template to GPU | Host compositor | `TemplateNormalizer.to_renderer_dict()` → `--templateB64` |

---

# 15. Golden fixtures

See [`tests/fixtures/video/README.md`](../../tests/fixtures/video/README.md).

| Fixture set | Tests |
|-------------|-------|
| `01_*` minimal defaults | Empty saved template + default draft → renderer dict |
| `02_*` bass drive excerpt | Real-world layers + nested settings |
| `03_*` legacy sensitivity | `audioSettings.sensitivity` only → dual keys in renderer |

**Test command (when implemented):**

```bash
pytest camxora_python/tests/features/video/test_template_normalizer.py -v
```

---

# 16. Related documents

- [`09_VIDEO_REQUIREMENTS.md`](09_VIDEO_REQUIREMENTS.md)
- [`09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md`](09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md)
- Electron: `videoWorkspaceTemplateSave.ts`, `renderSceneRequest.ts`
- python_app: `visualizer/gpu_render.py`, `visualizer/config.py`
