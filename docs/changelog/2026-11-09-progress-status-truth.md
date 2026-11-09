# Progress stages, Export/Merge, and YouTube status now follow real state

**Date:** 2026-11-09
**Surface:** `platform_api` (Progress aggregation, YouTube bookkeeping), `camxora_python` (Progress page, direct upload worker)
**Branch:** `fix/progress-status-truth`

## Summary

The Progress page reported three contradictions at once:

- YouTube showed **Published** for rows that were never uploaded. The newest
  upload job per `(batch, profile, role)` was mixed with a **batch-wide**
  aggregate, so one channel's success published its sibling channel too. A
  success also reset the group's failed/pending counts, and `youtube_success > 0`
  alone forced the stage to `Done`.
- Finished rows showed **Export = Not started / Merge = —**. Terminal rows
  (`Done`, `Completed`) skipped run-folder inspection while the API host cannot
  see the desktop's files, so it fell back to `"Waiting for image assets"` / `"—"`.
- Completed rows showed **Progress = —**, and **Active Runs** counted them as
  in-flight.

## Product impact

- The YouTube column only reads **Published** when that row's own newest upload
  succeeded. A sibling channel's upload no longer paints a row green.
- A daily-quota failure (raised before the upload starts) is now written back as
  a failed attempt, so the row reads **Failed** with a retryable message instead
  of staying on an old state or reading Published. A live video is never
  downgraded by a later failed re-attempt.
- `Completed` rows (including published ones) report **Export = Completed,
  Merge = Completed** and **Progress = 100%**. Publishing no longer creates a
  separate `Done` stage: the Stage column stays **Completed**, and the YouTube
  column says **Published** in green.
- While an upload is in flight, the **row, footer, and ROW DETAIL inspector** all
  show the same live text (`Sending 73%`, then `Publishing`), instead of the
  inspector saying "Not started" until the server records the upload.

## Technical impact

- `platform_api/routers/progress.py`
  - `_finalize_youtube_group()` collapses each upload slot to its newest
    attempt; stale URLs are cleared on failure.
  - `youtube_upload_jobs` no longer populate the batch aggregate when a slot
    key exists; the batch fallback is limited to batches with **no** slot rows.
  - `_build_row()` takes `youtube_legacy_batches`; terminal stages report
    Export/Merge as `Completed`; a successful upload keeps stage/status
    `Completed`; a failed upload becomes stage `YouTube` / status `Failed`;
    `youtube_text` covers cancelled/refunded/error.
- `platform_api/repositories/youtube_connection_repo.py`
  - `record_upload_result()` never downgrades a published slot; it updates the
    existing row or inserts a failed one.
- `camxora_python/shared/workers/data_workers.py`
  - `YouTubeDirectUploadWorker._report_failure()` records failed-before-publish
    attempts (quota/cap, missing file, provider rejection) through
    `POST /youtube/uploads/report`.
- `camxora_python/shared/lib/progress_presentation.py`
  - `compute_stage_progress_percent()` returns `100%` for `Completed`.
- `camxora_python/features/progress/views/progress_view.py`
  - Active Runs excludes `Completed`; the inspector re-binds to the selected row
    on every poll/upload tick.
- `camxora_python/features/progress/widgets/progress_detail_card.py`
  - The YouTube step reads the live `publish_activity` registry, so it shows
    `Sending n%` / `Publishing` while the upload is in flight.
- `camxora_python/features/progress/widgets/operational_rows_card.py`
  - `Published` is green in the YouTube column.

## Files touched

| File | Change |
|---|---|
| `platform_api/routers/progress.py` | Per-slot YouTube aggregation; published rows stay `Completed`; terminal Export/Merge; failed-upload stage |
| `platform_api/repositories/youtube_connection_repo.py` | `record_upload_result` success guard |
| `platform_api/tests/test_progress_router.py` | Sibling-channel, legacy fallback, newest attempt, Completed-stage, terminal Export/Merge tests |
| `camxora_python/shared/workers/data_workers.py` | Report failed direct uploads |
| `camxora_python/shared/lib/progress_presentation.py` | `Completed` → 100% |
| `camxora_python/features/progress/views/progress_view.py` | Active Runs excludes Completed; inspector re-binds on poll/tick |
| `camxora_python/features/progress/widgets/progress_detail_card.py` | Live `Sending n%` / `Publishing` in the YouTube step |
| `camxora_python/features/progress/widgets/operational_rows_card.py` | `Published` is green |
| `camxora_python/tests/test_progress_presentation.py` | Completed-percent regression test |
| `camxora_python/tests/test_progress_view.py` | Live-percent inspector + Published-color tests |

## Tests

```bash
python -m pytest platform_api/tests/test_progress_router.py -q
# 19 passed

python -m pytest platform_api/tests/test_youtube_router.py \
  platform_api/tests/test_youtube_connection_service.py \
  platform_api/tests/test_publish_router.py -q
# 16 passed

cd camxora_python
python -m pytest tests/test_progress_presentation.py tests/test_upload_status_priority.py \
  tests/test_workflow_steps.py tests/test_video_runtime_inspection.py \
  tests/test_progress_local_overlay.py tests/test_progress_view.py -q
# 80 passed
```

## Deploy

No schema change and no migration. Deploy `platform_api` for the aggregation and
bookkeeping fixes; ship the next desktop installer for the failure reporting,
100% progress, and Active Runs count.

## Follow-ups

- `YouTubeConnectionService.quota_status()` counts jobs by `created_at`, but a
  re-upload updates the existing slot row instead of creating a new one. Retries
  of an older slot therefore do not always count toward the daily cap. Reconcile
  against `updated_at` (or a per-attempt row) in a separate change.
