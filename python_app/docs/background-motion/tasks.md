## Background Motion — Tasks

### Goal
Add optional music-reactive background motion in the Python app:
- Vibrate (shake) on audio
- Zoom in/out on audio
Background-only (does not move spectrum/logo/particles).

### Scope
- Python app template settings UI (PyQt) → Background tab
- GPU renderer for export + preview + live preview: `visualizer/gpu_render.py`
- Template defaults + normalization: `python_app/models/spectrum_model.py`

### Out of Scope
- Whole-scene camera motion
- Electron/React editor UI

---

## M1 — Schema + Defaults
- [ ] Add new keys under `backgroundSettings`:
  - `motionMode`: `"none" | "zoom" | "vibrate" | "both"` (default `"none"`)
  - `motionZoomStrength`: float `0..2` (default `1.0`)
  - `motionVibrateStrength`: float `0..2` (default `1.0`)
- [ ] Normalize/clamp these values in `normalize_template`.

Acceptance
- Old templates behave as before (no new motion unless enabled).
- New templates include defaults.

---

## M2 — Python App UI (PyQt)
- [ ] Add Background Motion section:
  - Mode dropdown: None / Zoom / Vibrate / Both
  - Zoom Strength slider (visible when mode includes zoom)
  - Vibrate Strength slider (visible when mode includes vibrate)
- [ ] Bind controls to `self.template["backgroundSettings"]` and refresh preview.

Acceptance
- Changing mode/strength updates the live preview immediately.

---

## M3 — Renderer (GPU Export + Preview + Live Preview)
- [ ] Parse new motion keys in all three renderer entrypoints:
  - MP4 export loop
  - Preview PNG render
  - Live preview render
- [ ] Apply zoom and vibrate to background only:
  - Zoom maps to shader `bg_scale`
  - Vibrate maps to shader `bg_offset`

Acceptance
- Export MP4 and live preview behave consistently for motion.

---

## M4 — Verification + Logging
- [ ] `python -m compileall -q python_app visualizer` passes
- [ ] App launches to Video page without crash
- [ ] Update `python_app/DEVELOPMENT_LOG.md`
