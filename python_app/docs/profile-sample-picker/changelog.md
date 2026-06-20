## Change Log

### Summary
- Replaced Profile “Background/Thumbnail samples (one path per line)” text fields with selectable lists loaded from the chosen samples directory.
- Added Reload buttons and automatic refresh when the directory changes.
- Manual selection supports up to 5 samples; Random mode disables manual selection.

### UX
- Set Samples Dir → list auto-populates.
- Manual: uncheck Random → select up to 5 images from the list.
- Random: check Random → list is disabled and selection is cleared.

### Affected Files
- `python_app/views/music_view.py`
- `python_app/app/main_window.py`
- `python_app/docs/profile-sample-picker/{tasks.md,design.md,technical.md,changelog.md}`

