# web-music: WAV generated on demand, not for every song

## Summary

`music.camxora.com` produced a WAV for **every** successful generation. Measured on
the live bucket: **100.75 GiB across 2,735 objects — 58.6% of the entire
`web-music/` prefix**, at ~37.7 MiB per track. WAV is an optional paid export that
most listeners never request.

It is now produced only when downloaded.

## Product impact

- No visible change for users who never download WAV.
- **Known trade-off (accepted 2026-10-28):** the first WAV download of a song now
  waits on a Suno conversion. Measured at **14.2 s** on production
  (`GET /api/v3/web-music/generations/{id}/download-wav → 200 in 14211ms`).
  The result is **not** written back to B2, so every subsequent download of that
  song pays the same cost again. Deliberately parked; see Follow-ups.
- Storage stops growing by ~33 MiB per generated track.

## Technical impact

Four separate paths generated WAV. The first fix caught two; a live download
proved the other two were still firing, so all four are now covered:

1. `routers/callbacks.py` — no longer schedules `schedule_web_music_wav_upload`
   after SUCCESS.
2. `services/streaming_upload_service.py` — `run_backfill_sweep` no longer
   converts missing WAVs (it re-created any missing WAV for tasks inside 48 h).
3. `services/streaming_upload_service.py` — `_upload_mp3_variant` no longer
   schedules a WAV upload after the MP3 upload. **This was the real traffic
   source**, because `schedule_web_music_b2_backfill` is deliberately kept in the
   callback path and fires for every generation.
4. `services/streaming_upload_service.py` — the asset recovery pass no longer
   converts WAVs (it was capped by `wav_budget`, and its `wav_recovered=0` log
   line was misleading because path 3 consumed the budget first).

`_backfill_web_music_wav` and `schedule_web_music_wav_upload` are kept for explicit
admin/tool use; nothing in a generation path reaches them.

## Verification (production)

| | pre-fix track `de3889bc` | post-fix track `65345316` |
|---|---|---|
| created | 11:25:43 | 11:34:38 (after deploy) |
| `b2_wav_storage_key_ok` | `…/ok.wav` | **null** |
| `b2_wav_uploaded_at_ok` | 11:27:41 | **never** |
| eager uploads | `ok.wav` 28,418,764 B + `alt.wav` 33,026,801 B | none |
| WAV download | 200 in 8,975 ms | 200 in **14,211 ms** |

The download still works with no stored object, which is the intended behaviour.

## Files touched

- `platform_api/routers/callbacks.py`
- `platform_api/services/streaming_upload_service.py`

## Migration/deploy

- No migration. `platform_api` restart via `sync_platform_api_production.py`.
- Deployed `ec36bea4` then `61ff371f` (the second fixes the two paths missed by
  the first).
- Close to PR #266 (`fix(platform_api): stop B2 sweep re-paging on terminal WAV
  failures + recover them`) — it recovers WAVs in the same sweep and would undo
  part of this. Closed as superseded. Its `wav_failed=2` alert also stops, since
  the sweep no longer looks for WAVs at all.

## Tests

- `py_compile` clean on both files.
- `pytest platform_api/tests -k "wav or web_music or backfill or callbacks or recovery"`
  → **172 passed**, 3,134 deselected.
- Live verification as tabled above.

## Follow-ups

- [ ] **WAV write-back cache.** The download path converts but does not persist.
      Caching the result after the first request would keep the zero-eager-storage
      win and make repeat downloads instant. Parked by decision 2026-10-28.
- [ ] **Playback: first click fails with "Playback is not available for this
      track."** Proven to be a packaging-readiness race, not encryption:
      track `65345316` logged `package=none` during the failing attempt and is
      `ready` afterwards. 28 of 1,685 web-music tracks are un-packaged at any
      time. `music_web/src/components/player-provider.tsx:902` treats a missing
      play URL as a permanent error instead of retrying. Suggested fix: retry the
      play-URL fetch 2–3 times over ~2 s before surfacing the error.
- [ ] Expire the existing `web-music/` WAV backlog (~100 GiB). Now safe: nothing
      re-creates them. Use the same paired `Expiration` +
      `ExpiredObjectDeleteMarker` rule shape as `musicapi/wav/`.
