## Existing

### Current Preset Source
- Presets are currently hardcoded in Settings UI:
  - Global: [music_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/music_view.py#L856-L862)
  - Per-profile: [music_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/music_view.py#L549-L555)

### Video Workspace Preview
- Preview aspect ratio is derived from `outputResolution` (or fallback) at build time:
  - [video_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/video_view.py#L86-L100)
- Aspect ratio is enforced by `AspectRatioBox`:
  - [components.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/components.py#L92-L136)

### Pipeline Resolution Usage
- Export uses `_resolved_output_resolution()`:
  - [main_window.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L10015-L10024)
- Image generation uses `outputResolution` fallback logic:
  - [image_generation.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/image_generation.py#L62-L66)

## Change Plan

### 1) Shared Preset List
- Create `python_app/views/resolution_presets.py` that returns a preset list (label + `WxH`).
- Replace hardcoded addItem calls in `music_view.py` with the shared list.
- Use the same list in the Video workspace dropdown.

### 2) Video Workspace Dropdown
- Add a `QComboBox` to the Video workspace header.
- On change:
  - Persist to settings with `_persist_setting_patch({"outputResolution": "<WxH>"})`
  - Update preview aspect ratio.

### 3) Update AspectRatioBox
- Add a setter method to update its ratio dynamically without rebuilding the widget tree.

## Risks
- Must avoid duplicate preset definitions (single source of truth).
- Existing saved values remain valid; invalid values fall back via `_parse_output_resolution`.

