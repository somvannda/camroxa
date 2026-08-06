# Lock batch Album 1 / Album 2 (and run dirs) under parallel draft workers

**Date:** 2026-08-03  
**Status:** implemented (sandbox deploy pending)

## Summary

Parallel stage draft workers could each invent a different album and stamp a
different `{channel}/{date}_{album}` path onto their Suno download tasks. Desktop
then mkdir'd every distinct path — often **3+ folders** for one Generate — while
Music History only showed the final batch Album 1 / Album 2.

## Product impact

- Workers may still draft **lyrics + titles** in parallel.
- **Album 1 (`ok_album`) and Album 2 (`alt_album`) lock once** (first successful
  claim wins). Later songs reuse those names.
- Run folders lock once to those albums. Suno downloads prefer the locked batch
  dirs over any stale per-task race paths.

## Technical impact

- `claim_batch_channel_albums` / `claim_batch_run_directories` use SQL
  `COALESCE` so the first writer wins.
- `retry_song_draft` forces `batch.ok_album` onto the song after claim.
- `_submit_song_to_suno` and pending-download listing re-read / prefer batch
  `ok_run_dir` / `alt_run_dir`.

## Files touched

- `platform_api/repositories/batch_repo.py`
- `platform_api/services/batch_service.py`
- `platform_api/tests/test_batch_service.py`
- `platform_api/CHANGELOG.md`
- `docs/changelog/2026-08-03-lock-batch-album-run-dirs.md`

## Migration / deploy

- No DB migration.
- Deploy `platform_api` to **sandbox** after merge; production only on request.

## Tests

- `pytest platform_api/tests/test_batch_service.py -k "album or assign_batch_run or retry_song_draft_forces"`
