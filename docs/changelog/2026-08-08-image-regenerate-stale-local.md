# Image regenerate no longer keeps the previous local PNG

## Summary

Right-click **Regenerate Background / Thumbnail** on the Image page was calling production successfully and generating a new image, but the desktop kept showing the old file because the server reuses the same relative output path and the client skipped download when that path already existed locally.

## Product impact

- Regenerated backgrounds/thumbnails replace the previous local PNG and preview.
- Output sync / Open File also refresh when the job `updated_at` is newer than the local file.

## Evidence (production)

- `POST /api/v1/image-jobs/retry` returned 200 and workers logged new SLAI generations (different byte sizes) for the same job id.
- No follow-up `GET /api/v1/image-jobs/{id}/output` after those regenerations — the client never re-pulled bytes.

## Files touched

- `camxora_python/shared/lib/image_output_utils.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/features/image/views/image_view.py`
- `camxora_python/tests/test_image_output_and_pipeline_auth.py`
