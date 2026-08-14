# Force update: draft/delete restore previous live

**Date:** 2026-08-13  
**Surfaces:** `platform_api`, `admin_portal`, `camxora_python`, `website`  
**Branch:** `bugfix/force-update-draft-restore`

## Summary

Draft, Unpublish, and delete of a desktop release no longer leave that version
public. Website `/download`, `/changelog`, and in-app force update follow the
**live** snapshot. Putting the newest version back to draft (or deleting it)
restores the previous live version and unpublishes its Release notes post.

## Product impact

- Saving a draft or uploading an installer never changes `/download` or force
  update until Publish.
- Draft / Unpublish / delete of the live installer:
  - stops force update for that version
  - restores the previous live version on `/download`
  - unpublishes matching website Release notes so changelog “Latest” rolls back
- Desktop revalidates the live release on every app open. A confirmed 404 or a
  live version that is no longer a newer mandatory update clears a persisted
  force-update gate. Network failure keeps a previously persisted gate.

## Technical impact

- Live snapshot (`desktop.software_update.live`) is separate from draft keys.
- Previous lives stored in `desktop.software_update.live_history`.
- New admin route: `POST .../installers/{filename}/draft`.
- Delete installer rolls back live if that file was public.
- Desktop `apply_server_release` distinguishes 404 vs unreachable.

## Files touched

- `platform_api/services/desktop_notification_admin_service.py`
- `platform_api/routers/admin.py`
- `platform_api/tests/test_desktop_notification_admin_service.py`
- `platform_api/tests/test_desktop_release_upload.py`
- `admin_portal/src/hooks/use-desktop-notifications.ts`
- `admin_portal/src/pages/software-updates/index.tsx`
- `admin_portal/src/components/software-updates/release-status-card.tsx`
- `admin_portal/src/components/software-updates/installer-files-table.tsx`
- `camxora_python/shared/services/desktop_release_client.py`
- `camxora_python/shared/services/software_update_service.py`
- `camxora_python/shared/workers/software_update_check_worker.py`
- `camxora_python/shared/workers/software_update_worker.py`
- `camxora_python/shared/lib/software_update_copy.py`
- `camxora_python/app/root_window.py`
- `camxora_python/tests/test_desktop_release_client.py`
- `camxora_python/tests/test_software_update_service.py`
- `docs/DESKTOP_DISTRIBUTION.md`

## Migration / deploy

- Sandbox: `platform_api` + `admin_portal` (and `website` rebuild so `/download`
  and `/changelog` pick up restored live data; no website code change required).
- Desktop client revalidation ships in the next installer. Until then, already
  gated clients revalidate only after this desktop build is installed — prefer
  Draft/Unpublish (keeps the file) over Delete if some clients already saw the
  force gate.

## Tests

- `pytest platform_api/tests/test_desktop_notification_admin_service.py platform_api/tests/test_public_desktop_router.py platform_api/tests/test_desktop_release_upload.py -q`
- `pytest camxora_python/tests/test_software_update_service.py camxora_python/tests/test_desktop_release_client.py -q`

## Follow-ups

- Ship a desktop installer that includes the revalidation client so machines
  that already persisted a withdrawn force update clear the gate on next open.
