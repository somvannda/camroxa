# Visualizer Composition Engine — Alignment Assessment

**Date:** 2026-08-05  
**Status:** Architecture assessment only — **no implementation**  
**Scope:** Build a **pure composition / render engine** driven by JSON. AI is **out of scope for now** (deferred until the engine + schema are stable).  
**Product surface:** Desktop `camxora_python` (preview + export). Legacy Electron `camxora/` is reference/history only.  
**Related:**

- [`camxora_python/.docs/pages/09_VIDEO_DOMAIN_SCHEMA_APPENDIX.md`](../camxora_python/.docs/pages/09_VIDEO_DOMAIN_SCHEMA_APPENDIX.md) — saved template / draft / renderer contracts  
- [`docs/COMPOSITION_ENGINE_P0_SCENE_SCHEMA.md`](COMPOSITION_ENGINE_P0_SCENE_SCHEMA.md) — **P0 frozen composition keys**  
- [`docs/COMPOSITION_ENGINE_P1_ORTHOGONAL_AXES.md`](COMPOSITION_ENGINE_P1_ORTHOGONAL_AXES.md) — **P1 orthogonal axis apply**  
- [`camxora_python/.docs/pages/09_VIDEO_ENTERPRISE_ARCHITECTURE.md`](../camxora_python/.docs/pages/09_VIDEO_ENTERPRISE_ARCHITECTURE.md) — domain isolation + effect packs  
- [`docs/PREVIEW_HDR_BLOOM_DESIGN.md`](PREVIEW_HDR_BLOOM_DESIGN.md) — post path (HDR → bloom → tonemap)  
- [`docs/PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md`](PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md) — preview compositing constraints  

**AI note (deferred):** Later, AI only needs to learn the **stable JSON schema** (and allowed enum values / ranges) and emit valid scene/template JSON. It does not invent shaders. This document focuses on the engine.

---

## Canonical source requirements (verbatim text — formatting only)

> Source requirements below. **Markdown formatting only** — wording and meaning unchanged.

### Layer 1 — Scene Objects

These are the major objects in every scene.

- Background
- Spectrum
- Logo
- Text
- Particles
- Lighting
- Camera
- Audio
- Overlay

These never change.

### Layer 2 — Asset Libraries

Each object has its own library.

#### Spectrum

- Circle
- Double Circle
- Wave
- Bars
- Hexagon
- Diamond
- Triangle
- Infinity
- Heart
- Audio Ribbon
- Spiral
- Tunnel

Notice these are geometry, not effects.

#### Particle System

- Dust
- Snow
- Rain
- Fire
- Smoke
- Magic
- Electric
- Stars
- Bubbles
- Ash
- Confetti
- Leaves
- Sparkles

#### Lighting

- Lightning
- Aura
- Glow
- God Rays
- Lens Flare
- Light Beam
- Light Sweep
- Neon Rim
- Halo
- Energy Pulse

#### Camera

- Zoom
- Pan
- Orbit
- Rotate
- Shake
- Tilt
- Dolly
- Roll
- Focus Pull
- Parallax

### Layer 3 — Post Processing

This is the biggest category I think you're missing.

Most modern engines separate effects from objects.

- Bloom
- Color Grading
- Tone Mapping
- HDR
- Exposure
- Gamma
- Contrast
- Saturation
- Vignette
- Chromatic Aberration
- Film Grain
- Sharpen
- Motion Blur
- Depth of Field
- Lens Distortion
- Glow

These don't belong to the spectrum—they affect the entire rendered frame.

### Layer 4 — Animation Behaviors

Instead of asking:

> Which spectrum?

Ask:

> How does it move?

- Pulse
- Bounce
- Rotate
- Expand
- Contract
- Ripple
- Wave
- Twist
- Elastic
- Fade
- Flash
- Breathing

These behaviors can apply to many different objects.

### Layer 5 — Materials

This is another important concept.

Imagine your spectrum can use different materials.

- Neon
- Glass
- Crystal
- Electric
- Fire
- Ice
- Metal
- Liquid
- Plasma
- Gold
- Hologram
- Carbon

Now a circular spectrum can become:

- Neon Circle
- Glass Circle
- Fire Circle
- Plasma Circle

without creating four separate spectrum assets.

### Layer 6 — Color Systems

Don't hardcode colors.

Create palettes.

- Cyberpunk
- Synthwave
- Festival
- EDM
- Dubstep
- Future Bass
- Sunset
- Aurora
- Galaxy
- Fire
- Ocean
- Monochrome

AI can simply choose a palette.

### Layer 7 — Atmosphere

This affects the whole scene.

- Fog
- Mist
- Rain
- Snow
- Storm
- Stars
- Clouds
- Dust
- Smoke
- Nebula
- Aurora

### Layer 8 — Background Motion

- Static
- Slow Zoom
- Ken Burns
- Orbit
- Parallax
- Ripple
- Energy Wave
- Floating
- Rotate
- Warp

This alone makes a static AI image feel alive.

### Layer 9 — Audio Reactions

This is where your visualizer becomes unique.

Different scene elements can react differently to the music.

- Bass
- Treble
- Vocals
- Beat
- Melody
- Kick
- Snare
- Overall Loudness

Examples:

- Lightning flashes only on bass hits.
- Particles emit on kick drums.
- Camera shakes with low frequencies.
- Logo pulses with vocals.

This gives users much more expressive control.

### The architecture I would build

```text
Scene
│
├── Background
│     ├── Image
│     ├── Motion
│     ├── Atmosphere
│
├── Spectrum
│     ├── Shape
│     ├── Material
│     ├── Animation
│
├── Particles
│     ├── Type
│     ├── Behavior
│
├── Lighting
│     ├── Effect
│     ├── Trigger
│
├── Camera
│
├── Post Processing
│
└── Audio Mapping
```

### Why this matters for AI

If a user says:

> "Create a futuristic purple EDM visualizer."

AI doesn't invent anything.

It simply fills in the scene:

```json
{
  "background": {
    "theme": "Cyberpunk City",
    "motion": "Parallax"
  },
  "spectrum": {
    "shape": "Double Circle",
    "material": "Neon",
    "animation": "Pulse"
  },
  "particles": {
    "type": "Electric Dust"
  },
  "lighting": {
    "effect": "Energy Pulse"
  },
  "postProcessing": {
    "bloom": "High",
    "toneMapping": "HDR",
    "vignette": true
  },
  "colorPalette": "Synthwave"
}
```

Your renderer already knows how to interpret that JSON.

### The biggest opportunity I see for Camxora

Based on everything you've told me over the past few days, I wouldn't aim for "the biggest effect library." I'd aim for the smartest composition engine.

For example, if you eventually have:

- 15 spectrum shapes
- 20 particle types
- 15 lighting effects
- 20 materials
- 20 color palettes
- 15 camera behaviors
- 15 atmosphere presets
- 20 post-processing effects

...the AI isn't limited to a few hundred templates. It can intelligently combine compatible pieces into millions of distinct visual styles while reusing the same underlying components. That's a far more scalable approach than continuously creating handcrafted templates, and it's exactly the kind of architecture that makes AI both inexpensive and genuinely useful.

---

## 0. Verdict (read this first)

**Directionally aligned. Not a rewrite. Engine-first.**

Camxora already thinks in **scene domains** stored as **JSON** (Background, Spectrum, Logo, Particles, Text, Lightning, Atmosphere effects, Audio). The layered proposal is the same idea pushed further: turn today’s **handcrafted preset bundles** into **orthogonal axes** (shape × material × animation × palette × audio map) so the engine can interpret any valid combination.

| Question | Answer |
|----------|--------|
| Does this match how we already structure Video? | **Yes** — Layer 1 scene objects ≈ our domains. |
| Are effects built with JSON? | **Yes** — templates/presets/packs are JSON; GPU reads a normalized renderer dict. |
| Do we already have a composition engine? | **Partially** — domains + effect packs + per-domain presets. Not yet a full combinatorial matrix. |
| Would adopting this require a lot of changes? | **No big-bang rewrite.** Medium evolutionary work. Hard parts: materials, shared animation vocabulary, richer post — not a new graphics stack. |
| What about AI? | **Later.** Once the JSON schema is clean and complete, AI learns that structure and emits JSON. |

**Wrong move:** rebuild the renderer as a new “engine,” or design around AI first.  
**Right move:** keep domains / normalizer / preview+export GPU path; **orthogonalize** the JSON so humans (and later AI) compose by filling fields the renderer already understands.

---

## 1. Core idea: the engine is JSON → pixels

```text
┌─────────────────────────────────────────────────────────────┐
│  Template / effect JSON  (saved on disk, packs, presets)    │
│  backgroundSettings · spectrum · logo · particles · …       │
└──────────────────────────────┬──────────────────────────────┘
                               │ TemplateNormalizer
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  Renderer dict  (same JSON shape + aliases)                 │
└──────────────────────────────┬──────────────────────────────┘
                               │ preview_widget / gpu_render
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  ModernGL frame: BG → atmosphere → spectrum → particles →   │
│  logo → lightning → text → post                             │
└─────────────────────────────────────────────────────────────┘
```

**Asset files** (background image, logo PNG, MP3) are **paths**, not inventable by the visualizer JSON. The JSON describes **how** those assets + procedural layers look and move.

---

## 2. Yes — effects are JSON (what AI would eventually learn)

### 2.1 Three representations (same product truth)

| Representation | Who uses it | Shape |
|----------------|-------------|-------|
| **Saved template JSON** | Disk, API, effect packs after merge | Nested keys: `backgroundSettings`, `logoSettings`, `particlesSettings`, `effects`, `layers`, `audioSettings`, … |
| **Flat draft** | Inspectors / editor state | Flat camelCase: `backgroundMotionMode`, `logoSpinSpeed`, … |
| **Renderer dict** | ModernGL preview + export | Saved JSON + merge + aliases (`TemplateNormalizer.to_renderer_dict`) |

Authoritative field map: schema appendix. Golden fixtures: `camxora_python/tests/fixtures/video/`.

### 2.2 What “understand the JSON” means (for a future AI)

Basically **yes** — with three clarifications:

1. **Schema + enums + ranges**, not free-form creativity.  
   Valid `backgroundMotionMode` today is roughly `none` | `zoom` | `vibrate`. Invalid values get normalized/clamped. AI (later) must emit values the engine accepts.

2. **Domain patches**, not one mystery blob.  
   Spectrum JSON ≠ logo JSON ≠ lightning JSON. Each domain has its own keys. A good engine doc is a **per-domain schema**, which we already sketch in the appendix.

3. **Media paths are separate.**  
   JSON says “logo spin + reactivity”; the actual `logoPath` / background file comes from workspace / pipeline / user. AI inventing `"theme": "Cyberpunk City"` is **image content**, not visualizer engine JSON — keep that outside this engine doc.

### 2.3 Example of what the engine already consumes (shape, not full file)

```json
{
  "style": "orbit-spikes",
  "spectrumEnabled": true,
  "layers": [ { "enabled": true, "glow": 0, "barWidth": 5, "color": { "mode": "gradient", "gradientColors": ["#…"] } } ],
  "audioSettings": { "inputGain": 1, "kickImpact": 0.2, "bassEmphasis": 1 },
  "backgroundSettings": { "enabled": true, "motionMode": "zoom", "reactivity": 4.5 },
  "logoSettings": { "enabled": true, "spinEnabled": false, "reactivity": 0.3 },
  "particlesSettings": { "enabled": true, "variant": "dust", "spawnTrigger": "kick" },
  "effects": {
    "vignette": { "enabled": true, "strength": 0.35 },
    "smoke": { "enabled": false },
    "bloom": { "enabled": false },
    "camera_shake": { "enabled": false }
  },
  "effectPacks": { "spectrum": null, "particles": null }
}
```

**Engine job:** interpret every field consistently in preview and export.  
**Later AI job:** emit valid objects like the above (or patches that merge into them).

---

## 3. What was proposed (engine layers — ignore AI)

Nine conceptual layers for the **composition model**:

1. **Scene objects** — Background, Spectrum, Logo, Text, Particles, Lighting, Camera, Audio, Overlay  
2. **Asset libraries** — geometry / particle types / lighting types / camera moves  
3. **Post-processing** — bloom, grading, vignette, grain, … (whole-frame)  
4. **Animation behaviors** — Pulse, Bounce, Rotate, … (reusable across objects)  
5. **Materials** — Neon, Glass, Fire, Plasma, …  
6. **Color systems** — named palettes  
7. **Atmosphere** — Fog, Rain, Stars, Nebula, …  
8. **Background motion** — Static, Ken Burns, Parallax, Warp, …  
9. **Audio reactions** — Bass / Kick / … mapped per object  

Target tree (engine JSON mental model):

```text
Scene
├── Background   (image ref + motion + atmosphere)
├── Spectrum     (shape + material + animation)
├── Logo         (asset ref + motion + audio react)
├── Overlay      (text / album / title layers + animation)
├── Particles    (type + behavior)
├── Lighting     (effect + trigger)
├── Camera
├── Post Processing
└── Audio Mapping
```

**Overlay** in Camxora today = `textOverlays` + album/title domains (timed text on top of the frame). It is a first-class scene object, not part of Spectrum or Logo.

Filling that tree = writing JSON the renderer understands. No AI required to build or ship the engine.

---

## 4. How Camxora works today (ground truth)

### 4.1 Scene is already domain-shaped

| Proposed scene object | Current Camxora home | Maturity |
|-----------------------|----------------------|----------|
| Background | `backgroundSettings` + image path (external) | Strong |
| Spectrum | `style` + `layers[]` + multi-instance registry | Strong |
| Logo | `logoSettings` + path | Strong |
| Text / Overlay | `textOverlays` + album/title domains | Strong |
| Particles | `particlesSettings` | Strong |
| Lighting | Lightning domain + spectrum glow | Partial |
| Camera | `effects.camera_shake` + logo/bg motion | Thin |
| Audio | `audioSettings` + per-domain reactivity / triggers | Strong |
| Atmosphere | `effects.vignette`, `effects.smoke` | Thin–medium |
| Post | `effects.bloom`, `effects.rgb_split`, HDR bloom path (flag) | Partial |

### 4.2 Presets exist — but they are recipes, not axes

Today a “style” often **bundles** geometry + colors + motion + audio knobs in one patch:

| Domain | Examples today | Bundle nature |
|--------|----------------|---------------|
| Spectrum | `orbit-spikes`, `aurora-ribbon`, `plasma-bloom` | Shape + layer stack + defaults together |
| Particles | `embers`, `dust_field`, `energy_sparks` | Variant + spawn + color + trigger together |
| Background | `cinematic_static`, `bass_pulse_zoom` | Motion + grade + vignette/smoke together |
| Lightning | `neon_sky`, styles `fork`/`sheet`/`neon` | Style + trigger presets |

Engine evolution = **split recipes into orthogonal JSON fields** so `shape` + `material` + `animation` + `palette` can be combined freely. Keep preset buttons as **convenience patches** that fill those fields.

### 4.3 Effect packs

Domain-isolated packs (`effectPacks.spectrum|background|logo|particles|…`) already ship JSON payloads merged into the template before render. Marketplace extensibility fits this engine model: packs are more JSON the same schema understands.

---

## 5. Layer-by-layer alignment

Legend: **Aligned** · **Partial** · **Gap** · **Effort**

### Layer 1 — Scene objects → **Aligned** (low effort)

Stable scene slots already exist. Map names → domains; do not invent a parallel scene graph.

### Layer 2 — Asset libraries → **Partial** (medium)

Have style/variant IDs. Missing geometry-only libraries (Circle, Bars, Hexagon, …) independent of look. Expand catalogs + GPU paths; keep JSON aliases for old style keys.

### Layer 3 — Post-processing → **Partial** (medium–high)

Have vignette, bloom, rgb_split, camera shake, HDR path (flag), BG brightness/contrast/sat/hue. Missing first-class whole-frame grading, grain, DOF, motion blur, lens distortion, etc. Keep under `effects` / future `postProcessing` — not on spectrum presets.

### Layer 4 — Animation behaviors → **Partial** (medium)

Per-domain motion exists (zoom/vibrate/spin/react). Missing shared behavior vocabulary (`Pulse`, `Bounce`, …) as JSON fields reusable across objects.

### Layer 5 — Materials → **Gap** (medium for look packs; high for true shaders)

No `material: neon | glass | plasma` axis yet. Start with **material look packs** (parameter JSON applied onto shape), not a PBR rewrite.

### Layer 6 — Color systems → **Partial** (low–medium)

Gradients and per-layer colors exist. Missing named scene palettes that write into multiple domains in one apply.

### Layer 7 — Atmosphere → **Partial** (medium)

Smoke + vignette + lightning/particles cover some looks. Missing fog/rain/stars/nebula-style atmosphere presets (often particles + post + JSON, not new engines).

### Layer 8 — Background motion → **Partial** (low–medium)

`none` / `zoom` / `vibrate` only. Expanding `backgroundMotionMode` is mostly engine + JSON enum work.

### Layer 9 — Audio reactions → **Aligned** (low–medium to unify)

Already strong: spectrum audio dials, logo/bg reactivity, particle spawn triggers, lightning triggers, kick/bass envelopes, shake. Optional later: one `audioMapping` object in JSON that writes into those existing fields (single source after expand — avoid dual truth).

---

## 6. Proposed “high-level” scene JSON vs engine JSON

Sparse example from the layered proposal:

```json
{
  "background": { "motion": "Parallax" },
  "spectrum": { "shape": "Double Circle", "material": "Neon", "animation": "Pulse" },
  "particles": { "type": "Electric Dust" },
  "lighting": { "effect": "Energy Pulse" },
  "postProcessing": { "bloom": "High", "vignette": true },
  "colorPalette": "Synthwave"
}
```

**Engine-first interpretation:** this is a **compact composition patch** — useful as a preset format or internal apply language — that **must resolve into** the real saved template / draft fields the GPU already uses.

| Compact field | Resolves into (today / planned) |
|---------------|----------------------------------|
| `background.motion` | `backgroundSettings.motionMode` (+ strengths) |
| `spectrum.shape` | Spectrum style / geometry + layers |
| `spectrum.material` | New material look fields / pack |
| `spectrum.animation` | Motion / reactivity fields |
| `particles.type` | Particle preset / variant+style |
| `lighting.effect` | Lightning layers / presets |
| `postProcessing.*` | `effects.*` |
| `colorPalette` | Cross-domain color writes |

Do **not** replace saved template JSON with only the compact form. Compact form is optional sugar; **saved template JSON remains source of truth**.

---

## 7. Do we need a lot of changes?

### 7.1 What we do **not** need

- New renderer technology (Vulkan/RHI) for this architecture  
- Abandoning domain isolation / effect packs / draft-before-save  
- Designing the engine around AI prompts  
- Handcrafting thousands of full templates  

### 7.2 Engine workstreams (AI deferred)

| Workstream | Why | Relative size |
|------------|-----|---------------|
| **A. Composition vocabulary** | Document enums: shapes, materials, behaviors, palettes, motions, audio buses | Small |
| **B. Orthogonalize presets** | Split bundled presets into axes; keep aliases | Medium |
| **C. Palette system** | Named palettes → multi-domain color apply | Small–Medium |
| **D. Material looks** | Neon/Glass/… as parameter packs on shapes | Medium |
| **E. Shared animation behaviors** | Map Pulse/Bounce/… onto domains | Medium |
| **F. Post stack expansion** | Grow `effects` / post behind HDR path | Medium–High |
| **G. Background motion library** | Ken Burns, parallax, etc. | Low–Medium |
| **H. Audio Mapping object** | Optional façade → existing fields | Small–Medium |
| **I. Schema freeze + fixtures** | Golden JSON for every domain combo we claim to support | Medium |
| **J. Compatibility rules** | Which field combos are valid / performance-safe | Medium |

**Total:** multi-phase engine evolution, not a rewrite.

### 7.3 Effort summary

```text
Already aligned ████████████░░░░  ~60% of Layer 1 + Layer 9 + domain JSON skeleton
Partial         ████████░░░░░░░░  libraries, post, motion, atmosphere, color
True gaps       ████░░░░░░░░░░░░  materials axis, orthogonal schema, combo rules
```

---

## 8. Compatibility / quality rules (engine concerns)

Combinatorial explosion only works with **constraints** baked into the engine (and documented in schema):

| Rule | Example |
|------|---------|
| Domain caps | Max spectrum instances / particle budgets by export speed tier (already exist) |
| Look conflicts | Heavy smoke + heavy bloom may auto-derate |
| Geometry × material | Some materials only for closed shapes / fill modes |
| Pack + builtin | Same schema; packs merge into template fields before render |

These rules protect preview/export quality whether a human or (later) AI authored the JSON.

---

## 9. Delivery phases (from canonical requirements)

Do **not** start coding from this doc until explicitly requested.

**Program goal:** ship a JSON-driven composition engine that delivers **every** canonical Layer 1–9 requirement, the architecture tree, and these **catalog targets**:

| Catalog | Target count | Canonical named list | Fill to target |
|---------|-------------:|----------------------|----------------|
| Spectrum shapes | **15** | 12 (Circle … Tunnel) | +3 additional geometries |
| Particle types | **20** | 13 (Dust … Sparkles) | +7 additional types |
| Lighting effects | **15** | 10 (Lightning … Energy Pulse) | +5 additional effects |
| Materials | **20** | 12 (Neon … Carbon) | +8 additional materials |
| Color palettes | **20** | 12 (Cyberpunk … Monochrome) | +8 additional palettes |
| Camera behaviors | **15** | 10 (Zoom … Parallax) | +5 additional behaviors |
| Atmosphere presets | **15** | 11 (Fog … Aurora) | +4 additional presets |
| Post-processing effects | **20** | 16 (Bloom … Glow) | +4 additional effects |

**Also required (not counted above, but must ship):** Layer 1 scene objects, Layer 4 animation behaviors (all 12), Layer 8 background motions (all 10), Layer 9 audio buses (all 8) + Audio Mapping, architecture tree axes (Background Image/Motion/Atmosphere, Spectrum Shape/Material/Animation, Particles Type/Behavior, Lighting Effect/Trigger, Camera, Post Processing, Audio Mapping), Logo / Text / Overlay as scene objects.

**AI is deferred** until Phase 13. Engine + JSON schema must be complete first (P0–P12).

---

### 9.1 Phase overview

| Phase | Name | Canonical coverage | Catalog target progress |
|-------|------|--------------------|-------------------------|
| **P0** | Scene contract & architecture tree | Layer 1 + architecture tree skeleton | Schema only |
| **P1** | Orthogonal composition axes | Shape / Material / Animation / Type / Behavior / Effect / Trigger fields | Schema only |
| **P2** | Color Systems | Layer 6 (all 12 named) | → **20** palettes |
| **P3** | Spectrum shapes | Layer 2 Spectrum (all 12 named) | → **15** shapes |
| **P4** | Materials | Layer 5 (all 12 named) | → **20** materials |
| **P5** | Animation Behaviors | Layer 4 (all 12 named), multi-object | Behaviors complete |
| **P6** | Particle System | Layer 2 Particle System (all 13 named) | → **20** types |
| **P7** | Lighting | Layer 2 Lighting (all 10 named) | → **15** effects |
| **P8** | Camera | Layer 2 Camera (all 10 named) | → **15** behaviors |
| **P9** | Atmosphere + Background Motion | Layer 7 (all 11) + Layer 8 (all 10) | → **15** atmosphere |
| **P10** | Post Processing | Layer 3 (all 16 named) | → **20** effects |
| **P11** | Audio Reactions + Audio Mapping | Layer 9 (all 8 buses + examples) | Audio Mapping complete |
| **P12** | Composition completion gate | Full coverage matrix + compatibility | **All targets met** |
| **P13** | AI authoring (deferred) | “Why this matters for AI” | Out of engine scope until asked |

Phases **P0 → P12** are the project delivery for the engine. **P13** is explicitly later.

---

### 9.2 Phase detail

#### Phase 0 — Scene contract & architecture tree

**Delivers**

- Layer 1 scene objects locked as first-class JSON domains (never change):
  - Background, Spectrum, Logo, Text, Particles, Lighting, Camera, Audio, Overlay
- Architecture tree as the scene JSON mental model:

```text
Scene
│
├── Background
│     ├── Image
│     ├── Motion
│     ├── Atmosphere
│
├── Spectrum
│     ├── Shape
│     ├── Material
│     ├── Animation
│
├── Particles
│     ├── Type
│     ├── Behavior
│
├── Lighting
│     ├── Effect
│     ├── Trigger
│
├── Camera
│
├── Post Processing
│
└── Audio Mapping
```

- Map each tree node → current saved template / draft keys (and gaps)
- Golden fixtures for empty/default scene
- Preview + export still interpret today’s JSON (no break)

**Exit criteria**

- [x] All 9 Layer 1 objects documented in schema appendix  
- [x] Architecture tree fields exist as typed keys (even if some values are stub/`none`)  
- [x] Logo, Text, Overlay explicitly in scene contract (not folded into Spectrum)

**P0 shipped (2026-08-05):** [`docs/COMPOSITION_ENGINE_P0_SCENE_SCHEMA.md`](COMPOSITION_ENGINE_P0_SCENE_SCHEMA.md) + `composition_scene_contract.py`.

---

#### Phase 1 — Orthogonal composition axes

**Delivers**

- Split bundled presets into independent JSON axes:
  - Spectrum: `shape` + `material` + `animation`
  - Particles: `type` + `behavior`
  - Lighting: `effect` + `trigger`
  - Background: `image` + `motion` + `atmosphere`
- Keep legacy style/preset keys as **aliases** that expand into axes
- Notice from Layer 2: Spectrum library entries are **geometry, not effects**

**Exit criteria**

- [x] Applying shape does not force a material  
- [x] Applying material does not change geometry id  
- [x] Preset buttons remain convenience patches over the axes  
- [x] Old templates still load via aliases  

**P1 shipped (2026-08-05):** [`docs/COMPOSITION_ENGINE_P1_ORTHOGONAL_AXES.md`](COMPOSITION_ENGINE_P1_ORTHOGONAL_AXES.md) + `composition_axes.py`.

#### Phase 2 — Color Systems → 20 palettes

**Delivers Layer 6 (exact named list first)**

1. Cyberpunk  
2. Synthwave  
3. Festival  
4. EDM  
5. Dubstep  
6. Future Bass  
7. Sunset  
8. Aurora  
9. Galaxy  
10. Fire  
11. Ocean  
12. Monochrome  

**Fill to target 20** — add **8** more palette ids (names chosen in implementation; must be documented in schema). Do not hardcode one-off colors in new presets; presets reference palette ids.

**Exit criteria**

- [ ] All 12 canonical palettes apply across Spectrum / Particles / Lighting / Overlay colors
- [ ] Catalog count = **20**
- [ ] “AI can simply choose a palette” is satisfied by stable palette JSON ids (AI itself deferred)

---

#### Phase 3 — Spectrum shapes → 15

**Delivers Layer 2 Spectrum geometry (exact named list first)**

1. Circle  
2. Double Circle  
3. Wave  
4. Bars  
5. Hexagon  
6. Diamond  
7. Triangle  
8. Infinity  
9. Heart  
10. Audio Ribbon  
11. Spiral  
12. Tunnel  

**Fill to target 15** — add **3** more geometry ids (documented in schema).

**Exit criteria**

- [ ] All 12 canonical shapes render in preview + export
- [ ] Catalog count = **15**
- [ ] Each shape is selectable independent of material (Phase 1)

---

#### Phase 4 — Materials → 20

**Delivers Layer 5 (exact named list first)**

1. Neon  
2. Glass  
3. Crystal  
4. Electric  
5. Fire  
6. Ice  
7. Metal  
8. Liquid  
9. Plasma  
10. Gold  
11. Hologram  
12. Carbon  

**Fill to target 20** — add **8** more material ids.

**Proves the requirement example without four separate spectrum assets:**

- Neon Circle  
- Glass Circle  
- Fire Circle  
- Plasma Circle  

**Exit criteria**

- [ ] All 12 canonical materials apply onto at least Circle (and remaining shapes where compatible)
- [ ] Catalog count = **20**
- [ ] No duplicate spectrum assets required for material variants

---

#### Phase 5 — Animation Behaviors (all 12)

**Delivers Layer 4 — ask “How does it move?” not only “Which spectrum?”**

1. Pulse  
2. Bounce  
3. Rotate  
4. Expand  
5. Contract  
6. Ripple  
7. Wave  
8. Twist  
9. Elastic  
10. Fade  
11. Flash  
12. Breathing  

Behaviors must be attachable to **many different objects** (at minimum Spectrum, Logo, Overlay, Particles where applicable).

**Exit criteria**

- [ ] All 12 behaviors exist as JSON enum values
- [ ] Same behavior id works on more than one scene object
- [ ] Spectrum animation axis uses this library

---

#### Phase 6 — Particle System → 20 types

**Delivers Layer 2 Particle System (exact named list first)**

1. Dust  
2. Snow  
3. Rain  
4. Fire  
5. Smoke  
6. Magic  
7. Electric  
8. Stars  
9. Bubbles  
10. Ash  
11. Confetti  
12. Leaves  
13. Sparkles  

**Fill to target 20** — add **7** more types.

Particles JSON uses `type` + `behavior` (architecture tree).

**Exit criteria**

- [ ] All 13 canonical types render
- [ ] Catalog count = **20**
- [ ] Type and behavior are independent fields

---

#### Phase 7 — Lighting → 15 effects

**Delivers Layer 2 Lighting (exact named list first)**

1. Lightning  
2. Aura  
3. Glow  
4. God Rays  
5. Lens Flare  
6. Light Beam  
7. Light Sweep  
8. Neon Rim  
9. Halo  
10. Energy Pulse  

**Fill to target 15** — add **5** more lighting effect ids.

Lighting JSON uses `effect` + `trigger` (architecture tree). Triggers integrate with Audio Mapping (full wiring completed in P11; stubs allowed earlier).

**Exit criteria**

- [ ] All 10 canonical lighting effects render
- [ ] Catalog count = **15**
- [ ] Effect ≠ whole-frame post (those stay in Layer 3)

---

#### Phase 8 — Camera → 15 behaviors

**Delivers Layer 2 Camera (exact named list first)**

1. Zoom  
2. Pan  
3. Orbit  
4. Rotate  
5. Shake  
6. Tilt  
7. Dolly  
8. Roll  
9. Focus Pull  
10. Parallax  

**Fill to target 15** — add **5** more camera behavior ids.

**Exit criteria**

- [ ] All 10 canonical camera behaviors implemented
- [ ] Catalog count = **15**
- [ ] Camera is a scene-level object (not a Spectrum setting)

---

#### Phase 9 — Atmosphere (15) + Background Motion (all 10)

**Delivers Layer 7 Atmosphere (exact named list first)**

1. Fog  
2. Mist  
3. Rain  
4. Snow  
5. Storm  
6. Stars  
7. Clouds  
8. Dust  
9. Smoke  
10. Nebula  
11. Aurora  

**Fill atmosphere to target 15** — add **4** more presets.

**Delivers Layer 8 Background Motion (exact named list — all required)**

1. Static  
2. Slow Zoom  
3. Ken Burns  
4. Orbit  
5. Parallax  
6. Ripple  
7. Energy Wave  
8. Floating  
9. Rotate  
10. Warp  

Background tree: Image + Motion + Atmosphere.  
Requirement note preserved: this alone makes a static AI image feel alive (motion is engine; image source may remain external).

**Exit criteria**

- [ ] All 11 canonical atmosphere presets
- [ ] Atmosphere catalog = **15**
- [ ] All 10 background motions
- [ ] Motion and atmosphere are independent Background fields

---

#### Phase 10 — Post Processing → 20

**Delivers Layer 3 (exact named list first)** — whole-frame only; **do not belong to the spectrum**

1. Bloom  
2. Color Grading  
3. Tone Mapping  
4. HDR  
5. Exposure  
6. Gamma  
7. Contrast  
8. Saturation  
9. Vignette  
10. Chromatic Aberration  
11. Film Grain  
12. Sharpen  
13. Motion Blur  
14. Depth of Field  
15. Lens Distortion  
16. Glow  

**Fill to target 20** — add **4** more post-processing effect ids.

**Exit criteria**

- [ ] All 16 canonical post effects available under Post Processing / `effects`
- [ ] Catalog count = **20**
- [ ] None of these are stored as Spectrum-only assets
- [ ] Preview + export WYSIWYG for enabled post stack (within performance tiers)

---

#### Phase 11 — Audio Reactions + Audio Mapping

**Delivers Layer 9 audio buses (exact named list)**

1. Bass  
2. Treble  
3. Vocals  
4. Beat  
5. Melody  
6. Kick  
7. Snare  
8. Overall Loudness  

**Delivers the requirement examples**

- Lightning flashes only on bass hits.  
- Particles emit on kick drums.  
- Camera shakes with low frequencies.  
- Logo pulses with vocals.  

**Delivers** architecture tree `Audio Mapping` as the JSON object that routes buses → scene objects (Lighting trigger, Particles emit, Camera shake, Logo pulse, etc.).

**Exit criteria**

- [ ] All 8 buses available to mapping
- [ ] All four examples work end-to-end in preview + export
- [ ] Users have expressive per-object audio control via JSON / UI

---

#### Phase 12 — Composition completion gate (project delivery)

**Delivers**

- Full requirements coverage matrix green (see §9.3)
- Compatibility rules for valid combinations (smart composition engine — not the biggest handcrafted template library)
- Catalog counts verified:

| Catalog | Must equal |
|---------|-----------:|
| Spectrum shapes | 15 |
| Particle types | 20 |
| Lighting effects | 15 |
| Materials | 20 |
| Color palettes | 20 |
| Camera behaviors | 15 |
| Atmosphere presets | 15 |
| Post-processing effects | 20 |

- Documented combinatorial capacity consistent with the opportunity statement (shapes × particles × lighting × materials × palettes × camera × atmosphere × post), with compatibility constraints so combinations remain valid
- Golden fixtures + regression tests for each catalog id
- Effect-pack metadata can expose the same libraries

**Exit criteria = project delivery done for the engine**

- [ ] Every canonical named item from Layers 1–9 is implemented
- [ ] Every catalog target count is met
- [ ] Architecture tree is fully interpretable JSON
- [ ] Preview and export both understand the JSON
- [ ] No AI dependency required to use the engine

---

#### Phase 13 — AI authoring (deferred — not part of engine delivery)

Out of scope until explicitly requested. When started, AI only fills the scene JSON the renderer already interprets (example from canonical requirements: futuristic purple EDM → background/spectrum/particles/lighting/postProcessing/colorPalette). Engine must already be complete from P12.

---

### 9.3 Requirements coverage matrix (nothing left out)

| Canonical requirement | Phase |
|----------------------|-------|
| Layer 1 Background | P0 |
| Layer 1 Spectrum | P0 |
| Layer 1 Logo | P0 |
| Layer 1 Text | P0 |
| Layer 1 Particles | P0 |
| Layer 1 Lighting | P0 |
| Layer 1 Camera | P0 |
| Layer 1 Audio | P0, completed wiring P11 |
| Layer 1 Overlay | P0 |
| Layer 2 Spectrum geometries (12 named) | P3 |
| Layer 2 Spectrum → 15 shapes | P3 |
| Layer 2 “geometry, not effects” | P1, P3 |
| Layer 2 Particle System (13 named) | P6 |
| Layer 2 Particles → 20 types | P6 |
| Layer 2 Lighting (10 named) | P7 |
| Layer 2 Lighting → 15 effects | P7 |
| Layer 2 Camera (10 named) | P8 |
| Layer 2 Camera → 15 behaviors | P8 |
| Layer 3 Post Processing (16 named) | P10 |
| Layer 3 Post → 20 effects | P10 |
| Layer 3 “not spectrum — whole frame” | P10 |
| Layer 4 Animation Behaviors (12 named) | P5 |
| Layer 4 multi-object behaviors | P5 |
| Layer 5 Materials (12 named) | P4 |
| Layer 5 Materials → 20 | P4 |
| Layer 5 Neon/Glass/Fire/Plasma Circle example | P4 |
| Layer 6 Color palettes (12 named) | P2 |
| Layer 6 Palettes → 20 | P2 |
| Layer 7 Atmosphere (11 named) | P9 |
| Layer 7 Atmosphere → 15 | P9 |
| Layer 8 Background Motion (10 named) | P9 |
| Layer 9 Audio buses (8 named) | P11 |
| Layer 9 audio mapping examples (4) | P11 |
| Architecture: Background Image/Motion/Atmosphere | P0, P9 |
| Architecture: Spectrum Shape/Material/Animation | P1, P3, P4, P5 |
| Architecture: Particles Type/Behavior | P1, P6 |
| Architecture: Lighting Effect/Trigger | P1, P7, P11 |
| Architecture: Camera | P8 |
| Architecture: Post Processing | P10 |
| Architecture: Audio Mapping | P11 |
| Smart composition engine opportunity / catalog targets | P12 |
| AI fills JSON example | P13 (deferred) |

---

### 9.4 Fill slots — what this means (and proposed names)

#### What is a “fill slot”?

The canonical lists name the **required** items (e.g. 12 spectrum shapes).  
The **project delivery targets** ask for higher counts (e.g. **15** spectrum shapes).

| Catalog | Canonical named | Target | Gap (“fill slots”) |
|---------|----------------:|-------:|-------------------:|
| Spectrum shapes | 12 | 15 | **+3 names we must invent** |
| Particle types | 13 | 20 | **+7 names** |
| Lighting effects | 10 | 15 | **+5 names** |
| Materials | 12 | 20 | **+8 names** |
| Color palettes | 12 | 20 | **+8 names** |
| Camera behaviors | 10 | 15 | **+5 names** |
| Atmosphere presets | 11 | 15 | **+4 names** |
| Post-processing effects | 16 | 20 | **+4 names** |

**What we need from you exactly:** approve (or rewrite) the **product display names** below. Those become the official catalog ids (plus a stable machine id like `ring` / `petal`). Without approved names, phases can still start on the canonical 12/13/… lists, but a phase cannot be marked **done** for the full target count.

These are **proposals only** until Boss confirms.

#### Proposed Spectrum shapes (+3) → total 15

Canonical 12: Circle, Double Circle, Wave, Bars, Hexagon, Diamond, Triangle, Infinity, Heart, Audio Ribbon, Spiral, Tunnel.

| # | Proposed name | Machine id (draft) | Note |
|---|---------------|--------------------|------|
| 13 | Ring | `ring` | Closed thin annulus (distinct from filled Circle) |
| 14 | Starburst | `starburst` | Radial spikes from center |
| 15 | Pillars | `pillars` | Tall vertical column bars |

#### Proposed Particle types (+7) → total 20

Canonical 13: Dust, Snow, Rain, Fire, Smoke, Magic, Electric, Stars, Bubbles, Ash, Confetti, Leaves, Sparkles.

| # | Proposed name | Machine id (draft) |
|---|---------------|--------------------|
| 14 | Embers | `embers` |
| 15 | Petals | `petals` |
| 16 | Glitter | `glitter` |
| 17 | Smoke Rings | `smoke_rings` |
| 18 | Energy Orbs | `energy_orbs` |
| 19 | Pixel Dust | `pixel_dust` |
| 20 | Feather Drift | `feather_drift` |

#### Proposed Lighting effects (+5) → total 15

Canonical 10: Lightning, Aura, Glow, God Rays, Lens Flare, Light Beam, Light Sweep, Neon Rim, Halo, Energy Pulse.

| # | Proposed name | Machine id (draft) |
|---|---------------|--------------------|
| 11 | Strobe Flash | `strobe_flash` |
| 12 | Rim Light | `rim_light` |
| 13 | Spot Cone | `spot_cone` |
| 14 | Volumetric Shaft | `volumetric_shaft` |
| 15 | Color Wash | `color_wash` |

#### Proposed Materials (+8) → total 20

Canonical 12: Neon, Glass, Crystal, Electric, Fire, Ice, Metal, Liquid, Plasma, Gold, Hologram, Carbon.

| # | Proposed name | Machine id (draft) |
|---|---------------|--------------------|
| 13 | Chrome | `chrome` |
| 14 | Matte | `matte` |
| 15 | Velvet | `velvet` |
| 16 | Obsidian | `obsidian` |
| 17 | Iridescent | `iridescent` |
| 18 | Latex | `latex` |
| 19 | Frosted Glass | `frosted_glass` |
| 20 | Wireframe | `wireframe` |

#### Proposed Color palettes (+8) → total 20

Canonical 12: Cyberpunk, Synthwave, Festival, EDM, Dubstep, Future Bass, Sunset, Aurora, Galaxy, Fire, Ocean, Monochrome.

| # | Proposed name | Machine id (draft) |
|---|---------------|--------------------|
| 13 | Midnight | `midnight` |
| 14 | Neon Pink | `neon_pink` |
| 15 | Tropical | `tropical` |
| 16 | Industrial | `industrial` |
| 17 | Candy | `candy` |
| 18 | Blood Moon | `blood_moon` |
| 19 | Arctic | `arctic` |
| 20 | Gold Rush | `gold_rush` |

#### Proposed Camera behaviors (+5) → total 15

Canonical 10: Zoom, Pan, Orbit, Rotate, Shake, Tilt, Dolly, Roll, Focus Pull, Parallax.

| # | Proposed name | Machine id (draft) |
|---|---------------|--------------------|
| 11 | Handheld | `handheld` |
| 12 | Crane | `crane` |
| 13 | Whip Pan | `whip_pan` |
| 14 | Punch In | `punch_in` |
| 15 | Drift | `drift` |

#### Proposed Atmosphere presets (+4) → total 15

Canonical 11: Fog, Mist, Rain, Snow, Storm, Stars, Clouds, Dust, Smoke, Nebula, Aurora.

| # | Proposed name | Machine id (draft) |
|---|---------------|--------------------|
| 12 | Haze | `haze` |
| 13 | Heatwave | `heatwave` |
| 14 | Underwater | `underwater` |
| 15 | Void | `void` |

#### Proposed Post-processing effects (+4) → total 20

Canonical 16: Bloom, Color Grading, Tone Mapping, HDR, Exposure, Gamma, Contrast, Saturation, Vignette, Chromatic Aberration, Film Grain, Sharpen, Motion Blur, Depth of Field, Lens Distortion, Glow.

| # | Proposed name | Machine id (draft) |
|---|---------------|--------------------|
| 17 | Letterbox | `letterbox` |
| 18 | Posterize | `posterize` |
| 19 | RGB Split | `rgb_split` (aligns with existing `effects.rgb_split`) |
| 20 | Soft Diffusion | `soft_diffusion` |

**Boss action:** reply approve / change names. Until then these stay “proposed.”

#### Decisions locked (2026-08-05)

| # | Decision |
|---|----------|
| 1 | **Build canonical lists first.** Do not block phases on fill-slot names. Request/approve extra names **when that phase is active** (e.g. name +3 shapes during P3 after the 12 work). |
| 2 | **Schema / key design:** Boss leaves recommendations to engineering. Goal: **no messy keys** — clear architecture-tree field names, with aliases for today’s legacy keys. |
| 3 | **Overlaps + hard audio buses:** Clarify **one by one** when the owning implementation phase starts (not all up front). |
| 4 | **Text and Overlay are both Layer 1 and different** — follow recommendation (Text = typography; Overlay = top composites / frames / stickers / watermarks). |

---

### 9.4b What “P0 schema freeze” means (plain language)

Today the engine already reads JSON, but keys are **historical and scattered**, for example:

- Background motion → `backgroundSettings.motionMode`
- Spectrum look → top-level `style` + `layers[]`
- Particles → `particlesSettings.variant`
- Post vignette → `effects.vignette`
- Camera shake → `effects.camera_shake`

The **architecture tree** wants a clear mental model:

```text
spectrum.shape / spectrum.material / spectrum.animation
particles.type / particles.behavior
lighting.effect / lighting.trigger
…
```

**P0 schema freeze** = we write down and lock the **exact field names** the product will use going forward (and how they map to today’s keys), before we build 15 shapes and 20 materials on shifting sand.

Example of what P0 must decide (when P0 starts):

| Architecture idea | Exact JSON key? (to decide) | Maps from today? |
|-------------------|-----------------------------|------------------|
| Spectrum shape | `spectrum.shape` vs keep `style`? | today’s `style` |
| Spectrum material | `spectrum.material`? | new |
| Background motion | `background.motion` vs `backgroundSettings.motionMode`? | today’s motionMode |
| Color palette | `colorPalette`? | new |
| Audio Mapping | `audioMapping.logo` = `"vocals"`? | new façade |

Boss approved (2026-08-05): engineering recommends clean keys; aliases keep old templates working.

#### What “Session A / B / C” and “P0 schema freeze” actually mean

Nothing special — **not** a meeting system, calendar, or separate product.  
It only means: **when we start that piece of work, we pause and decide that topic clearly before coding it.**

| Name | When it happens | What we decide together (short) |
|------|-----------------|----------------------------------|
| **P0 schema freeze** | When you say “start P0” / start composition engine work | Exact JSON field names for the architecture tree + legacy aliases |
| **Session A** | During P0 (Layer 1 contract) | Confirm Text ≠ Overlay in schema (already agreed — just wire it) |
| **Session B** | When we implement Atmosphere / Particles / Post / Lighting that share names (mainly P7, P9, P10) | Rain/Glow etc.: which layer owns which; no double-stack mess |
| **Session C** | When we implement Audio Mapping (P11) | How hard buses (Vocals / Melody / Snare) ship: real heuristic vs stub |

**You do not need to schedule Sessions A/B/C now.**  
When a phase starts, the agent will say: *“We’re at P11 — before coding Vocals, here are options…”* That *is* Session C. Same idea for P0: *“Here is the recommended JSON key table — OK to lock?”* That *is* the schema freeze.

---

### 9.4c Open decisions — detail sessions required (do not guess at implement time)

These items need a **dedicated requirement session** before/during the owning phase. Notes below are reminders, not final design.

#### Session A — Text vs Overlay (Layer 1)

**Decision locked (2026-08-05):** Text and Overlay are **both** Layer 1 and **different**.

- **Text** — typography domains (album / title / timed captions).  
- **Overlay** — top-of-frame composites (frames, stickers, watermarks, badges); may include text but is not limited to text.

Wire this in P0 schema; no further product debate unless Boss reopens it.

#### Session B — Overlaps (Atmosphere vs Particles; Lighting Glow vs Post Glow)

Same English word can mean different engine jobs:

| Name collision | Atmosphere (Layer 7) | Particles (Layer 2) | Lighting (Layer 2) | Post (Layer 3) |
|----------------|----------------------|---------------------|--------------------|----------------|
| Rain / Snow / Dust / Smoke | Whole-scene weather volume / environment | Discrete sprites/points | — | — |
| Stars | Sky field / env | Twinkle particles | — | — |
| Glow | — | — | Local light on objects / bolts | Whole-frame soft glow / bloom cousin |

**Rule to lock in Session B:**

1. **Atmosphere** = scene-wide environment (usually behind / around content).  
2. **Particles** = emitter objects (count, spawn, lifetime).  
3. **Lighting Glow** = local light contribution tied to Lighting effect.  
4. **Post Glow** = full-frame post pass (with Bloom / HDR family).  

JSON must use **different ids or namespaces** even if UI labels look similar (e.g. `atmosphere.rain` vs `particles.type = rain`; `lighting.effect = glow` vs `postProcessing.glow`).  
Compatibility rule: avoid stacking Atmosphere Rain + Particle Rain at full strength unless user explicitly wants both (auto-derate in `rules/`).

#### Session C — Audio buses difficulty (Layer 9)

Not all buses are equal to implement:

| Bus | Difficulty | Why |
|-----|------------|-----|
| Bass | Lower | Already strong in Camxora (envelopes / reactivity) |
| Kick | Lower | Onset / kick envelope exists |
| Beat | Lower–medium | Onset / beat features exist |
| Overall Loudness | Lower | RMS / loudness from spectrum features |
| Treble | Medium | Band-split exists in places; needs stable bus API |
| Snare | Higher | Needs transient mid-band detection; easy to confuse with kick |
| Vocals | Higher | Needs vocal-band / presence heuristic (or stem); not a simple FFT bin |
| Melody | Higher | Needs pitched/harmonic emphasis; easy to false-trigger |

**When implementing P11:** do not pretend Vocals/Melody/Snare are as cheap as Kick/Bass. Session C must decide for each hard bus:

1. **v1 heuristic** (FFT bands + smoothing) acceptable for shipping?  
2. Or **stub bus** (JSON exists, mapping UI works, engine uses fallback until detector quality is ready)?  
3. Acceptance tests for the four canonical examples (bass→lightning, kick→particles, low-freq→camera, vocals→logo).

Detail session required before marking P11 done for Vocals / Melody / Snare.

---

## 9.5 Proposed engine package structure — is it possible?

Proposed layout:

```text
│
├── engine/              # Rendering engine
├── scene/               # Scene graph
├── assets/              # Asset management
├── materials/           # Materials and shaders
├── effects/             # Visual effects
├── animations/          # Motion system
├── audio/               # Audio analysis & beat detection
├── ai/                  # AI orchestration
├── rules/               # Design rules and compatibility
├── renderer/            # Video export
├── templates/           # User templates
├── presets/             # Built-in styles
├── ui/                  # Studio interface
├── plugin-sdk/          # Future third-party extensions
└── docs/                # Knowledge base & schema
```

### Verdict

| Question | Answer |
|----------|--------|
| Can we use this structure for the composition engine? | **Yes — as the target module map.** |
| Can we deliver the canonical requirements with it? | **Yes.** Every Layer 1–9 item and catalog target fits into these packages. |
| Must we rewrite Camxora into this tree on day one? | **No.** Big-bang move is high risk. Grow into this layout (or mirror it under `visualizer/` + `features/video/`) phase by phase. |

This structure matches a game-engine / design-tool split and is **compatible** with our enterprise rule: UI / application / rendering stay separated (`features/video` vs `visualizer`).

### Map: proposed folder → Camxora today → canonical ownership

| Proposed package | Exists today (approx.) | Owns for canonical delivery |
|------------------|------------------------|-----------------------------|
| `engine/` | `camxora_python/visualizer/` (preview loop, ModernGL ctx, frame integrate) | Core frame loop; compose scene passes |
| `scene/` | Template/draft domains + draw order in `gpu_render` / `preview_widget` | Layer 1 scene objects + architecture tree JSON |
| `assets/` | Workspace paths, background/logo/audio CLI args, `assets/` app resources | Background Image, Logo paths, media refs (not inventing bitmaps) |
| `materials/` | Glow/color/fill knobs; no first-class material axis yet | Layer 5 → **20 materials** + shaders/look packs |
| `effects/` | `effects.py`, `hdr_bloom.py`, lightning, smoke, vignette | Layer 3 post → **20**; Layer 7 atmosphere → **15**; Layer 2 lighting → **15** |
| `animations/` | Per-domain motion (bg zoom/vibrate, logo spin, text anim) | Layer 4 behaviors (12); Layer 8 background motions (10); camera behaviors → **15** |
| `audio/` | `visualizer/audio.py`, kick/bass envelopes, FFT features | Layer 9 buses + Audio Mapping |
| `ai/` | Not an engine package today (platform AI is separate) | **P13 deferred** — stub only until engine complete |
| `rules/` | Export caps, partial normalizers; no full compatibility matrix | P12 compatibility / design rules |
| `renderer/` | `gpu_render.py`, encode pipeline, export daemon | Video export WYSIWYG of same scene JSON |
| `templates/` | User video template JSON / local store | Saved user scenes |
| `presets/` | Style registries (spectrum, particles, background, lightning, …) | Built-in catalogs (shapes, particles, palettes, …) |
| `ui/` | `features/video/views` + `widgets` inspectors | Studio controls over JSON axes |
| `plugin-sdk/` | Effect pack manifest + catalog protocol (marketplace-ready) | Third-party packs using same schema |
| `docs/` | `.docs/pages/09_*`, this alignment doc, schema appendix | Knowledge base & schema (canonical + phases) |

### How this delivers the catalog targets

| Target | Primary package(s) | Phase |
|--------|--------------------|-------|
| 15 spectrum shapes | `presets/` + `engine/` / spectrum draw | P3 |
| 20 particle types | `presets/` + `effects/` or particles module | P6 |
| 15 lighting effects | `effects/` | P7 |
| 20 materials | `materials/` | P4 |
| 20 color palettes | `presets/` (+ apply in `scene/`) | P2 |
| 15 camera behaviors | `animations/` + `scene/` Camera | P8 |
| 15 atmosphere presets | `effects/` | P9 |
| 20 post-processing effects | `effects/` + `renderer/` parity | P10 |
| Audio Mapping | `audio/` + `rules/` | P11 |
| Smart composition (not template spam) | `rules/` + `scene/` + `presets/` | P12 |

### Recommended adoption path (do not big-bang)

**Option A — Logical packages inside current tree (preferred near-term)**  
Evolve folders under something like:

```text
camxora_python/visualizer/
  engine/
  scene/
  materials/
  effects/
  animations/
  audio/
  rules/
  renderer/     # export path helpers (or keep gpu_render as renderer entry)
```

Keep `features/video/` as `ui/` + template/preset product services. Keep `ai/` empty or a stub package until P13.

**Important:** Option A’s short tree under `visualizer/` only listed **GPU-side** packages. That does **not** mean we drop `assets/`, `templates/`, `presets/`, or `ui/`. Those four are **required** product packages — they already exist under other names and stay in the full target structure:

```text
camxora_python/
├── visualizer/          # engine, scene, materials, effects, animations, audio, rules, renderer
├── features/video/
│   ├── views/ widgets/  # ui/
│   └── lib/             # templates + presets registries + draft/normalizer
├── assets/ / workspace  # assets/ (media paths, logos, backgrounds)
└── …                    # plugin-sdk (effect packs), docs/
```

#### We are having `assets/`, `templates/`, `presets/`, and `ui/`

They were never removed from the plan. They were only **not duplicated** under `visualizer/` because they belong to the **product / studio** side (or media), not the GPU frame loop.

| Package | Why we need it | Camxora today | Role in canonical delivery |
|---------|----------------|---------------|----------------------------|
| `assets/` | Background Image, Logo file, audio file | Workspace paths + CLI `--background` / `--logo` / audio; app `assets/` | Scene tree Background.Image + Logo asset refs |
| `templates/` | User-saved scenes | Video template JSON + local/API store | Persist full architecture-tree JSON |
| `presets/` | Built-in catalogs | `*_style_registry.py`, particle/background/lightning presets | 15 shapes, 20 particles, 20 palettes, … |
| `ui/` | Humans edit the JSON | Video page: inspectors, stage, preset dropdowns | Controls for every new axis (shape, material, palette, post, audio map, …) |

Without these four, users cannot pick media, save looks, browse catalogs, or edit the engine — so **canonical requirements cannot be delivered in product form**.

#### Do we need to refactor the current Video page UI?

**Yes — evolve it. No — not a full page rewrite on day one.**

| Approach | When | What |
|----------|------|------|
| **Evolve inspectors (required)** | Each phase P2–P11 | Add/reshape controls for new JSON axes: shape vs material, palette picker, post stack, camera, atmosphere, audio mapping. Keep existing Video shell (stage + left/right inspectors). |
| **Rename / regroup modules (optional)** | Anytime for clarity | Treat `features/video/views`+`widgets` as `ui/`; move registries into a clearer `presets/` package path — cosmetic structure, not a new UX. |
| **Full Video page redesign (not required for P12)** | Only if product asks | New studio chrome, new IA, CapCut-like layout, etc. **Not** needed to hit catalog counts if inspectors expose the axes. |

**Rule:** UI must follow the architecture tree (Background / Spectrum / Particles / Lighting / Camera / Post / Audio Mapping / Overlay), not invent a parallel control model. Preset dropdowns remain shortcuts that fill orthogonal fields.

**Practical sequence**

1. P0–P1: schema axes exist (UI can still use old bundled presets via aliases).  
2. P2+: each phase ships **matching UI** for that catalog (palette UI with P2, shape/material UI with P3–P4, …).  
3. Do **not** block engine work on a full Video UI redesign.  
4. Optional later: visual refactor of the Video page once axes are stable.

**Option B — Top-level `composition_engine/` sibling**  
Same packages as a clearer boundary, imported by Video UI. Only worth it if we want a stricter engine boundary; still must not break EA-1 (engine must not import UI).

**Option C — Full rename of the whole app to this tree**  
Possible but **not required** to deliver canonical requirements. High churn, high merge risk, delays P2–P12.

### Constraints (so “possible” stays true)

1. **JSON remains the contract** — folders organize code; they do not replace template schema.  
2. **One scene authority** — `scene/` interprets the architecture tree; UI only edits draft/JSON.  
3. **Preview and export share packages** — `renderer/` must not fork a second materials/effects stack.  
4. **`ai/` stays deferred** — do not block P0–P12 on AI orchestration.  
5. **`plugin-sdk/` = effect packs first** — same schema as builtins in `presets/`.  
6. **Inward dependencies** — `ui/` → application services → engine packages; never engine → UI.

### Bottom line on structure

**Yes, it is possible.** That folder layout is a good **target architecture** for delivering every canonical requirement and the catalog counts. Use it as the module map while implementing P0–P12; migrate code gradually. Do **not** require a greenfield rewrite before shipping shapes, materials, palettes, post, and audio mapping.

---

## 10. Risks

1. **Dual schema drift** — Compact composition JSON vs saved template diverge. Mitigation: compact always expands into saved/draft; saved JSON remains authority.  
2. **Preset breakage** — Orthogonalizing renames recipes. Mitigation: aliases forever.  
3. **Performance** — More post/atmosphere vs export speed tiers. Mitigation: keep existing caps.  
4. **Scope bleed** — Image themes vs visualizer JSON. Keep image pipeline docs separate.  
5. **UI overload** — Expose axes via presets first; power controls second.

---

## 11. Bottom line

| Claim | Camxora reality |
|-------|-----------------|
| Organize like a game engine / design tool | **Already the direction** (domains, frame composite, audio buses, JSON templates) |
| Effects are JSON | **Yes** — saved template + packs + presets; renderer consumes normalized JSON |
| Later AI only needs the JSON structure | **Yes** — schema, enums, ranges, domain patches; plus separate media paths |
| Layers > flat assets | **Agree** — next is orthogonal axes in that JSON |
| Post-processing is missing | **Partially true** — grow `effects` / HDR path |
| Materials unlock look × shape | **True gap** — material look packs in JSON |
| Biggest opportunity = composition engine | **Agreed** — build the engine; AI later |

**Conclusion:** Build the **JSON-driven composition engine** first. We are already ~halfway there structurally. Orthogonalize and extend the schema; keep preview/export as the interpreter. When AI comes later, it only has to **understand and emit valid engine JSON** — not invent rendering.
