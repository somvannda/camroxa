# Video Page Design System + Rendering Engine — Revamp Plan

**Date:** 2026-07-30
**Status:** plan only — no implementation in this doc
**Scope:** `camxora_python` desktop Video workspace (preview + export), specifically the Playlist glass card, Logo staging, Spectrum (bar/ring/orbit-spikes), and Particles subsystems, and the shared "design system" that should govern all of them.
**Owner input:** reference screenshots (Thunder Bass playlist-over-car preview; circular-spectrum "singer in a ring of light" reference) + a designer-style critique the user pasted in chat.

---

## 0. TL;DR answers to the questions asked in chat

**"Is this stupid?"** No. The car-background + logo + playlist composition is a completely reasonable first pass, and the color palette (blue/purple, consistent hue family) is already right. What's missing is *visual hierarchy and material quality*, not the concept.

**"Do you see the spectrum — circle and bar, and particles?"** Yes. `camxora_python` already has three separate, real, GPU-drawn visual systems:
- Bar/ring **spectrum** styles including `orbit-spikes` (concentric ring + radial spike bars around a circle — this is the *same primitive* as the reference "singer in a ring of light" image), driven by FFT bands (`visualizer/gpu_render.py`, `_spectrum_draw_jobs`, `_resolve_spectrum_layer_style_key`, style constant `orbit-spikes`).
- **Particles** — a real (if CPU-simulated) particle system with per-particle color/size/glow/trail, drawn as GPU quads with a dedicated vertex+fragment shader (`visualizer/particles.py` + `_compile_particle_quads` / `_render_particle_styled_quads` in `gpu_render.py`).
- **Logo** staging with circular mask, ring glow, drop shadow (`_ensure_music_icon_texture`, logo shader in `gpu_render.py`).

These three are already GPU-native and reasonably capable — they are *not* the weak link. The weak link, confirmed by code inspection, is the **Playlist/Album text+panel system**, which is CPU-rasterized with Pillow and has no shared design language with the spectrum/particle/logo systems. That asymmetry — GPU-quality background elements next to a Win95-dialog-quality foreground panel — is exactly why the composition in your screenshot "feels off," independent of any one setting being wrong.

**"What's the real limitation?"** You already diagnosed it correctly in the pasted critique: the agent (and the current codebase) thinks in **components** (`Border`, `Background`, `Text`, `Radius` — one tab per feature, one preset dict per feature) instead of **layers** (glass → blur → tint → noise → glow → shadow → highlight → text hierarchy), and there is no shared **design token / visual-weight budget** across Background / Logo / Spectrum / Particles / Playlist. This plan's central deliverable is exactly the token/theme layer you sketched with `PlaylistTheme(...)`, generalized to the whole video page.

---

## 1. Current architecture audit (evidence-based)

### 1.1 Three renderer subsystems, three different quality tiers

| Subsystem | Files | Render technique | Quality tier |
|---|---|---|---|
| Spectrum (bar/ring/orbit-spikes) | `visualizer/gpu_render.py` (`_spectrum_draw_jobs`, `vao_lines` draws, style resolvers), `features/video/lib/spectrum_instance_registry.py` | Real GPU: per-frame vertex buffers of bar/ring geometry, drawn with `moderngl` `TRIANGLE_STRIP`/`TRIANGLE_FAN`/`TRIANGLES`, additive blending, log-frequency FFT mapping | **GPU-native, real-time reactive** |
| Particles | `visualizer/particles.py` (`ParticleSystem`, numpy position/velocity/age/color/trail arrays), `_compile_particle_quads`, `_render_particle_styled_quads` | CPU simulation (numpy, vectorized) → GPU quad draw with dedicated particle shader (icon atlas, glow uniform, trails) | **GPU-drawn, CPU-simulated — good today, not infinitely scalable** |
| Logo | `_ensure_music_icon_texture`, dedicated logo fragment shader (circle mask, ring glow) | Real GPU shader | **GPU-native** |
| Playlist / Album text + glass panel | `features/video/lib/playlist_list_card.py`, `playlist_glass_backdrop.py`, `gpu_render._render_panel_rgba`, `_render_overlay_rgba`, `_render_text_rgba` | **Pillow (CPU) rasterization** of every panel/pill/text run into a PNG-like RGBA buffer, uploaded once as a static `moderngl.Texture`, then blitted as a textured quad. Blur/bloom/border/gradient are all baked into the raster with `ImageFilter.GaussianBlur`. Backdrop "frost" is a **one-shot crop-and-blur of the static background image**, not a live scene sample. | **CPU raster, static texture — the weak link** |

This confirms the user's own diagnosis: the playlist card is architecturally a *different kind of thing* than the spectrum/particles/logo. It was built as "draw a rounded rectangle with Pillow," not as a shader-native glass material that participates in the same GPU lighting/bloom language as everything else on screen.

### 1.2 "Component thinking" is visible in the UI structure too

`features/video/widgets/right_rail.py` exposes `_SIDE_TABS = (("album", "Album"), ("title", "Playlist"))`. Spectrum settings, Particle settings, and Logo settings each live in their own separate rail/tab with their own preset dict shape (`PLAYLIST_LOOK_PRESET_PATCHES` in `text_domain_registry.py` for Playlist; a parallel style-preset system for spectrum layers in `spectrum_instance_registry.py`; presumably similar siloed structures for particles/logo). Each tab's presets hard-code their own opacity/blur/border/color values with **no shared vocabulary** — there is no single object that says "this template's overall visual intensity budget is X, and Background/Logo/Spectrum/Particles/Playlist each get a share of it."

This is precisely the "thinks in components, not layers" and "no design system" problem from the critique, and it's visible at the code level, not just the pixel level.

### 1.3 The specific defects visible in the Thunder Bass screenshot

Cross-referencing the screenshot against the code:

1. **Panel is near-opaque gray**, not 15-25% frosted glass → `panelOpacity` default for most looks is 0.45-0.8+, and the *fill* is a flat hex color composited at that alpha over a **static one-time blurred crop**, not a live translucent sample — so it reads as "gray card," not "glass over a moving scene."
2. **Border is a solid bright ring** → `_render_panel_rgba`'s border pass draws a solid outline + one Gaussian blur; there's no separate "1-2px hairline + 10px soft glow" split the way the critique asks for — thickness and glow are conflated into one stroke.
3. **Corner radius reads "mobile app," not "HUD"** → current list-card radius constant (`_CARD_RADIUS = 12.5` template units → ~30px at 1080p) is fine per the *first* reference image (glass phone playlist), but wrong for *this* cyberpunk/HUD composition, which wants the 12-18px + thin neon edge look from the critique. This is a **look-specific token problem**, not a bug — Neon Glass Pro and a hypothetical "Cyberpunk HUD" look need different radius/border/opacity tokens, and today there's no token system to express that difference declaratively.
4. **Typography has weak hierarchy** → every row uses the same white color/opacity split (`text_opacity`, `text_opacity*0.6`, `text_opacity*0.7` — see `playlist_list_card.py`); there's no bright/bold "now playing" contrast beyond the gradient pill, and no `▶`/dot/accent-bar "now playing" glyph independent of the pill background.
5. **Header is a plain bar** → `PLAYLIST` + `N TRACKS` are just two text runs on the glass fill; no distinct sub-panel, divider, or "NOW PLAYING / Thunder Bass" treatment.
6. **No ambient integration with the scene** → no light spill from the logo onto the car, no particles interacting with the panel edge, no lens-flare/streak layer — because there is currently no "scene compositing" pass that lets these layers reference each other (light spill would require the logo's bloom pass to write into a shared glow buffer that other layers can sample).

None of this requires "more prompting." It requires the token/material system and (for a subset of items) real shader work described below.

---

## 2. Target: a two-layer system (Design Tokens + Rendering Engine)

Mirroring the user's own proposal (`PlaylistTheme(...)`), but generalized to the whole page:

```
Layer 1: DESIGN TOKENS (declarative, data-only, no rendering logic)
  VideoLookTheme
  ├── visual_weight_budget: {background, logo, spectrum, particles, playlist}  # sums to 1.0-ish, documents intended focal hierarchy
  ├── palette: {primary, accent, glow, text_primary, text_secondary, text_muted}
  ├── glass: {opacity, blur_radius, tint, border_width, border_opacity, glow_radius, glow_color, corner_radius, noise_amount}
  ├── typography: {title_font, body_font, mono_font, title_size, body_size, letter_spacing, now_playing_style}
  ├── spectrum: {style, bar_count, bar_width, ring_radius, glow, palette_ref}
  ├── particles: {density, size, speed, glow, palette_ref, spawn_area}
  └── motion: {pulse_period_sec, hover_scale, glow_pulse_amplitude}

Layer 2: RENDERING ENGINE (code, consumes tokens, produces pixels)
  ├── GlassMaterial (GPU) — SDF rounded-rect + live backdrop blur + gradient + bloom + hairline border
  ├── TypographyRenderer — hierarchy-aware text run compositor (keeps Pillow for glyphs, but composited through the same GPU glow/bloom path as everything else)
  ├── SpectrumRenderer (existing, extended to read tokens instead of ad hoc style dicts)
  ├── ParticleRenderer (existing, extended to read tokens; optional GPU-sim upgrade)
  └── SceneCompositor — single post pass that unifies bloom/glow across logo+spectrum+particles+glass so light "spills" consistently
```

The critical architectural shift: **presets stop being "a dict of raw pixel/opacity values per feature"** and become **"a set of token values shared by a material/typography engine that every feature draws through."** A new Look preset changes 15-20 token values once; it does not require re-deriving Pillow blur radii, border widths, and gradient stops independently for panel vs. header vs. divider vs. active-row-pill the way `playlist_list_card.py` does today.

---

## 3. Design tokens — concrete spec (answers "what values should we actually use")

This directly encodes the critique's numeric suggestions as a reusable, named token set (not one-off Pillow parameters):

### 3.1 Glass material tokens (per Look)

| Token | Cyberpunk HUD (Thunder Bass-style) | Neon Glass Pro (phone-reference style) | Notes |
|---|---|---|---|
| `opacity` | 0.15 - 0.22 | 0.75 - 0.85 | HUD wants *see-through*; phone-reference wants a *legible solid card*. Both are valid — the token, not the code, should differ per Look. |
| `blur_radius` (live backdrop) | 18-24px | 12-16px | Heavier blur reads "glass," lighter blur reads "frosted plastic." |
| `tint` | cool blue `#3fa9ff` @ 8-12% | warm lavender `#6d5b8e` @ solid fill | |
| `border_width` | 1-2px | 1-2px hairline everywhere | Never render a border as the *primary* visual signal. |
| `border_glow_radius` | 10-14px | 6-10px | Border is a hairline **+ separate soft glow pass**, never a thick solid stroke standing in for glow. |
| `corner_radius` | 12-18px | 28-32px | Radius should be a *Look* token, driven by the reference aesthetic (HUD = small radius; premium phone glass = large radius), not a single hardcoded constant shared by all Looks. |
| `noise_amount` | 2-4% grain | 0-2% | Subtle noise breaks up flat alpha gradients — currently entirely absent from the renderer. |
| `inner_glow` | soft cyan rim @ 15% | soft white rim @ 10% | |
| `drop_shadow` | soft, 20-30px blur, 30-40% opacity | soft, 20-30px blur | |

### 3.2 Typography hierarchy tokens

| Row state | Color / opacity | Weight | Extra |
|---|---|---|---|
| Now playing title | 100% white (or accent), bold | Semibold/Bold | subtle glow (`glow=0.2-0.3`), slightly larger size (+10-15%) |
| Now playing artist | 70-80% white | Regular | |
| Other titles | 80-90% white | Medium | |
| Other artists | 55-65% white | Regular | |
| Track numbers | 55-70% white | Regular, tabular | lower opacity than title always |
| Duration | 65-75% white | Regular, tabular | |
| Now-playing indicator | dedicated glyph (`▶`, `●`, or 3px accent bar), not just the pill background | — | should render even if `activeRowPlate` gradient is off, so "now playing" is legible two ways |

Font families: keep Montserrat as the safe default (already bundled), but add **Rajdhani** and/or **Orbitron/Exo 2** as selectable "Cyberpunk/HUD" typography tokens for Looks that want a geometric sci-fi feel — bundle as OFL webfonts the same way Montserrat/Inter were bundled in Phase 1 (`camxora_python/assets/fonts/`, `system_fonts.py`).

### 3.3 Visual-weight budget (the "layers have weight" idea, made literal)

Each Look declares an intended focal hierarchy, e.g.:

```
Cyberpunk Car Hero:
  background: 0.20   logo: 0.35   spectrum: 0.20   particles: 0.10   playlist: 0.15

Playlist Hero (phone-reference):
  background: 0.15   logo: 0.05   spectrum: 0.10   particles: 0.05   playlist: 0.65
```

This isn't rendered directly — it's a **design-time budget** used to derive default opacity/scale/glow tokens per subsystem so that, e.g., a "Logo=0.35" Look automatically biases the logo 2-3x larger and glowier than a "Logo=0.05" Look, without a human re-tuning five different sliders by hand every time. It also becomes an automatic linter: if a Look's *rendered* alpha coverage or bounding-box area wildly disagrees with its declared budget, that's a signal the preset needs rebalancing.

---

## 4. Rendering engine changes (the GPU work)

### 4.1 GlassMaterial — the single highest-value piece of new GPU work

Replace `_render_panel_rgba`'s Pillow raster with a real GLSL material, added alongside the existing `_compile()` shader programs in `gpu_render.py`:

1. **Live backdrop capture**: render the scene (background + spectrum + particles + logo, everything *behind* the glass panel in z-order) to an offscreen FBO texture once per frame, as `tex_scene` already effectively is captured for post-processing (`tex_scene`, `tex_out` already exist in the pipeline — extend rather than invent).
2. **Blur pass**: a small two-pass separable Gaussian (horizontal then vertical) GLSL blur on the *panel's screen-space rect only* (not the whole frame — bounded to `panelWidth`/`panelHeight` + padding for performance), sampling `tex_scene`.
3. **Glass fragment shader**: SDF rounded-rect distance field for crisp, resolution-independent corners (`sdRoundedBox` — a standard, cheap GLSL function) driving: fill tint+opacity, hairline border (`smoothstep` ring at the SDF boundary), and a separate outer soft glow (second, larger SDF evaluated with a blur-like falloff, additive-blended — this replaces the current single-Gaussian "outer_glow" hack with a real analytic glow that's cheap and infinitely resizable without re-rasterizing).
4. **Gradient fill**: for active-row pills, a simple `mix()` across the SDF box's local U coordinate — trivial in-shader, removes the need for Pillow gradient rasterization entirely.
5. **Optional noise**: a tiny procedural noise function (or a small tileable noise texture) added at low amplitude inside the fill for "acrylic" texture.

This one change addresses critique items 1 ("glass panel too opaque, no blur"), 2 ("corner radius"), 3 ("border too thick, should be hairline + glow"), and most of item 4's visual-weight complaint (since a true glass fill recedes automatically at 15-20% opacity instead of reading as a gray box).

**Why this is worth the engineering cost vs. tuning Pillow further:** Pillow can approximate blur and gradients, but it **cannot sample the live composited scene** behind the panel every frame at interactive framerate — a static one-time blurred crop can never track particles/spectrum motion behind the glass, which is the #1 reason the current panel reads as "a sticker" rather than "glass in the scene." This is a hard architectural ceiling, not a tuning problem, matching what I told you in the prior turn.

### 4.2 Typography — keep Pillow for glyphs, change how it's composited

Rewriting a full text shaper in GLSL is not worth it. Keep Pillow/FreeType for glyph rasterization (this is the *correct* tool for text), but:
- Route the resulting glyph-alpha texture through the **same glow/bloom shader** the GlassMaterial uses (so "now playing" glow is a real analytic glow matching the panel's glow language, not a separate Gaussian-blurred PIL layer with different falloff characteristics).
- Pre-bake hierarchy (opacity/weight/size) from tokens (§3.2) instead of per-call magic numbers scattered through `playlist_list_card.py`.
- Cache per-glyph-run textures (already done via the `key_list`/cache mechanism) — this part of the architecture is fine and should be preserved.

### 4.3 Spectrum + Particles — smaller, targeted upgrades

These are already GPU-native and don't need a rewrite, but to reach "premium," add:
- **Shared glow/bloom pass**: currently the logo, particles, and (new) glass material would each have their own glow math. Introduce one shared bright-pass+blur+additive-composite bloom pass at the end of the frame (bright-pass threshold on the whole composited scene, 2-3 mip levels of blur, additive back onto the final image) — this is what makes the *whole frame* feel like one coherent glowing world instead of five independently-glowing elements. This directly answers the critique's "neon energy radiates outward" and "logo doesn't belong to the scene" (light spill) requests: with a scene-wide bloom pass, the logo's brightness naturally bleeds onto nearby pixels (including car body) with zero extra per-element code.
- **Particle depth/parallax**: bias particle size/opacity/blur slightly by a pseudo-depth value so some particles read as "closer/bigger/sharper" and others "farther/smaller/softer" — cheap (one extra per-particle attribute), large perceived-quality win for "floating particles drifting through the scene."
- **Orbit-spikes tuned as the default "circular spectrum around subject" style**: confirm/verify `orbit-spikes` (already present) is exposed as a first-class, well-tuned preset — since it is architecturally the same primitive as the reference image's ring-of-light effect (concentric ring + radial bars around a circular subject). If a dedicated "portrait ring" preset doesn't already look like the reference, that's a tuning task on an existing style, not new engineering.

### 4.4 SceneCompositor — ties it together

A small new module (`visualizer/scene_compositor.py`) responsible only for z-order + the shared bloom pass + the visual-weight-budget sanity check from §3.3. Every existing draw call keeps happening where it already happens in `gpu_render.py`; this module just owns "capture to FBO → shared bloom → final composite," replacing the current ad hoc `tex_scene`/`tex_out` juggling with one documented, testable seam.

---

## 5. Look presets rebuilt on tokens (product-facing outcome)

Once §3-4 exist, a "Look" (today: `PLAYLIST_LOOK_PRESET_PATCHES` in `text_domain_registry.py`, plus separate spectrum/particle/logo presets elsewhere) becomes **one `VideoLookTheme` object** per Look, e.g.:

```python
CYBERPUNK_HUD = VideoLookTheme(
    palette=Palette(primary="#3fa9ff", accent="#a855f7", glow="#67e8f9"),
    glass=GlassTokens(opacity=0.18, blur_radius=20, corner_radius=14,
                       border_width=1.5, border_glow_radius=12, tint="#3fa9ff"),
    typography=TypographyTokens(title_font="rajdhani", now_playing_glow=0.25),
    spectrum=SpectrumTokens(style="orbit-spikes", glow=0.6),
    particles=ParticleTokens(density=0.35, glow=0.5, spawn_area="ambient_drift"),
    visual_weight=VisualWeightBudget(background=0.20, logo=0.35, spectrum=0.20,
                                       particles=0.10, playlist=0.15),
)
```

This is the literal implementation of "Instead of prompting 'build playlist panel,' give it constraints" — except the constraints live in a typed Python object the renderer consumes deterministically, not in a natural-language prompt re-derived every session. It also directly enables the "reusable template, switch layouts while keeping the same rendering engine" idea from the critique (center logo / left logo / bottom logo / car focus / singer focus become **layout variants that select which VideoLookTheme fields drive position**, while the rendering engine underneath never changes).

---

## 6. Phased delivery plan

### Phase 0 — already done this session (baseline fix, no new engineering)
- Fixed the Neon Glass Pro off-canvas anchor bug (`y: -50 → y: 14` in `text_domain_registry.py`).
- Confirmed via direct math simulation that the card now renders fully on-canvas.
- *Everything below is new scope, not yet started.*

### Phase 1 — Design tokens module (no rendering changes yet)
- New `features/video/lib/design_tokens.py`: `Palette`, `GlassTokens`, `TypographyTokens`, `SpectrumTokens`, `ParticleTokens`, `VisualWeightBudget`, `VideoLookTheme` dataclasses.
- Port 2-3 existing Looks (Neon Glass Pro + one Playlist look) into `VideoLookTheme` objects as a proof of concept, **without changing any renderer code** — just prove the token shape can express what the current dict-based presets express, plus the new fields (noise, border-glow split, visual-weight budget).
- Unit tests: token defaults are in-range, `VideoLookTheme` round-trips to/from the legacy dict shape (needed for backward compatibility with saved templates).

### Phase 2 — GlassMaterial shader (highest visual ROI)
- Add SDF rounded-rect + live-backdrop-blur + hairline-border-and-glow + gradient fill GLSL program to `gpu_render.py`, gated behind a feature flag so it can be A/B'd against the current Pillow panel.
- Wire one Look (Neon Glass Pro, since it's already the reference-reconstruction target) through the new material.
- Manual visual QA against both reference images side-by-side; iterate token defaults, not shader code, to converge.

### Phase 3 — Typography hierarchy + now-playing indicator
- Rewrite `playlist_list_card.py` row-building to pull all opacity/size/weight values from `TypographyTokens` instead of inline constants.
- Add a dedicated now-playing glyph/accent-bar independent of the gradient pill.
- Route glow through the shared bloom pass from Phase 4 once that exists (can temporarily keep Pillow glow in the interim).

### Phase 4 — SceneCompositor + shared bloom pass
- New `scene_compositor.py`; move the existing ad hoc `tex_scene`/`tex_out` bloom logic into one documented bright-pass+blur+composite stage that logo, spectrum, particles, and the new GlassMaterial all feed into.
- This is what produces "light spill from logo onto car," "neon energy radiates outward," and a coherent single-scene feel instead of five independently-lit elements.

### Phase 5 — Particle depth/parallax + ambient presets
- Add per-particle pseudo-depth attribute (size/opacity/blur bias).
- Add an "ambient drift" spawn/travel preset tuned for floating-dust/lens-flare-adjacent atmosphere (distinct from existing reactive/beat-driven particle presets).

### Phase 6 — Look catalog rebuild + visual-weight linter
- Rebuild all existing Looks as `VideoLookTheme` objects.
- Add the automatic "declared visual-weight budget vs. rendered alpha coverage" sanity check (§3.3) as a dev-time diagnostic (not user-facing), to catch future presets that drift back into "everything competes for attention."
- Add 1-2 new example Looks matching the two reference images directly (a "Cyberpunk HUD Playlist" Look, and confirm/tune "Portrait Ring Spectrum" as a first-class preset).

### Phase 7 — Preview/export parity + perf validation
- Confirm the new GLSL GlassMaterial + shared bloom pass produce **identical output** in the live PyQt preview and the offline export path (both already go through the same `gpu_render.py`, so this should mostly be "verify," not "build" — but live backdrop blur bounded to panel rect needs explicit perf testing at preview frame rate).
- Perf budget check: bounded-rect blur (§4.1.2) should be cheap since it only processes the panel's own pixel footprint, not the full frame — validate this holds at 1080p/4K export resolutions too.

---

## 7. File-by-file change map (for the implementation session, once this plan is approved)

| File | Change |
|---|---|
| `features/video/lib/design_tokens.py` | **New.** Token dataclasses + legacy-dict round-trip helpers. |
| `features/video/lib/text_domain_registry.py` | Looks migrate from raw dict patches to `VideoLookTheme`-backed patches (keeps existing dict shape as the serialization format for backward compatibility with saved templates). |
| `visualizer/gpu_render.py` | Add GlassMaterial GLSL program + bounded backdrop-blur FBO pass; add shared bloom pass in `SceneCompositor`; `_render_panel_rgba` becomes a fallback path (kept for non-GPU export contexts if any exist) rather than the primary path. |
| `visualizer/scene_compositor.py` | **New.** Owns z-order + shared bloom + visual-weight diagnostic. |
| `features/video/lib/playlist_list_card.py` | Row/typography building reads `TypographyTokens`; add now-playing glyph/accent-bar. |
| `features/video/lib/playlist_glass_backdrop.py` | Superseded by live GPU backdrop sampling for Looks on the new material; keep as fallback/CPU export path. |
| `visualizer/particles.py` | Add pseudo-depth attribute; add ambient-drift preset. |
| `camxora_python/assets/fonts/` | Add Rajdhani/Orbitron/Exo 2 OFL fonts for HUD-style typography tokens. |
| `camxora_python/tests/test_playlist_phase1.py` + new `test_design_tokens.py`, `test_glass_material.py` | Extend/add coverage per phase. |
| `docs/changelog/2026-07-30-video-page-design-system-revamp.md` | Created once Phase 1+ implementation actually lands (per repo's changelog rule — this planning doc itself is not a changelog entry). |

---

## 8. Risks / tradeoffs (said plainly)

- **This is a real scope increase**, not a config change. Phase 2 (GlassMaterial) alone is new GLSL + FBO plumbing inside an already-large `gpu_render.py`. Budget it as its own focused work session, not a "quick follow-up."
- **Bounded backdrop blur still costs something every frame** in the live PyQt preview. It should be cheap if strictly bounded to the panel's screen-space rect, but must be perf-validated on lower-end hardware, not assumed.
- **Backward compatibility**: existing saved templates store the current dict-shaped Look/spectrum/particle presets. The token system must serialize to/from that same dict shape so old project files keep loading — this is explicitly designed for in Phase 1 (round-trip helpers) rather than a "migrate later" afterthought.
- **Don't over-rotate into a generic game-engine effort.** The goal is a *design system* (tokens + a handful of reusable materials/passes), not a fully generic shader graph editor. Keep the token vocabulary tied to the actual Looks/aesthetics Camxora ships (cyberpunk HUD, premium glass, EDM neon, etc.), not an open-ended abstraction.
- **Visual QA is inherently subjective.** The visual-weight budget (§3.3) and phased reference-image comparisons (Phase 2, Phase 6) are there specifically to keep iteration anchored to the two reference images instead of drifting on taste alone.

---

## 9. Acceptance criteria (how we'll know this worked)

1. Side-by-side against the "singer in circular spectrum" reference: logo/subject reads as the clear focal point (35%+ visual weight), ring spectrum pulses convincingly to audio, particles drift ambiently without competing for attention.
2. Side-by-side against the Thunder Bass playlist-over-car screenshot: playlist card reads as translucent HUD glass (not a gray dialog box), border is a hairline+glow (not a thick bright ring), now-playing row is unmistakable via a dedicated indicator + brightness contrast (not just a colored pill), and light from the logo visibly influences nearby scene elements.
3. A new Look can be authored by setting ~15-20 token values and gets a coherent glass/typography/spectrum/particle treatment automatically, without hand-tuning Pillow blur radii per text run.
4. Preview and export remain pixel-parity (same `gpu_render.py` path for both).
5. No regression in the 16 passing tests in `tests/test_playlist_phase1.py` (extended, not replaced, by new token/material tests).

---

## 10. Suggested next step

Approve/adjust this plan (particularly §3's specific token values and §6's phase ordering — Phase 2 GlassMaterial is the single highest-leverage item if you want visible progress fastest), then start implementation with **Phase 1 (tokens, zero rendering risk)** immediately followed by **Phase 2 (GlassMaterial)** since that's the change that most directly fixes both reference images' biggest complaint ("glass panel looks like a dialog box").
