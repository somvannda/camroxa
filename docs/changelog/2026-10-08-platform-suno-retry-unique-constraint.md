# Retrying a failed Suno song no longer charge-refunds forever

## Summary

A desktop/batch retry of a song whose previous Suno task **failed** could never
succeed. `suno_tasks` is `UNIQUE(user_id, request_hash)`, and the issue #372 fix
(`find_by_hash` skips `failed` rows so a retry regenerates) left the write path
as a plain `INSERT`, which collided with the still-present failed row:

```
duplicate key value violates unique constraint "suno_tasks_user_id_request_hash_key"
DETAIL: Key (user_id, request_hash)=(…, …) already exists.
```

`batch_service._submit_song_to_suno` caught that as a generic failure and called
`_refund_suno_billing(reason="suno_generation_failed")`, so every retry produced
a `v3_music` charge immediately followed by a `suno_generation_failed` refund —
the user saw a "keep failing" loop with no regeneration. Seen in production on
Oct 08 for user `ad6eda59…` / song `89bfcb7c…`.

## Product impact

- A failed song can be retried again: the retry revives the task row and submits
  to Suno instead of bouncing off the unique constraint.
- No more spurious `v3_music` charge → `suno_generation_failed` refund pairs for
  retries of previously-failed songs.
- No change for a first attempt or for a retry whose prior task is still live.

## Technical impact

- `platform_api/repositories/batch_repo.py` — `create_suno_task` (and its
  `create` alias) is now an upsert:

  ```sql
  INSERT INTO suno_tasks (…)
  VALUES (…)
  ON CONFLICT (user_id, request_hash) DO UPDATE SET
      external_task_id = EXCLUDED.external_task_id,
      model = EXCLUDED.model,
      title = EXCLUDED.title,
      lyrics = EXCLUDED.lyrics,
      style = EXCLUDED.style,
      instrumental = EXCLUDED.instrumental,
      status = EXCLUDED.status,
      source = EXCLUDED.source,
      error_message = NULL,
      audio_url_ok = NULL,
      audio_url_alt = NULL,
      downloaded_ok = false,
      downloaded_alt = false,
      updated_at = NOW()
  WHERE suno_tasks.status = 'failed'
  RETURNING id
  ```

  - The `WHERE suno_tasks.status = 'failed'` guard means only a **failed** row is
    revived; a live/successful row is never clobbered. If the guard matches
    nothing, the existing id is looked up and returned.
  - The persisted (existing) id is written back onto `task.id`, so
    `GenerationService.submit_suno` returns the real row id and the subsequent
    `link_suno_task` re-links `song_id`/`batch_id`. `song_id`/`batch_id` are
    deliberately **not** overwritten by the upsert.

## Files touched

- `platform_api/repositories/batch_repo.py`
- `platform_api/tests/test_batch_repo_suno_task_upsert.py` (new)
- `platform_api/tests/test_generation_service.py` (fake repo + #372 test mirror
  the upsert)
- `platform_api/CHANGELOG.md`
- `docs/changelog/2026-10-08-platform-suno-retry-unique-constraint.md` (this file)

## Migration / deploy

- No migration — the unique constraint is unchanged; the write now satisfies it.
- Requires a redeploy of **`platform_api`** only, then a restart of `camxora-api`
  and the `camxora-worker-suno@*` workers.

## Tests

- `platform_api/tests/test_batch_repo_suno_task_upsert.py`: 3 passed (revive a
  failed row and reuse its id; fresh insert keeps its id; a live conflict is not
  clobbered).
- `test_generation_service.py` (`test_failed_task_is_not_treated_as_duplicate`
  updated to assert in-place revival): passed.
- Batch/generation/callback/resolver/usage subset: **266 passed**.

## Follow-ups

- Songs already stuck on this error need no data migration: the next retry now
  revives the failed row. Re-trigger the affected songs' retries (or let the
  desktop retry) after deploy.
- Consider moving the Suno submit **after** the local task row is persisted, so a
  submit that fails locally can no longer orphan an upstream generation (the
  submit currently happens before the row write).
