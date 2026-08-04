# Black live preview from ModernGL alpha-only clear

**Date:** 2026-08-04  
**Status:** implemented  
**Surfaces:** `camxora_python` (Video live preview)

## Summary

After pulling latest `main` (preview P0 Alpha_Lock) into a local
`python main.py production` run, Video preview stayed solid black even though
background/logo textures uploaded and `paintGL` kept running (`bg=True`).

Root cause was **not** the GLSL `noise2` rename. End-of-frame
`_force_framebuffer_opaque_alpha` used:

```python
ctx.color_mask = (False, False, False, True)
ctx.clear(0, 0, 0, 1)
```

ModernGL’s `Context.clear` **ignores** the color mask and clears RGB as well,
so every frame was drawn then wiped to black.

## Fix

Use raw OpenGL `glColorMask` + `glClear` for the alpha-only pass (RGB preserved).

## Files

- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/tests/test_preview_opaque_alpha.py`
- `docs/changelog/2026-08-04-preview-black-moderngl-alpha-clear.md`
