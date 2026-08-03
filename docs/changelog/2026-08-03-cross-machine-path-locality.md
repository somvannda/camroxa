# Cross-machine Windows profile paths + startup import retry

**Date:** 2026-08-03
**Status:** implemented (desktop v1.0.15; includes 1.0.14 merge-readiness)

## Summary

Two related production reports from a second Windows machine (`C:\Users\PC\...`)
logged into the same Camxora account as the developer's machine
(`C:\Users\Kong Somvannda\...`):

1. Every startup attempted to create account-synced media folders under
   `C:\Users\Kong Somvannda\AppData\Local\Camxora\...`, which Windows denies
   on the PC profile → multi-level `PermissionError` cascades in the log
   (app continued via self-heal, but noisy and confusing).
2. A separate launch failed during the initial import chain with
   `TypeError: 'tuple_iterator' object does not support the context manager
   protocol` inside pydantic while building `MusicLanguageListResponse`. Only
   attempt 1/2 was logged; a single 1.5s retry is sometimes not enough when
   Defender is still scanning the install.

## Product impact

**Before:** Opening Camxora on a second PC under the same account spammed
PermissionError for the first machine's `C:\Users\...` paths, and occasional
cold starts could die on a flaky pydantic import after one retry.

**After:** Foreign `C:\Users\<other>\...` paths are ignored up front and
replaced with this machine's `%LOCALAPPDATA%\Camxora\Media\...` defaults
(shared drives like `D:\` / `E:\SUNO` are unchanged when usable). Startup
import failures retry up to 4 times with growing backoff and log recovery
when a later attempt succeeds.

## Technical impact

- New `shared.lib.path_locality` helper detects paths under a different
  Windows Users profile (allows Public / shared profiles; ignores non-Users
  paths).
- `apply_workspace_path_defaults` / `ensure_directory` (workspace +
  file_service) and pending music-download sync skip mkdir/download into
  foreign profiles entirely.
- `run_entry._run_desktop_with_retry` defaults to 4 attempts, `1.5 * attempt`
  sleep, `gc.collect()` between tries, recovery log line, and alternate
  crash-log paths next to the executable.

## Files touched

- `camxora_python/shared/lib/path_locality.py` (new)
- `camxora_python/shared/lib/workspace_defaults.py`
- `camxora_python/shared/services/file_service.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/run_entry.py`
- `camxora_python/tests/test_path_locality.py` (new)
- `camxora_python/tests/test_workspace_defaults.py`
- `camxora_python/tests/test_run_entry_retry.py`
- version bump to 1.0.15 + `CHANGELOG.md`

## Migration / deploy

Desktop-only. No platform_api / DB changes. Ships in the v1.0.15 production
installer (combined with the 1.0.14 Continue→Merge readiness fix). After
install on the second machine, one login self-heals path settings back to
that machine's defaults (and PATCHes the healed values).

## Tests

- `pytest camxora_python/tests/test_path_locality.py -v`
- `pytest camxora_python/tests/test_workspace_defaults.py -v`
- `pytest camxora_python/tests/test_run_entry_retry.py -v`
