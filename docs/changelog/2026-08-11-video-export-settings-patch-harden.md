# 2026-08-11 — Harden video export settings save (no QThread crash)

## Summary

Changing Resolution / FPS / Speed / Workers on the Video export panel could
crash with `QThread: Destroyed while thread 'PatchSettingsWorker' is still
running` when rapid edits replaced an in-flight settings worker. Saves are now
coalesced and local prefs mirror export options so values survive a restart
even if the API patch is delayed.

## Changes

- Debounced, single-flight `PatchSettingsWorker` queue for export option patches.
- Never overwrite a live settings worker reference; flush pending after finish.
- Resolution API save uses the same queue (local prefs still write immediately).
- Mirror FPS / workers / speed / tier into video workspace prefs; load prefers
  local prefs over cloud settings.
- Flush pending settings patch when leaving the Video page.
- Resolution preview refresh is scheduled (less aggressive while playing).

## Surfaces

- `camxora_python` desktop only.
