# 2026-08-29 — Desktop Video studio restyle

Local desktop only. Sandbox and production were not deployed.

## Summary

Video still used the old slate / sky-blue card look. It now matches the Create studio design system used by Dashboard, Music, Image, Progress, Workflow, Marketplace, and Settings.

Preview, template CRUD, inspectors, playback, and export / merge behavior are unchanged.

## Product impact

- In-page CreateHeader gives Video a studio page title (the generic shell header was already hidden)
- Left rail, preview stage, inspector, and export cards use navy studio panels
- Domain tabs, Save, Play, and Manual Export use purple selected / primary chrome
- Export track selection uses brand purple instead of sky blue

## Technical impact

- `VideoView` applies `build_video_page_qss()`
- Loading card is `StudioPanel`; existing `SettingsPanel` rails pick up studio colors via scoped QSS

## Files touched

- `camxora_python/features/video/views/video_view.py`
- `camxora_python/features/video/video_styles.py`
- `camxora_python/features/video/widgets/left_rail.py`
- `camxora_python/features/video/widgets/export_queue_panel.py`
- `camxora_python/tests/test_video_view.py`
- `CHANGELOG.md`
- `docs/changelog/2026-08-29-desktop-video-studio-ui.md`

## Migration/deploy

None. Desktop UI only.

## Tests

- `python -m pytest camxora_python/tests/test_video_view.py -q`
