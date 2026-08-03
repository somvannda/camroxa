# Force update publish: version from form, not filename

**Date:** 2026-08-03
**Status:** implemented (platform_api + admin_portal; deploy separately from desktop installer)

## Summary

Admin "Publish" on an uploaded installer row returned **400 Could not
determine version from installer filename** for real Inno artifacts named
`CamxoraSetup-1.0.14.exe` / `CamxoraSetup-1.0.14-production.exe`. The parser
only accepted `Camxora-{version}.*`, so Force update never went live when
publishing from the installer table.

**Product intent:** Force update must not depend on installer filename shape.
The Software Update form owns Version + Download URL + Force update. The
uploaded file is only the binary to download. Filename parse is a convenience
auto-fill, never a publish gate.

## Fix

- Installer-row publish resolves version in this order:
  1. `version` from the publish request body (form field)
  2. already-saved draft config version
  3. optional filename parse (last resort only)
- 400 only if Version is still empty after that — message tells admins to
  set Version in the form, not to rename the file.
- Filename parser still accepts `CamxoraSetup-` / `Camxora-Setup-` and
  optional `-production`/`-sandbox` so the UI can auto-fill Version when
  possible.
- Admin publish dialog sends the form `version` on installer-row publish.

## How Force update works (admin)

1. Set **Version** (must be newer than what clients are running)
2. Set / upload **Download URL** (any `.exe` / `.msi` / `.zip` name is fine)
3. Check **Force update**
4. Publish

Desktop clients that receive the push (and see a newer version) block until
they install. Filename structure is irrelevant.

## Files

- `platform_api/routers/admin.py`
- `platform_api/services/desktop_release_upload_service.py`
- `platform_api/tests/test_desktop_release_upload.py`
- `admin_portal/src/components/software-updates/release-editor-dialog.tsx`
- `admin_portal/src/components/software-updates/installer-files-table.tsx`
- `admin_portal/src/hooks/use-desktop-notifications.ts`

## Deploy

Sandbox first, then production on request: platform_api + admin_portal only.
