# musicapi: real Suno reference-video upload (`user_uploaded_video_id`)

**Date:** 2026-10-29
**Branch:** `feat/musicapi-video-reference`
**Surface:** `musicapi` (Suno wrapper)

## Summary

The create composer's `+ → Video` attach used to reach Suno as a **single still
frame**: `processMusicSubmitWithVideo` extracted one frame at `t=1s`, uploaded it
as an image, and generated from that. Suno's own web app instead uploads the clip
as a visual asset and sends `user_uploaded_video_id`.

`SunoClient` now performs the same upload, so a reference clip reaches the model
as a clip.

## Product impact

- A video reference now influences the song as a video, not as one screenshot.
- A clip and an image can be attached together: images go as
  `user_uploaded_image_ids`, the clip as `user_uploaded_video_id`.
- No API or UI change: `platform_api` and `camxora.com` already upload the file
  and pass `video_urls` / `background_video_url`.
- Generation may take longer when a clip is attached: Suno processes video
  asynchronously before the song can start (observed ~7s for a 19 KB clip;
  budget up to 6 minutes).

## Technical impact

Flow, taken from Suno's own composer bundle and implemented verbatim:

```
POST /api/uploads/video/            { extension }            -> { id, url, fields }
POST <url> (S3 policy form + bytes)
POST /api/uploads/video/{id}/upload-finish/
     { upload_type: "studio_file_upload",
       upload_filename: "<name>",
       fail_task_on_moderation: false }
GET  /api/uploads/video/{id}/       poll every 3s, up to 6 min
     { status: uploading|processing|complete|error, error_type?, s3_id?, video_url? }
```

Then `generate/v2` receives `user_uploaded_video_id: <upload id>`.

- `musicapi/src/client.ts`
  - `createVideoUpload()` / `uploadVideo()` (create → S3 → finish → poll)
  - `GenerateParams.videoIds` → `user_uploaded_video_id` (max 1)
- `musicapi/src/server.ts`
  - `uploadReferenceVideo()` replaces `uploadReferenceVideoFrames()`
  - `processMusicSubmitWithReferences()` passes `videoIds` alongside
    `imageIds` / `audioIds` instead of flattening frames into images
- `musicapi/src/video.ts`: `extractVideoFrames()` left in place, unused by the
  submit path (still available for other tooling).

## Files touched

| File | Change |
|---|---|
| `musicapi/src/client.ts` | Video upload methods + `user_uploaded_video_id` |
| `musicapi/src/server.ts` | Clip upload replaces frame extraction |
| `musicapi/docs/api-parity-checklist.md` | Reference media row updated |
| `docs/changelog/2026-10-28-web-create-video-attach.md` | Follow-up marked resolved |

## Migration/deploy

- No schema change, no new env var.
- Restart `musicapi` to pick it up. `platform_api` needs no change.
- Rollback: revert `server.ts` (frames path returns) — no data repair.

## Tests

- `npm run test:unit` (musicapi) → **132 passed**
- `npx tsc --noEmit -p tsconfig.json` → clean
- **Live upload probe** against Suno with a pool account (`iamduke1987@gmail.com`):
  19,407-byte MP4 → upload id returned in **7s** (create → S3 → finish → poll
  `complete`).
- Generation with the clip is **not yet proven end-to-end**: the pool account had
  0 Suno credits at the time (renews ~2026-11-04). Retest then.

## Follow-ups

- Add a unit test that stubs `request()` and asserts `videoIds[0]` becomes
  `user_uploaded_video_id`.
- Surface the "processing" wait in job telemetry so a slow clip does not look
  like a stuck job.
- Clip moderation (`error_type`) currently fails the job and refunds through the
  existing path; consider a friendlier message.
