## Change Log

### Summary
- Add Output resolution selector to Video workspace so preview aspect ratio matches the selected resolution.
- Expand resolution preset list while keeping one shared source of truth across Settings, Profiles, and Video workspace.

### Affected Files
- `python_app/views/resolution_presets.py` (new shared preset list)
- `python_app/views/music_view.py` (Settings + Profiles dropdowns now use shared preset list)
- `python_app/views/video_view.py` (Video workspace dropdown added)
- `python_app/views/components.py` (`AspectRatioBox.set_ratio()` applies immediately)
- `python_app/app/main_window.py` (persist `outputResolution` + update preview ratio)
- `python_app/docs/video-resolution-presets/design.md` (preset list updated)
