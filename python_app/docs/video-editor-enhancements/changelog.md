## Change Log

### Summary
- Added Spectrum ON/OFF toggle (applies to preview + export).
- Added Logo “Spin (CD)” effect with direction and speed (applies to preview + export).
- Implemented background fit modes (cover/contain/original) with drag + wheel scale editing in preview, exporting exactly what preview shows.

### UX Notes
- Enable background edit mode in Background tab to drag the background in preview; mouse wheel changes background scale.
- Fit mode prevents stretching when changing output resolution.

### Affected Files
- `python_app/models/spectrum_model.py`
- `python_app/views/settings_view.py`
- `python_app/views/components.py`
- `python_app/views/video_view.py`
- `python_app/app/main_window.py`
- `python_app/visualizer/gpu_render.py`
- `python_app/docs/video-editor-enhancements/{tasks.md,design.md,technical.md}`

