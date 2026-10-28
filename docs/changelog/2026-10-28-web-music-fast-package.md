# web-music: playable before lane B and HLS finish

## Summary

First play of a freshly generated track failed with **"Playback is not available
for this track."** and worked on the second click, or after a refresh.

Root cause: `content_license_service` returns an empty `play_url` until
`package_status = 'ready'`, and `package_plaintext` only wrote that after doing
*everything* — `.cxo`, `.cxa`, `.b.cxa`, then ~35 HLS segment uploads one at a
time. On a live track, generation was at 11:34:38 and packaging was still
`package=none` at 11:36:39, becoming `ready` minutes later.

## Product impact

- New tracks become playable within seconds of their MP3 arriving, instead of
  minutes.
- No change to encryption or to what a listener can download: playback still
  requires the packaged `.cxa` plus its content key.
- Existing already-packaged tracks are untouched (they were never in this window).
- **Not fixed by this change:** the 28 tracks already stuck in `package_status =
  'none'`. The asset recovery pass covers them; a play-triggered kick would be
  better and is listed as a follow-up.

## Technical impact

- `audio_package_service.py`
  - New `_mark_playable()` writes the three columns the playback gate actually
    reads — `package_status='ready'`, `packaged_storage_key`, `content_key_id`
    (plus `encrypted_original_key` and the existing `audio_url_*` nulling) —
    immediately after lane A is uploaded.
  - `_package_plaintext_body()` then continues with lane B and HLS exactly as
    before. The pre-existing UPDATEs at the end re-assert the same values, so the
    **final persisted state is unchanged**; only the moment of playability moves.
  - Scoped to `suno_task` subjects. `stream_track` keeps its previous ordering.

## Why not stream from Suno instead

Suno's own CDN URL would remove the wait, but `audio_package_service.py:204`
deliberately nulls it at packaging (`null_suno_urls=True`), and a Suno URL is a
plaintext, unauthenticated link — streaming from it would let any listener
download the raw MP3, defeating the protection this pipeline exists for. It is
also gone for the 1,657 already-packaged tracks. Preview tracks (which have an
`is_preview` path) are the only place it belongs, and that is not part of this
change.

## Files touched

- `platform_api/services/audio_package_service.py`

## Migration/deploy

- No migration. `platform_api` restart via `sync_platform_api_production.py`.

## Tests

- `py_compile` clean.
- `pytest -k "package or wav or web_music or license"` → **234 passed**,
  3,072 deselected.

## Verify after deploy

1. Generate a song and click play immediately — it should play on the first
   click, with no second attempt.
2. Confirm the same track later has `packaged_storage_key_ok_b` set and
   `hls_status_ok = 'ready'`, proving the second phase still completes.
3. Confirm an already-packaged track still plays immediately and does not get
   re-packaged.

## Follow-ups

- [ ] Play-triggered packaging for tracks stuck at `package_status='none'` (28 at
      time of writing), deduped per `(task_id, variant)`.
- [ ] `playback_state: preparing|ready|unavailable` in the license payload, so the
      player can show "Preparing…" instead of a false "unavailable".
- [ ] Client: poll the play URL for ~60 s when `preparing`, then fall back.
- [ ] Preview tracks stream a cheap path instead of the packaged one.
- [ ] Streaming from Suno for previews only — safe there, unsafe for paid tracks.
- [ ] `_encrypt_ingested_mp3` is defined twice, identically
      (`streaming_upload_service.py:364` and `:396`). Clean up.
