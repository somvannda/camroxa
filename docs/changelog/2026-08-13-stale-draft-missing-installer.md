# Stale draft when the installer file is gone

**Date:** 2026-08-13  
**Surfaces:** `platform_api`, `admin_portal`  
**Branch:** `bugfix/software-update-stale-draft`

## Summary

Deleting `Camxora-1.2.6.exe` removed it from Uploaded installers but left draft
settings at 1.2.6 with a dead download URL. The status card still showed a
draft that had no table row.

## Product impact

- Opening Software Updates resets a leftover draft to the live release when
  its installer is no longer on disk.
- The status card says the draft installer is missing instead of linking a
  404 URL.

## Technical impact

- `get_software_update_config(..., installer_candidates=)` copies live into
  draft when the draft URL is a hosted `/desktop-release/files/` installer
  that is not in the file list.
- Delete installer copies live into draft instead of only clearing the URL.
- External (non-hosted) draft URLs are left alone.

## Files touched

- `platform_api/services/desktop_notification_admin_service.py`
- `platform_api/routers/admin.py`
- `platform_api/tests/test_desktop_notification_admin_service.py`
- `admin_portal/src/components/software-updates/release-status-card.tsx`
- `admin_portal/src/pages/software-updates/index.tsx`

## Migration / deploy

Sandbox `platform_api` + `admin_portal`. Production only on request.

## Tests

- `pytest platform_api/tests/test_desktop_notification_admin_service.py`

## Follow-ups

None.
