# Suno polls remember the owning key

**Date:** 2026-11-09
**Surface:** `platform_api`
**Branch:** `fix/suno-owner-key-pinning`

## Summary

Suno's record-info endpoint is account-scoped: only the key that created a task
can read it, and every other key answers `401/403`. Polls therefore iterated the
whole pool — with 3 active keys that is 3 provider calls per poll, two of them
guaranteed to fail, on every 5s poll a pending song receives.

## Product impact

- A pending song's poll now usually makes **one** provider request instead of
  three, and stops touching unrelated accounts (their rate limits stay clear).
- If the recorded key was rotated or disabled, the poll falls back to a scan once
  and re-records the new owner; nothing breaks.
- Pinning is best-effort: a lookup or update failure (including a pre-migration
  database) silently falls back to the old scan.

## Technical impact

- Migration `185_suno_task_owner_key`: nullable `suno_tasks.suno_key_id` (UUID)
  plus a partial index on non-null values.
- `platform_api/services/suno_audio_resolver.py`
  - `active_suno_key_entries()` returns `(api_key_entries.id, decrypted key)`;
    `active_suno_key_values()` remains as a values-only wrapper for existing
    callers.
  - `_pinned_suno_key_id()` / `_remember_suno_key_owner()` read and persist the
    owner for an `external_task_id`.
  - `poll_suno_generate_with_pool()` tries the pinned key first (stable sort),
    scans on failure, and records the winner.
- Tests: new `test_suno_owner_key_pinning.py` (5) and an updated resolver test.

## Files touched

| File | Change |
|---|---|
| `platform_api/migrations/versions/185_suno_task_owner_key.py` | New column + partial index |
| `platform_api/services/suno_audio_resolver.py` | Pin-first polling + persist |
| `platform_api/tests/test_suno_owner_key_pinning.py` | New tests |
| `platform_api/tests/test_suno_audio_resolver.py` | Patch target updated |
| `platform_api/CHANGELOG.md` | Entry |

## Migration/deploy

Additive, idempotent migration (`ADD COLUMN IF NOT EXISTS`). Runs at API
startup like the others; no backfill needed — the first successful poll for an
existing task records its owner.

## Tests

```bash
python -m pytest platform_api/tests/test_suno_owner_key_pinning.py \
  platform_api/tests/test_suno_audio_resolver.py -q      # 56 passed
```

## Follow-ups

- Extend pinning to `call_with_owning_suno_key()` (WAV conversion, timestamped
  lyrics, recovery) once its callers pass the external task id.
- `_iter_generate_clips` is imported but unused in the resolver (pre-existing).
