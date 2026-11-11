# LRC background tasks no longer log shutdown tracebacks

**Date:** 2026-11-09
**Surface:** `platform_api`
**Branch:** `fix/lrc-task-hygiene`

## Summary

Every API restart logged `ERROR [asyncio] Task exception was never retrieved` with
`InterfaceError('pool is closing')` from `StreamingUploadService._upload_web_music_lrc`.
The LRC upload is fire-and-forget, so when the pool closed first nobody retrieved
the exception. Seen during the 8 Nov and 9 Nov deploys.

## Technical impact

- `streaming_upload_service.py`
  - New `_log_background_task_error()` done-callback: consumes successful and
    cancelled tasks, logs `pool is closing` at debug, and any real failure at
    warning (so genuine bugs stay visible).
  - The LRC task now registers the callback.
- `tests/test_streaming_lrc_task_hygiene.py` (new, 3 tests): pool-closing error
  consumed, other errors warned, success/cancel ignored.

## Migration/deploy

No schema change. API-only deploy.

## Tests

```bash
python -m pytest platform_api/tests/test_streaming_lrc_task_hygiene.py \
  platform_api/tests/test_web_music_b2_ingest_retry.py -q   # 7 passed
```

Ruff reports only pre-existing unused locals in `streaming_upload_service.py`.

## Follow-ups

- The other fire-and-forget `create_task` calls in the same service (streaming
  upload, WAV, asset recovery) should get the same callback.
