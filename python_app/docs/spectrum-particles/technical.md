## Spectrum Particles v2 — Technical

### Summary
Implement new particle controls and rendering behavior across:
- Web preview: React `ParticlesCanvas.tsx` (Canvas2D)
- Export renderer: Python `visualizer/gpu_render.py` (ModernGL point sprites)
While keeping both sides aligned in math and defaults.

---

## Existing Architecture (Verified)

### Web
- Template state: `template.particlesSettings` in [spectrumTemplateStore.ts](file:///d:/Development/Projects/Electron/MusicGenerator/src/store/spectrumTemplateStore.ts)
- UI controls: particles panel in [LeftPanel.tsx](file:///d:/Development/Projects/Electron/MusicGenerator/src/components/spectrum/LeftPanel.tsx)
- Preview renderer: [ParticlesCanvas.tsx](file:///d:/Development/Projects/Electron/MusicGenerator/src/components/spectrum/ParticlesCanvas.tsx)

### Export (Python)
- Particle simulation: `ParticleSystem` + `ParticleConfig` in [particles.py](file:///d:/Development/Projects/Electron/MusicGenerator/visualizer/particles.py)
- Export pipeline: particle config parsing + render uniforms in [gpu_render.py](file:///d:/Development/Projects/Electron/MusicGenerator/visualizer/gpu_render.py)
- Point sprite shader (current): `vs_points`/`fs_points` in [gpu_render.py](file:///d:/Development/Projects/Electron/MusicGenerator/visualizer/gpu_render.py#L174-L197)

---

## Proposed Schema Changes

### `particlesSettings` (new fields)
- `spawnMode`: `"always" | "reactiveOnly"` (default `"always"`)
- `spawnTrigger`: `"kick" | "bass" | "both"` (default `"both"`)
- `spawnThreshold`: number `0..1` (default `0.15`)
- `reactColor`: hex string (default `"#ffffff"`)
- `reactStrength`: number `0..1` (default `0.65`)
- `style`: `"dot" | "glow" | "ring" | "spark" | "bokeh"` (default `"dot"`)

Backward compatibility
- If these fields are missing, behavior remains the same as current.

---

## Shared Math / Behavior Contract

### Trigger Signal
We use one normalized intensity `t` in both preview and export:
- kick: kick envelope (`kick_pow` in export; `metrics.kick` in preview)
- bass: bass level (`bass` in export; `metrics.bass` in preview)
- both: `max(kick, bass)`

### Spawn Gating
If `spawnMode == reactiveOnly`:
- If `t < spawnThreshold`: effective `spawnRate = 0`
- Else: use existing spawn scaling logic (already audio-scaled), unchanged.

### Color Blending
Per-frame color:
- `mix = clamp01(t) * reactStrength`
- `finalRGB = lerp(baseRGB, reactRGB, mix)`
Export applies via `prog_points["pt_col"]`. Preview applies via computed fill style/gradient.

---

## Rendering Implementation

### Export Shader (ModernGL)
Extend `fs_points` with:
- `uniform int pt_style;`
and implement shape alpha based on `gl_PointCoord`:
- dot: hard circle
- glow: smooth radial falloff
- ring: band between radii
- spark: cross sparkle overlay (two thin bands) + optional glow
- bokeh: large soft falloff

### Preview Canvas
Implement style draw per particle:
- dot: circle fill
- glow/bokeh: radial gradient fill
- ring: stroke circle with alpha
- spark: draw two perpendicular thin rectangles/lines through center + glow

---

## Files To Modify

### Web
- `src/store/spectrumTemplateStore.ts` (schema + defaults + normalize)
- `src/components/spectrum/LeftPanel.tsx` (UI controls)
- `src/components/spectrum/ParticlesCanvas.tsx` (spawn gating + color blend + style draw)

### Python Export
- `visualizer/gpu_render.py` (parse new keys, compute trigger, gating, blended color, shader uniform, shader source)

### Python App Defaults (Optional)
- If Python app uses `python_app/models/spectrum_model.py` as a template source for some flows, update default/normalize to include the new keys:
  - [spectrum_model.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/models/spectrum_model.py#L57-L68)

---

## Testing Strategy
- Preview smoke test: toggle spawn gating and confirm births stop/start.
- Preview smoke test: switch styles and confirm shape changes.
- Export validation:
  - Export same MP3 with same template; confirm visible match (spawn gating + color reaction + style).
- Regression:
  - Particles disabled → no particles drawn.
  - Old templates without new keys → still render as current.

---

## Risk Assessment
- Shader style implementation must not introduce artifacts on different GPUs.
- Preview/export mismatch risk; mitigate by keeping one shared “trigger intensity” definition and matching default thresholds.
