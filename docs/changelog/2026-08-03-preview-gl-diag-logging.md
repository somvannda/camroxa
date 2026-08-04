# Preview GL diagnostics land in AppData support logs

**Date:** 2026-08-03  
**Status:** implemented (desktop local; full app restart required)

## Summary

Rare “see-through preview / background+logo never appear” reports had no useful
trail because preview OpenGL breadcrumbs wrote to `debug.log` beside the package
(`Program Files\Camxora\_internal\…`), which is often unwritable on frozen
installs. Failures were silent in `%LOCALAPPDATA%\Camxora\logs\camxora-*.log`.

## Fix

- New `visualizer/preview_diag.py` writes always-on lines to
  `%LOCALAPPDATA%\Camxora\logs\preview-gl-diag.log` (same pattern as
  `audio-load-diag.log`).
- Important lifecycle/load/init errors also mirror into the daily
  `camxora-*.log` under category `[preview-gl]`.
- `load_background` / `load_logo` / `initializeGL` catch failures, validate the
  Qt GL context before texture upload, and record GPU vendor/renderer.
- Diagnostics / Copy Diagnostics now include `glReady`, `lastGlError`,
  `bgTexSize`, and `glInfo`; error guidance points support at
  `preview-gl-diag.log`.

## Files

- `camxora_python/visualizer/preview_diag.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/features/video/lib/video_workspace_diagnostics.py`
- `camxora_python/tests/test_preview_gl_diag.py`
- `docs/changelog/2026-08-03-preview-gl-diag-logging.md`
- `CHANGELOG.md`
