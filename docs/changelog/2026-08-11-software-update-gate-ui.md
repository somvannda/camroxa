# Software update gate — landscape UI polish

**Date:** 2026-08-11  
**Surfaces:** `camxora_python`  
**Branch:** `feature/software-update-gate-ui`

## Summary

Redesigned the mandatory software-update dialog: simplified centered card with
Camxora logo (no brand text label), short body + version meta, compact Install
CTA, soft progress track, and professional installer-focused copy. What’s new
is intentionally omitted from the gate.

## Product impact

- Cleaner mandatory-update gate hierarchy and less vertical stretch.
- What’s new only shows when real user-facing bullets exist.
- Body copy no longer repeats version numbers or brand name.

## Technical impact

- Gate widget layout + QSS in `deep_blue.py`.
- `format_update_summary` / `format_whats_new` copy helpers.
- Dev preview: `CAMXORA_PREVIEW_UPDATE_GATE=1` injects a fake mandatory offer at
  startup so the dialog can be reviewed without publishing.

## Files touched

- `camxora_python/shared/widgets/software_update_gate.py`
- `camxora_python/shared/themes/deep_blue.py`
- `camxora_python/shared/lib/software_update_copy.py`
- `camxora_python/app/root_window.py`
- `camxora_python/tests/test_software_update_copy.py`
- `CHANGELOG.md`
- `docs/changelog/2026-08-11-software-update-gate-ui.md`

## Migration / deploy

- Local: restart the desktop app (or set `CAMXORA_PREVIEW_UPDATE_GATE=1`).
- No API / admin / sandbox deploy required (desktop UI only).

## Tests

- `pytest camxora_python/tests/test_software_update_copy.py`
- Manual: `CAMXORA_PREVIEW_UPDATE_GATE=1` → launch app → confirm layout.

## Follow-ups

- None.
