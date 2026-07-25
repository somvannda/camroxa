# Album image jobs: one BG + one TH per channel (fix 2/2 race)

**Date:** 2026-07-25  
**Status:** implemented (sandbox pending deploy)  
**Incident:** Progress showed `BG 2/2 · TH 2/2` on Neon Coastal Midnight / Beattok after concurrent Suno successes.

## Summary

Album image generation is designed as **one background and one thumbnail per Primary/Secondary channel**, not per song. When two Suno tracks in the same batch completed within ~300ms, both callbacks created a full image-job set before either saw the other’s inserts. Progress correctly counted the duplicates as `2/2`.

## Product impact

**Before**
- Error/recovery rows could show `BG 2/2 · TH 2/2` (and burn ~2× image provider cost).
- Healthy runs usually still showed `1/1` when only one song completed first.

**After**
- DB enforces one job per `(batch_id, profile_id, kind, channel_role)`.
- Racing creates are ignored (`ON CONFLICT DO NOTHING`).
- Migration removes existing duplicates (keeps earliest job). Progress returns to `BG 1/1 · TH 1/1`.

## Technical impact

- Migration `070_unique_album_image_jobs`: dedupe + partial unique index.
- `BatchRepo.create_image_job(s)` conflict-safe; returns only inserted rows.
- `BatchService.create_image_jobs_for_batch` returns actual created list; album key normalized (kind lower / role upper).

## Files touched

- `platform_api/migrations/versions/070_unique_album_image_jobs.py`
- `platform_api/repositories/batch_repo.py`
- `platform_api/services/batch_service.py`
- `platform_api/tests/test_batch_service.py`
- `platform_api/CHANGELOG.md`
- `docs/changelog/2026-07-25-album-image-job-dedupe-race.md`

## Migration / deploy

1. Deploy `platform_api` + run alembic to `070_unique_album_image_jobs`.
2. Restart API.
3. Refresh Progress — Neon Coastal should show `BG 1/1 · TH 1/1` per channel.

## Tests

- `test_create_image_jobs_for_batch_is_once_per_channel_not_per_song`
- `test_create_image_jobs_for_batch_race_second_insert_is_noop`

## Follow-ups

- Optional: refund/inspect image charges for batches that already double-ran (Neon Coastal `96d099e1-…` had 8 success jobs / expected 4).
- Consider advisory lock if we ever create album jobs outside this insert path.
