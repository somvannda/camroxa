## Existing Rendering

### Preview
- `SpectrumPreview.paintGL()` renders:
  - Background (`prog_scene`, `tex_bg`)
  - Particles
  - Spectrum geometry (`vao_lines`)
  - Logo quad (`prog_logo`, `tex_logo`)
  - Text overlays
  - See [components.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/components.py#L532-L1131)

### Export
- GPU renderer uses GLSL strings in [gpu_render.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/visualizer/gpu_render.py#L87-L339) and draws similar passes.

## Data Model

### New Template Fields
- Top-level:
  - `spectrumEnabled: bool`
- `logoSettings`:
  - `spinEnabled: bool`
  - `spinDirection: str` in `{"cw","ccw"}`
  - `spinSpeed: float` (degrees/sec)
- `backgroundSettings`:
  - `fitMode: str` in `{"cover","contain","original"}`
  - `userScale: float` (1.0 default)
  - `userOffsetX: float` (pixels)
  - `userOffsetY: float` (pixels)

## Implementation Plan

### 1) Spectrum Toggle
- Preview: guard the spectrum draw loop in `paintGL()` with `if spectrumEnabled`.
- Export: guard the spectrum geometry render loop similarly.

### 2) Logo Spin (Shader)
- Add a `time_sec` uniform to the logo shader and a `logo_rot_rad` uniform.
- In `fs_logo`: rotate UV around `(0.5, 0.5)` before sampling.
- Compute `logo_rot_rad = radians(spinSpeedDegPerSec) * time_sec * dir`.

### 3) Background Fit + Drag/Scale (Shader)
- Add uniforms:
  - `bg_tex_size` (vec2)
  - `bg_fit_mode` (int: 0 cover, 1 contain, 2 original)
- In `fs_scene`, compute an aspect-correct UV mapping based on `out_size` and `bg_tex_size`.
- Apply user + audio transforms through existing `bg_scale` and `bg_offset` by composing:
  - `bg_scale = userScale * audioScale`
  - `bg_offset = (userOffsetPx / out_size) + audioOffset`

### 4) Preview Interactions
- Add a background edit toggle; when enabled:
  - Drag updates `backgroundSettings.userOffsetX/Y`.
  - Wheel adjusts `backgroundSettings.userScale`.
- Keep existing drag behavior for spectrum position when background edit mode is off.

