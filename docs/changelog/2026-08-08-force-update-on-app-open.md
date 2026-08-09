# Force update only when opening the app

**Date:** 2026-08-08  
**Surfaces:** `camxora_python`  
**Branch:** `feature/force-update-on-app-open`

## Summary

Mandatory desktop updates no longer interrupt a live session via WebSocket.
The app checks the public published release **before login / relogin / studio**
and shows the blocking gate only then.

## Behavior

1. Startup (and again before login, auth submit, logout→login, and entering shell)
   calls `GET {api}/public/desktop-release` off the UI thread.
2. If `mandatory` and version newer than the running build → blocking update gate;
   login and shell stay unreachable until install.
3. Network / 404 → fail-open (continue) unless a prior mandatory update is still
   persisted on disk.
4. Mid-session `software_update.available` WebSocket events never show the blocking
   gate. Instead a green **arrow-up-circle** icon appears in the title bar
   immediately left of the notification bell (tooltip: “Update available — vX.Y.Z”).
   Click starts the same install flow; progress overlay appears only after the user
   chooses to update. Mandatory still forces on the **next** app open.

## Note for 1.2.0 → 1.2.1

Clients still on **1.2.0** do not have this on-open check. They need a one-time
manual install of `CamxoraSetup-1.2.1.exe`, or a live push while on 1.2.0 (old
behavior). From **1.2.1** onward, publishing a newer mandatory release forces on
the next app open only.

## Files

- `camxora_python/shared/services/desktop_release_client.py`
- `camxora_python/shared/workers/software_update_check_worker.py`
- `camxora_python/app/root_window.py`
- `camxora_python/shared/services/push_notification_hub.py`
