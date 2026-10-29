# streaming: "web music missing assets" stops counting on-demand WAVs

## Summary

The hourly Telegram streaming-capture report paged **"web music missing assets:
122"** on production 2026-10-29 14:47 (+07), while `web music missing mp3` was
`0`. The 122 were not capture failures: the counter still treated a missing
`b2_wav_storage_key_*` as a missing asset, but since 2026-10-28 web-music WAVs
are built on first download and are **never written back to B2**
(`docs/changelog/2026-10-28-web-music-lazy-wav.md`). Every new track was
therefore flagged for its whole 24 h window.

## Root cause

`_WEB_MUSIC_MISSING_ASSETS_PREDICATE` (`platform_api/repositories/streaming_repo.py`)
flagged a task when any of WAV / package / LRC was absent for a captured MP3.

The WAV clause was written when WAV was eager (`wav_task_id_*` empty → missing).
After the lazy-WAV change it was wrong in both directions:

1. **Never downloaded** → no `b2_wav_storage_key_*`, no `wav_task_id_*` → counted
   as missing, for every generated track.
2. **Just downloaded** → the on-demand path only writes `wav_status_* = 'success'`
   (`web_music_service.download_wav`) and never a B2 key, and the clause was
   `(wav_task_id_* = '' OR wav_status_* = 'success')` → still counted.

So the number tracked generation volume (~6 tracks/h × 2 variants) plus WAV
download activity, and could never reach zero.

## Product / ops impact

- The alert now means what it says: an actionable gap. MP3, package and LRC
  coverage are still reported; only the guaranteed-empty WAV column is dropped.
- Fixes a side effect in the asset recovery pass: it no longer recovers WAV
  (deliberate, 2026-10-28), but it still *selected* WAV-only tasks and spent its
  `WEB_MUSIC_ASSET_PASS_TASK_LIMIT` (8/pass) budget on gaps nothing would fix,
  starving the LRC/package work that can succeed.
- The package term still covers the playback-breaking `package_status <> 'ready'`
  backlog (28 tracks at time of writing, `2026-10-28-web-music-fast-package.md`).

## Technical impact

- `_WEB_MUSIC_MISSING_ASSETS_PREDICATE` keeps only:
  - `package_status_{ok,alt} <> 'ready'` while an MP3 exists,
  - `b2_lrc_storage_key_{ok,alt}` empty while an MP3 exists and not instrumental.
- Both consumers pick the change up automatically: `count_web_music_missing_assets`
  (health report) and `list_web_music_asset_tasks` (recovery pass).
- No schema change, no data migration, nothing to backfill.

## Known residuals (deliberately not changed)

- Songs where Suno never produced timestamped lyrics can never get an LRC and
  count for the 24 h window (`lrc_noop` in the recovery pass). Small and
  non-actionable; a future `lrc_unavailable_*` marker would silence it.
- A task generated seconds ago is legitimately `package_status = 'none'`. An
  hourly snapshot can catch a handful of in-flight packagings.
- Existing `b2_wav_storage_key_*` backlog (~100 GiB) is untouched; nothing
  re-creates it.

## Files touched

- `platform_api/repositories/streaming_repo.py`
- `platform_api/tests/test_streaming_upload_dedup.py`

## Verification

- `pytest platform_api/tests/test_streaming_upload_dedup.py platform_api/tests/test_streaming_health_report.py`
  → **18 passed**.
- `pytest platform_api/tests -k "wav or web_music or streaming or recovery or backfill"`
  → **232 passed**, 3,084 deselected.

## Deploy

- No migration. `platform_api` restart via `sync_platform_api_production.py`.
- Expect the next hourly report to drop from ~122 to 0–few. A non-zero residual
  is worth reading: it now means a real package or LRC gap.
