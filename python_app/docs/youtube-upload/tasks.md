## YouTube Upload — Tasks

### Phase 0 (Decisions)
- [x] Choose dependency strategy:
  - [x] Official Google libs (recommended)
  - [ ] Manual OAuth + resumable upload (higher risk)
- [x] Decide default privacy: Unlisted (safe default).
- [x] Include scheduling support in Phase 1 (Scheduled publish time).
- [ ] Confirm whether uploads must be Public in production (requires Google app verification/audit).
- [x] Decide scheduling strategy: use batch date + per-profile time (no manual date per profile).
- [x] Decide category UX: dropdown with common YouTube categories + custom override.
- [x] Decide thumbnail strategy: attach per-batch thumbnail from batch run folder during upload.

### Phase 1 (DB + Profile Settings) (implemented)
- [x] Migration: add `youtube_accounts` and `youtube_upload_jobs` tables.
- [x] Add profile settings UI section for YouTube.
- [x] Add setting toggle `autoUploadYouTube` in Music page.
- [x] Add per-profile defaults (privacy/category/tags/title/description templates).

### Phase 2 (OAuth Connect) (implemented)
- [x] Implement Connect flow (browser + loopback redirect).
- [x] Store refresh token securely (encrypted DB).
- [x] Implement Disconnect (remove tokens, clear link).

### Phase 3 (Upload Worker) (implemented)
- [x] Implement upload service with resumable uploads and chunking.
- [x] Implement upload job queue runner (threaded, cancellable).
- [x] Implement retry policy (exponential backoff + max attempts).
- [x] Store `youtubeVideoId` + URL on success.

### Phase 4 (End-to-End Integration) (implemented)
- [x] When Auto-Video merge finishes, enqueue YouTube upload job for that channel folder.
- [x] Add periodic scan to catch missed merges.
- [x] Prevent duplicates per (batchId, profileId, role).

### Phase 5 (UI + QA) (implemented)
- [x] Add “YouTube” page with queue table and retry/cancel actions.
- [x] Add detailed status messages to footer.

### Phase 6 (Multi-Channel + AI Use)
- [x] Add multi-channel selection during Connect when `channels.list(mine=true)` returns multiple channels.
- [x] Store selected channel id/title for the profile connection (no token changes beyond existing secure storage).
- [x] Add per-profile “AI use” field and apply it to uploads via `status.containsSyntheticMedia`.
- [ ] Regression tests:
  - [ ] connect to a Google account with multiple channels and bind the correct channel to the selected Profile
  - [ ] upload sets `containsSyntheticMedia` correctly (true/false) and does not break existing metadata fields

### Phase 7 (UX + Metadata Upgrades)
- [x] Replace Category id text input with dropdown and custom override:
  - [x] show common categories (Music=10) and persist numeric id
  - [x] allow custom numeric entry when needed
- [x] Scheduled publish improvements:
  - [x] Profile stores only publish time (HH:MM)
  - [x] Upload time uses batch date parsed from batchId + profile time
  - [x] Warn if multiple batches share the same batchDate for the same profile (action: change time)
- [x] Thumbnail upload:
  - [x] Resolve thumbnail path per job from batch run dir (prefer per-batch thumbnail_*; fallback thumbnail.png; fallback newest in thumbnails/)
  - [x] Upload thumbnail after `videos.insert` via `thumbnails.set`
- [x] Playlist selection:
  - [x] Fetch playlists for connected profile and show a dropdown
  - [x] Persist `youtubePlaylistId` per profile
- [x] Playlist auto-add:
  - [x] After a successful upload, add the uploaded video to `youtubePlaylistId` via `playlistItems.insert`
  - [x] If account scopes are missing playlist write permissions, show an actionable message to reconnect

### Documentation
- [x] Update DEVELOPMENT_LOG.md with multi-channel selection + AI use field behavior and any migration notes.
