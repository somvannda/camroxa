## Background Motion — Technical

### Summary
Implement background-only music-reactive motion (zoom + vibrate) in the Python app.

---

## Current Renderer Behavior (Verified)

### Background draw (GPU)
- Background uses a full-screen quad shader with UV transform:
  - [gpu_render.py:L87-L115](file:///d:/Development/Projects/Electron/MusicGenerator/visualizer/gpu_render.py#L87-L115)
  - `bg_scale` controls zoom (`uv = (uv-0.5)/scale + 0.5`)
  - `bg_offset` controls shake (`uv += offset`)

### Where backgroundSettings are parsed today
- MP4 export: [gpu_render.py:L553-L559](file:///d:/Development/Projects/Electron/MusicGenerator/visualizer/gpu_render.py#L553-L559)
- Preview PNG: [gpu_render.py:L1373-L1379](file:///d:/Development/Projects/Electron/MusicGenerator/visualizer/gpu_render.py#L1373-L1379)
- Live preview: [gpu_render.py:L2175-L2181](file:///d:/Development/Projects/Electron/MusicGenerator/visualizer/gpu_render.py#L2175-L2181)

---

## Schema Changes (Python only)
Add the following keys under `backgroundSettings`:
- `motionMode`: `"none" | "zoom" | "vibrate" | "both"`
- `motionZoomStrength`: float `0..2`
- `motionVibrateStrength`: float `0..2`

Defaults in `python_app/models/spectrum_model.py`:
- `motionMode = "none"`
- strengths = `1.0`

Normalization:
- clamp strengths to `[0..2]`
- if motionMode invalid → `"none"`

---

## Implementation Details

### Audio Envelope
Reuse the already-computed background envelope:
- `bg_audio_env` from `bg_audio_raw = max(bass, kick_pow*0.6)` smoothed by `bg_smoothing`.
This ensures the motion follows the same audio feel as brightness.

### Motion Mapping

**Zoom**
- When mode includes zoom:
  - `bg_scale_live = 1.0 + bg_audio_env * zoom_k * motionZoomStrength`
  - `zoom_k` should be small (e.g. `0.015`) to avoid cropping artifacts.
- Else:
  - `bg_scale_live = 1.0`

**Vibrate**
- When mode includes vibrate:
  - use existing shake state (`bg_shake_state_x/y`) but multiply target by `motionVibrateStrength`
  - feed `prog_scene["bg_offset"]` in normalized UV space
- Else:
  - `bg_offset = (0,0)`

### Where to Apply
Update all three GPU paths to use the same logic:
- MP4 export (main frame loop)
- Preview PNG render
- Live preview render

---

## Files to Modify
- `python_app/models/spectrum_model.py` (defaults + normalize)
- `python_app/views/settings_view.py` (Background tab controls)
- `python_app/main.py` (apply template to controls + update handlers)
- `visualizer/gpu_render.py` (motion parse + uniform updates)

---

## Testing Strategy
- App startup: Video page loads without exceptions.
- Live preview: toggle modes, verify visible motion.
- Export: render a short MP4, verify motion matches preview.
