# Desktop startup OpenGL window prime

**Date:** 2026-08-08  
**Status:** implemented locally (desktop-only)

## Summary

During splash startup, Camxora prewarms the Video workspace, which mounts a
`QOpenGLWidget` preview. On Windows, the first OpenGL widget parented into an
already-mapped top-level HWND often recreates that window — so the splash
briefly looks like the app closed and reopened right before “Preparing video
workspace.”

## Product impact

**Before:** splash could flash / taskbar-blink as if Camxora restarted while
still on the loading screen.

**After:** the root window is OpenGL-capable before the first `show()`, so
video prewarm no longer forces an HWND recreate mid-splash.

## Technical impact

- `shared/lib/opengl_startup.py` — `configure_opengl_before_qapplication()`
  (`AA_ShareOpenGLContexts` + default Compatibility 3.3 surface format) and
  `prime_opengl_on_window()` (1×1 hidden `QOpenGLWidget`).
- `app/bootstrap.py` — configure OpenGL before constructing `QApplication`.
- `app/root_window.py` — prime OpenGL on `RootWindow` before startup bootstrap
  / first show.

## Files touched

- `camxora_python/shared/lib/opengl_startup.py` (new)
- `camxora_python/app/bootstrap.py`
- `camxora_python/app/root_window.py`
- `camxora_python/tests/test_opengl_startup.py` (new)
- `docs/changelog/2026-08-08-startup-opengl-window-prime.md`
- `CHANGELOG.md`

## Migration / deploy

- Desktop-only. No API, admin, or portal deploy.
- Verify by launching Camxora and watching the splash through
  “Preparing video workspace” — the window should stay mapped with no close/reopen flash.
