# Desktop: save a diagnostics file while signed out

**Date:** 2026-11-09
**Surface:** `camxora_python` (desktop)
**Branch:** `feat/desktop-save-diagnostics`

## Summary

"Send diagnostics" uploads logs to support, but it requires an authenticated
session — exactly what a user does **not** have after the "Unauthenticated"
sign-out. Support had no way to get evidence from that state.

## Change

- Sign-in screen: new flat link **“Save diagnostics file”** below *Continue with
  Google*. It writes the same redacted snapshot the uploader sends to
  `~/Downloads/Camxora-diagnostics-<timestamp>.txt` and opens the folder.
  Works signed out, never uploads, no privacy change.
- `shared/services/log_sync.py`: `write_diagnostics_snapshot(directory=None)`
  reuses `build_client_log_payload()` (the logger already redacts secrets) and
  prefixes version + timestamp. Returns `None` when there is nothing to save.
- Tests: `tests/test_diagnostics_snapshot.py` (content written, empty case).

## Notes

- The authenticated **Settings → Send diagnostics** upload is unchanged.
- Ships with the next desktop installer (not deployed on its own).

## Tests

```bash
cd camxora_python
python -m pytest tests/test_diagnostics_snapshot.py tests/test_telemetry_app_version.py -q
# 5 passed
python -m ruff check shared/services/log_sync.py features/account/views/auth_view.py \
  tests/test_diagnostics_snapshot.py
# All checks passed
```
