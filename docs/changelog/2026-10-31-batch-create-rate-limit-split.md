# Batch-create rate limit: own bucket + desktop 429 backoff

**Date:** 2026-10-31
**Branch:** `fix/batch-create-rate-limit`
**Surfaces:** platform_api, camxora_python (desktop)

## Summary

Desktop Generate posts **one `POST /batches` per planned day × channel pair**.
That endpoint was classified in the `llm` rate-limit bucket (60 req / 60 s), and
the desktop retries every 429 up to 3 times with 1.5 s / 3 s backoff. A two-week
plan could therefore emit up to 45 requests in ~5 seconds. Once the window closed
every remaining slot failed, so the user saw one identical
`Rate limit exceeded. Please retry later.` line per planned day
(reported by `mr.zhiwei@gmail.com` for 1–15 Nov 2026, 15 of 15 slots).

`POST /batches` only inserts rows and enqueues a worker job — it makes no LLM
call — so sharing the `llm` bucket with `/generation/draft` and the rewrite
endpoints was the wrong classifier.

## Changes

**platform_api**

- `POST /batches` now resolves to its own `batch` endpoint type
  (`BATCH_CREATE_RATE_LIMIT = 120` / 60 s default) instead of `llm`.
- The limit stays admin-tunable: `PUT /admin/rate-limits` with
  `endpoint_type = "batch"` overrides the default within the 5 s cache TTL.
- `/batches/{id}` reads, deletes, `retry-draft` and `retry-suno` keep their
  previous buckets.

**camxora_python**

- `PlatformApiError.retry_after` exposes the 429 cooldown from the
  `Retry-After` header, falling back to the JSON body.
- `create_planned_batches` stops the current sweep on the first 429 instead of
  spending the rest of the plan against a closed window, waits the requested
  cooldown (15 s fallback, 30 s cap), then retries the leftovers.
- A cooldown longer than the cap is not slept through; the run is reported so
  Generate never looks frozen.
- Failures that are all rate limits now render one actionable line
  (`Rate limit exceeded. 15 of 15 batch runs not created. Try again in 60s.`)
  instead of one fragment per day.

## Product impact

- A 15-day, 2-pair plan (30 batches) now fits inside one window with room for
  retries; previously it could not succeed at all.
- Existing installed desktop builds are fixed by the API deploy alone (they
  simply stop being 429'd). The desktop changes harden the retry path and fix
  the error copy.
- No credit or wallet behaviour changed.

## Files touched

- `platform_api/middleware/rate_limit.py`
- `platform_api/tests/test_rate_limit.py`
- `camxora_python/shared/services/platform_client.py`
- `camxora_python/shared/lib/music_batch_plan.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/tests/test_music_batch_plan.py`
- `camxora_python/tests/test_platform_error_retry_after.py`

## Verification

```
python -m pytest platform_api/tests/test_rate_limit.py platform_api/tests/test_batch_router.py -q
python -m pytest camxora_python/tests/test_music_batch_plan.py \
  camxora_python/tests/test_platform_error_retry_after.py \
  camxora_python/tests/test_music_view.py -q
```

(Pre-existing unrelated failure: `camxora_python/tests/test_image_workspace.py::test_build_queue_rows_groups_by_batch_and_role_not_song`
fails on `origin/main` too.)

## Migration / deploy

- API deploy applies the new bucket immediately; no migration needed.
- Optional immediate mitigation without a deploy: raise the `llm` limit from the
  admin console (loosens draft/rewrite limits too — prefer the `batch` bucket).
- Desktop ships with the next installer.
