# Connect error copy + null sample path + hide User reference

**Date:** 2026-08-06  
**Branch:** `bugfix/connect-error-and-null-sample-path`  
**Surfaces:** `camxora_python`, `platform_api`

## Summary

Production user (Sophay) hit a developer-oriented ConnectError on login and image jobs failed after force-regen cleared sample paths. Also hide unfinished **User reference** until P2.

## Fixes

### Desktop

- Release/sandbox ConnectError and health unreachable messages no longer mention `uvicorn` / port 8000; local/dev keeps the start hint.
- Preferences + Image page source combos: **Category** and **Prompt only** only.
- Saved `personal_reference` normalizes to **category**.

### Platform API

- `_resolve_runtime_sample_path`: `input_image_path is None` no longer becomes literal path `"None"` (`str(None)`). Missing/stale stored refs fall through to Category sample rotation; clear error if no packs.
- `_read_image_file` rejects empty / `"None"` / `"null"`.

## Why images failed

Force regenerate (`POST /image-jobs/retry` `force=true`) intentionally NULLs sample paths so runtime can re-pick. Runtime treated `None` as path `"None"` and raised **Image reference file does not exist** before rotation. Not related to `persist_batch_run_dir`.

## Verification

- `camxora_python`: `pytest tests/test_connect_error_messages.py tests/test_settings_workspace.py`
- `platform_api`: null-path tests in `tests/test_image_job_service.py`
