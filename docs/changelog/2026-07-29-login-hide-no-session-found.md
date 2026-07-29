# Hide “No session found” error on login

**Date:** 2026-07-29  
**Status:** implemented (no deploy yet)

## Summary
When there are no saved session tokens (fresh install / cleared session), the desktop app now routes to the login screen without showing “No session found.” as an error pill.

## Product impact
**Before:** Login screen displayed an error-style line (“No session found.”) even though the user simply needs to sign in.  
**After:** Login screen stays clean; only real authentication/validation failures show an error.

## Technical impact
- `SessionService.run_bootstrap()` now returns an empty login message when tokens are missing, so `RootWindow` does not call `AuthView.set_error()`.

## Files touched
- `camxora_python/shared/services/session_service.py`

## Migration / deploy
- No migrations.
- Restart the desktop app to pick up UI behavior changes.

## Tests
- Linted updated module (no linter errors).

## Follow-ups
- If you want, we can add an automated UI test for “fresh install” bootstrap flow to prevent regressions.

