## Existing

### Profile fields
- `imageConfig.backgroundSamplesDir`, `thumbnailSamplesDir`
- `imageConfig.backgroundSamples`, `thumbnailSamples`
- UI currently uses two QTextEdits for the lists:
  - [music_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/music_view.py#L715-L722)
- Load/save happens in:
  - [main_window.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L4827-L4848)
  - [main_window.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L5132-L5157)

### Directory listing util
- [list_images_in_folder](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/image_generation.py#L26-L49)

## Implementation
- Replace the two QTextEdits with:
  - `music_settings_profile_image_bg_samples_list: QListWidget`
  - `music_settings_profile_image_thumb_samples_list: QListWidget`
- Add Reload buttons next to dir fields.
- Add a debounced refresh when dir text changes, and immediate refresh on Reload.
- Enforce max 5 selection on each list (same pattern as image tab).
- On Save:
  - Read selected `UserRole` paths from the lists and store to `backgroundSamples` / `thumbnailSamples`
- On Load:
  - Populate list from directory and select any saved paths

