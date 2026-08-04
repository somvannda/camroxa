# Preview P3 — translucent chrome audit

**Date:** 2026-08-04  
**Status:** implemented (docs + chrome docstring; no rounded-chrome rewrite)  
**Branch:** `bugfix/preview-p3-chrome-audit` (on top of P0–P2)  
**Spec:** [`docs/PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md`](../PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md) P3

## REQ-P3.1 — Translucent chrome audit

### Why `WA_TranslucentBackground` is set

| Item | Detail |
|------|--------|
| Call site | `configure_rounded_window()` in `camxora_python/shared/lib/window_chrome.py` |
| Caller | `RootWindow.__init__` → frameless studio shell |
| Purpose | Allow **per-pixel clear** outside the 8px rounded mask so corners are not a square black/theme slab |
| Companion | `sync_rounded_window_shape` applies `QRegion` mask (windowed) or `clearMask` (maximized/fullscreen) + DWM corner preference (attr 33) on win32 |
| Theme | `QMainWindow { background: transparent }` so only `#window_surface` paints the shell |

### What breaks if translucency is cleared (without a replacement)

1. **Square opaque corners** behind/around the mask — classic frameless Qt regression.
2. Rounded QSS `border-radius` on `#window_surface` alone does **not** clip the native HWND; without translucency + mask (or DWM-only round), OS still composites a rectangular frame.
3. Maximized path already clears the Qt mask and asks DWM for square corners — translucency attribute remains True; clearing it still risks flash/edge artifacts on restore to windowed.

### Opaque backplate confirmation

| Layer | Role | Opaque? |
|-------|------|---------|
| `QMainWindow` | Host HWND | Transparent (by design) |
| `QWidget#window_surface` | Shell fill `#0f1923` | **Yes — primary opaque backplate** |
| `QFrame#shell_sidebar` / content hosts | Studio chrome | Opaque via theme |
| Custom `WindowTitleBar` | Controls; idle paint alpha 0 | Sits on opaque `window_surface` |
| `VideoSpectrumPreview` (`QOpenGLWidget`) | Live preview FBO | Must keep **FBO alpha = 1** (P0) or desktop shows through |

### Other `WA_TranslucentBackground` widgets

| Widget | Path | Overlaps preview host? |
|--------|------|-------------------------|
| Root window | `window_chrome.py` | Yes (owns the HWND that composites the preview) |
| `TextDragOverlay` | `features/video/widgets/text_drag_overlay.py` | Yes — stacked **on** the preview in `AspectRatioBox`; translucent so handles sit over GL without an opaque card. Does **not** punch the desktop by itself; child of the opaque surface hierarchy. |
| `SetupNotification` dropdown | `shared/widgets/setup_notification.py` | No — title-bar popup, not over the Video stage |

### Audit conclusion (REQ-P3.1 A2)

Keep current chrome. P0 Alpha_Lock + end-of-frame opaque alpha are the correct fix for preview see-through. Clearing root translucency is **not** the default remediation.

## REQ-P3.2 — Safer rounded-window strategy

**Decision: not implemented now.**

Evidence:

1. Root cause of user reports was Preview_FBO alpha &lt; 1 under a translucent HWND (documented in P0), not missing `#window_surface` fill.
2. P0 restores Alpha_Lock on spectrum / particles / lightning and forces alpha = 1 at end of `paintGL`.
3. P1 adds opaque failure UX if GL never comes up (avoids empty transparent holes).
4. Alternate strategies (opaque HWND + DWM-only rounding, or mask without `WA_TranslucentBackground`) need product sign-off on corner fidelity and multi-monitor DPI testing — defer until a GPU still reproduces see-through **after** a build that includes P0.

Revisit P3.2 only if support confirms see-through on P0+ builds with `preview-gl-diag.log` showing healthy `initializeGL ok`.

## Files

- `camxora_python/shared/lib/window_chrome.py` (docstring warning)
- `docs/changelog/2026-08-04-preview-p3-chrome-audit.md`
- `docs/PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md` (§3 pointer)
- `CHANGELOG.md`
