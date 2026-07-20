# ExportCoordinator refactor (REQ-2.5)

**Date:** 2026-07-20  
**Status:** implemented (local)

## Summary

Centralized manual GPU export routing in `ExportCoordinator` with a single API for starting exports, cancelling active jobs, and forwarding `MG_EVENT`-shaped progress. Manual export worker now delegates to the coordinator instead of inlining backend selection.

## Product impact

Manual Video tab export behavior is unchanged for users: warm preview still prefers in-process GL when `CAMXORA_INPROCESS_EXPORT=1`, otherwise daemon/subprocess via `ExportJob`. Progress payloads and cancel semantics remain compatible with Progress/Video UI.

## Technical impact

- New `features/video/services/export_coordinator.py` — backend priority: in-process GL → `ExportJob` (daemon → one-shot subprocess).
- `manual_export_worker.py` refactored to use coordinator; `ExportGate` still respected inside coordinator.
- Unit tests: `tests/test_export_coordinator.py`.

## Files touched

- `camxora_python/features/video/services/export_coordinator.py` (new)
- `camxora_python/features/video/workers/manual_export_worker.py`
- `camxora_python/tests/test_export_coordinator.py` (new)

## Migration / deploy

No migrations. Optional env `CAMXORA_INPROCESS_EXPORT=1` unchanged.

## Tests

- `pytest camxora_python/tests/test_export_coordinator.py`
- Existing export-related tests in `camxora_python/tests/`

## Follow-ups

- Route pipeline batch export through coordinator (REQ-2.5 full scope).
- Explicit daemon vs subprocess backend tagging in progress events (REQ-2.6).
