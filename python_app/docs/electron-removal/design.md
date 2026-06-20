## Electron App Removal (Archive) - Design

### Product Goal
Make the repository Python-first and reduce confusion by removing the Electron/React/Vite application from the active project root.

### User Impact
- Users working on Python will no longer see frontend build/config folders in the root.
- Electron code is preserved under `archive/electron-app/` for future reference or rollback.

### UX / Workflow
- Primary entrypoint becomes Python-only:
  - Run from repo root: `python -m python_app`

### Non-Goals
- No UI changes inside the Python app in this task.
