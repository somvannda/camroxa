# Create "+" → Video: match Suno's reference-clip attach

**Date:** 2026-10-28
**Branch:** `feat/web-create-video-attach`
**Surface:** `camxora.com` Create page + Platform API

## Summary

Suno's create composer `+ → Video` does **not** open a video renderer. It opens
the OS file picker for one reference clip (`video/mp4`, `video/quicktime`,
`video/webm`), uploads it, and shows a removable attachment chip. The clip then
travels with the generation request as `user_uploaded_video_id`.

Camxora's `+ → Video` opened a 520px "Add video" modal with a song picker,
version chips, aspect-ratio chips, and a `Create video` button — a different
feature. This change replaces it with the Suno flow and keeps the MP4 renderer
reachable from the song rail.

Verified against the live Suno create UI (authenticated with a pool account
cookie) by reading the composer's React handlers:

- `onPickVideo` creates `<input type="file" accept="video/mp4,video/quicktime,video/webm">`.
- State machine: `uploading → processing → ready` with a `previewUrl`, plus
  `clearVideo`.
- One clip max: a second pick raises `magicBar.attachmentCapVideo`.
- Payload key: `videoUploadId` → `user_uploaded_video_id`.

## Product impact

- `+ → Video` opens the file picker immediately; no intermediate modal.
- The attached clip renders as a chip under the attach buttons (32px video
  thumbnail, filename, size, remove `×`), next to the existing image chip.
- Picking a second clip is refused: "Remove the attached clip first — one video
  at a time."
- Non-MP4/MOV/WebM files are rejected in the browser before upload.
- The MP4 renderer is unchanged but now opens from the song rail's `Video`
  action instead of the `+` menu.

## Technical impact

Frontend (`camxora.com`):

- `lib/web-music-api.ts`: `video_urls` on `WebMusicGenerateInput`;
  `WebMusicStudioVideoFile` + `uploadWebMusicStudioVideoFile()` posting to
  `POST /api/v3/web-music/studio/video-uploads`.
- `components/CreateStudio.tsx`: `referenceVideo` / `videoUploading` /
  `videoUploadError` state, hidden `videoInputRef` input, `pickReferenceVideo()`,
  `uploadReferenceVideoFile()`, chip UI, and `video_urls` on the generate payload.
- `components/TrackRail.tsx`: new `onCreateVideo` prop + `Video` action.
- `app/globals.css`: `.s-video-chip*` using `--s-*` tokens.

Backend (`platform_api`):

- Migration `168_reference_videos.py`: `suno_tasks.reference_video_urls JSONB
  NOT NULL DEFAULT '[]'`.
- `ports/generation_port.py`: `SunoRequest.video_urls`.
- `clients/suno_client.py`: `video_urls` param → `payload["videoUrls"][:1]`.
- `services/generation_service.py`: threaded through `_call_suno` and
  `submit_suno_external_id`.
- `services/web_music_service.py`: http(s)-only validation and a 1-item cap in
  `generate()`, persisted in `_enqueue_web_generate`, read back in
  `fulfill_queued_generate`, plus `create_studio_video_file()`.
- `routers/web_music.py`: `video_urls` (max 1) on the generate body and
  `POST /studio/video-uploads` (201, ≤100 MB).

`musicapi` already accepted `videoUrls` (`uploadReferenceVideo`); no change there.

## Files touched

| File | Change |
|---|---|
| `platform_api/migrations/versions/168_reference_videos.py` | New column |
| `platform_api/ports/generation_port.py` | `SunoRequest.video_urls` |
| `platform_api/clients/suno_client.py` | `video_urls` → `videoUrls` |
| `platform_api/services/generation_service.py` | Passthrough |
| `platform_api/services/web_music_service.py` | Validate, persist, fulfill, upload |
| `platform_api/routers/web_music.py` | Request field + upload route |
| `platform_api/tests/test_web_music_reference_video.py` | New coverage |
| `platform_api/tests/test_web_music_generate_queue.py` | Fixture gains reference columns |
| `camxora.com/lib/web-music-api.ts` | Type + upload helper |
| `camxora.com/components/CreateStudio.tsx` | Attach flow + chip |
| `camxora.com/components/TrackRail.tsx` | Renderer entry |
| `camxora.com/app/globals.css` | `.s-video-chip` |
| `camxora.com/DESIGN_SYSTEM.md`, `camxora.com/API_PARITY.md` | Docs |

## Migration/deploy

- Run Alembic through `168_reference_videos` before the API serves the new
  upload route. Additive column with a default, so it is safe to apply first.
- Rollback: revert the code, then drop `reference_video_urls`.
- No pricing change: the clip is an input to the normal charge, not a new SKU.

## Tests

- `python -m pytest platform_api/tests/test_web_music_reference_video.py
  platform_api/tests/test_web_music_generate_queue.py -q` → **11 passed**
- `python -m py_compile` on every touched Python file → OK
- `npx tsc --noEmit` (camxora.com) → clean
- `npm run check:ui` → compliant
- `platform_api/tests/test_web_music_router.py::test_stream_proxies_without_exposing_origin`
  still fails on `KeyError: 'request_headers'`; unrelated to this change
  (playback proxy kwargs), pre-existing.

## Update — renderer polish (same day)

The kept MP4 renderer gained the controls you asked about, and two of them were
wrong before this pass:

- **Aspect 1:1 was broken.** `renderMusicVideo` only special-cased `9:16`, so
  `1:1` silently produced 1280×720. It now renders 720×720. Verified with
  ffprobe: `16:9 → 1280×720`, `9:16 → 720×1280`, `1:1 → 720×720`.
- **Version** already worked (`variant` → `ok`/`alt` provider clip id); it only
  appears when both clips are ready.
- **Browse** was added: attach an MP4/MOV/WebM from the user's PC and it becomes
  the video background instead of the cover art.
  `renderMusicVideo` loops it (`-stream_loop -1`), crops to fill the chosen
  aspect, and keeps the waveform overlay. Verified: a 1s clip under a 3s song
  yields a 3.000s MP4.
- New plumbing: `background_video_url` on `StudioVideoRequest` →
  `/internal/studio/video` → musicapi fetches (≤100 MB) → `renderMusicVideo`.
  The clip is stored by the existing `POST /studio/video-uploads` route.

## Follow-ups

- **musicapi forwarded a frame, not the clip (resolved 2026-10-29).**
  `processMusicSubmitWithVideo` used to extract a frame at `t=1s` because the
  client had no video upload. `SunoClient.uploadVideo()` now performs Suno's
  own `/api/uploads/video/` 3-step upload and sends `user_uploaded_video_id`,
  so the model receives the real reference clip. See
  `2026-10-29-musicapi-reference-video.md`.
- **Image + video precedence.** `musicSubmitFactory` tries inline images, then
  reference images, then videos — so attaching both silently drops the video.
  Suno sends `user_uploaded_image_ids` and `user_uploaded_video_id` together.
- **Reference URL expiry.** The stored URL is a CDN URL or a signed B2 URL with
  `stream_url_ttl_seconds` (default 3600). A long queue backlog could expire it
  before musicapi fetches the clip.
- Live QA needs Suno credits: all pool accounts are out
  (`iamduke1987@gmail.com` = 0, renews ~2026-11-04). Retest attach + generate
  then.
- `DESIGN_SYSTEM.md` rows for `Image` and `Playlist` are also stale ("not
  enabled yet") and should be corrected separately.
- No duration validation yet; Suno warns when the clip exceeds its limit.
  Consider mirroring that once we know the platform's cap.
