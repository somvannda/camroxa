# Thumbnail orphan source_job_id after album image race

**Date:** 2026-07-27  
**Status:** implemented (sandbox + production file-scoped hotfix)  
**Incident:** Sandbox ALT thumbnail `354f25f9-…` failed with `Thumbnail image job source background job was not found.` while ALT background `4572a037-…` succeeded.

## Summary

When two Suno completions race to create album image jobs, the losing background insert is skipped (`ON CONFLICT DO NOTHING`), but the paired thumbnail could still insert with the discarded background UUID. Thumbnails now remap `source_job_id` onto the existing album-slot background before insert.

## Product impact

- Before: Secondary/ALT thumbnail could fail permanently (3 attempts) even when background succeeded.
- After: raced thumbnails attach to the winning background job; Progress should show TH success for that channel on new races.

## Technical impact

- `BatchRepo.create_image_jobs` remaps thumbnail `source_job_id` when background insert conflicts.
- `BatchRepo.get_image_job_for_album_slot` helper for `(batch_id, profile_id, kind, channel_role)`.

## Files touched

- `platform_api/repositories/batch_repo.py`
- `platform_api/tests/test_image_job_source_remap.py`
- `platform_api/CHANGELOG.md`
- `docs/changelog/2026-07-27-thumbnail-orphan-source-job.md`
- `scripts/deploy/hotfix_thumbnail_orphan_source_job_sandbox.py`
- `scripts/deploy/hotfix_thumbnail_orphan_source_job_production.py`

## Migration / deploy

File-scoped only (no full `platform_api` tree sync — DistroKid and other WIP stay out):

```bash
python scripts/deploy/hotfix_thumbnail_orphan_source_job_sandbox.py
python scripts/deploy/hotfix_thumbnail_orphan_source_job_production.py
```

Optional: reset/requeue the known orphan thumbnail after deploy.

## Tests

- `pytest platform_api/tests/test_image_job_source_remap.py`

## Follow-ups

- Re-run failed orphan thumbnail job(s) after deploy if users still need that ALT art.
