# Window chrome click hit-test fix

**Date:** 2026-08-04  
**Branch:** `bugfix/window-chrome-click-hit-test`  
**Surface:** Desktop (`camxora_python`)  
**Shipped in:** **1.2.0** (`CamxoraSetup-1.2.0.exe`)

## Problem

Some Windows users could not click UI controls accurately in the **windowed** (non-maximized) shell: dropdowns, calendar pickers, scrollbars, and buttons required clicking offset from the painted control, or felt dead. **Maximized** mode worked normally.

## Root cause

Windowed chrome used:

- `WA_TranslucentBackground`
- `QWidget.setMask()` rounded region

Maximized mode already called `clearMask()`. The translucent + mask combo misaligns mouse hit-testing vs painting on some DPI / multi-monitor setups.

## Fix

- Stop using `setMask()` and translucent background on the main shell.
- Keep frameless custom title bar.
- Keep rounded look via Windows 11 **DWM** corner preference + QSS `border-radius: 8px` on opaque `#window_surface`.
- Paint `QMainWindow` opaque `#0f1923` so corner pixels match the shell.

## Files

- `camxora_python/shared/lib/window_chrome.py`
- `camxora_python/shared/themes/deep_blue.py`
- `camxora_python/tests/test_window_chrome_hit_test.py`

## Verify

1. Windowed mode: click combos, date pickers, scrollbars, buttons — hit targets match visuals.
2. Windows 11: outer corners still look rounded (~8px).
3. Maximize / restore still works; custom header unchanged.
4. `pytest camxora_python/tests/test_window_chrome_hit_test.py`
