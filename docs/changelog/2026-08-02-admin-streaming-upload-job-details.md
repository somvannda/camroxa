# Admin streaming upload jobs — show user/album/batch detail

**Date:** 2026-08-02  
**Status:** implemented  
**Branch:** `fix/admin-streaming-upload-job-details`

## Problem

Admin **Streaming Upload Jobs** (`/streaming/upload-jobs`) rendered User / Email / Album / Publish / Batch / Song / Updated as `—` even for successful jobs.

The UI already expected enriched fields, but `GET /api/v1/admin/streaming/upload-jobs` only returned `id`, `kind`, `status`, `source_url`, `storage_key`, `error`, `created_at`. The underlying `stream_upload_jobs` rows already store `user_id` / `batch_id` / `song_id` (covers omit `song_id` by design; older covers often left `album_id` null).

## Fix

- Expand `UploadJobResponse` + list query with joins to `users`, `songs`, `stream_albums`, `stream_tracks`
- For cover jobs missing `album_id`, fall back to album matched by `batch_id` + `cover_storage_key`
- Persist `album_id` on successful cover/mp3 uploads going forward
- Sync admin page + TypeScript types with the enriched payload

## Surfaces

| Surface | Change |
|---------|--------|
| platform_api | enriched upload-jobs list + album_id on mark success |
| admin_portal | Streaming Upload Jobs cards show joined metadata |
