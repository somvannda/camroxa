# Desktop Diagnostics console (missing view for the `log` route)

**Date:** 2026-11-07
**Surface:** `camxora_python` (desktop)
**Branch:** `desktop/diagnostics-console`

## Problem

`app/router.py` mapped the support-only `log` route to
`features.logs.views.log_view.LogView`, but that module had never existed in
this repository (no commit, on any ref). Consequences:

- Navigating to `/app/log` raised `ModuleNotFoundError` and left the shell
  stack on the previous page.
- `tests/test_application.py::test_router_navigates_all_routes` failed on
  `main`, because it navigates every registered route.
- The route is only exposed when `CAMXORA_SHOW_DIAGNOSTICS=1`, which is why the
  breakage went unnoticed in normal builds.

A second, hidden cause: `.gitignore` line 2 is the bare pattern `logs`, which
matches **any** directory named `logs` at any depth — including
`camxora_python/features/logs/`. New files there were silently untracked (an
earlier `git stash -u` skipped them entirely). The file already carried two
`!…/logs/` negations for web route folders, so this was a known sharp edge.

## Change

| Place | Change |
|---|---|
| `camxora_python/features/logs/views/log_view.py` | New `LogView`: reads `AppLogger`'s ring buffer, follows `bus.line_emitted`, level filter (all / info+ / warn+ / error), pause-with-buffer, follow toggle, copy-all, confirmed clear. Records are already redacted by the logger. |
| `camxora_python/features/logs/{__init__,views/__init__}.py` | New package markers. |
| `camxora_python/shared/services/app_logger.py` | Added `record_count()` so the console can show "shown of buffered" without copying the 5 000-record deque on every line; removed the unused `Callable` import. |
| `.gitignore` | Added `!camxora_python/features/logs/` so the package is trackable. |
| `camxora_python/tests/test_log_view.py` | New tests for seeding, live follow, filtering, pause/flush, clear, and the line cap. |

The console never reads log files and never blocks the UI thread: cross-thread
records arrive through the existing queued Qt signal, and the widget keeps a
bounded `QPlainTextEdit` (`maximumBlockCount = 2000`).

## Verification

```bash
cd camxora_python
python -m pytest tests/test_log_view.py tests/test_application.py tests/test_navigation.py -q
# 17 passed
python -m ruff check features/logs shared/services/app_logger.py tests/test_log_view.py
# All checks passed
```

## Follow-ups

- The bare `logs` ignore rule should eventually be anchored (`/logs`) rather
  than patched with a growing list of negations.
- The console intentionally has no export button; support should keep using
  Settings → Send diagnostics for uploads.
