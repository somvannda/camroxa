# Delete failed batch + draft meter leak fix

**Date:** 2026-07-25  
**Status:** implemented (sandbox deployed)

## Summary

Users can delete failed music batches that never produced successful or in-progress Suno audio (wrong song description, all `draft_failed`, etc.) via `DELETE /batches/{batch_id}` and History → **Delete failed batch**. Draft-failure refunds now release every billed draft slot (lyric/title/album), fixing an under-refund that leaked draft meter. Delete restores leftover draft units for `draft_failed` songs; wallet and song quota are not re-gifted.

## Product impact

**Before**
- Failed batches stayed in History forever; only retry was available.
- Draft fails often released only 1 draft-meter slot after billing 2–3 slots, shrinking remaining drafts incorrectly.

**After**
- History right-click **Delete failed batch** removes eligible batches after confirm.
- Draft fails refund the full billed slot count; delete also restores leftover draft units for `draft_failed` songs so users can recreate with the correct description.

## Technical impact

- `DELETE /batches/{batch_id}` — eligibility: every song in `{pending, draft_failed, draft_ready, suno_failed}`; hard-delete cascade for songs/suno/image/youtube rows; stream FKs nulled.
- `deduct_split_draft_billing` returns `billed_slots`; batch + `/generation/draft` refund with that count.
- Desktop: History menu + `DeleteFailedBatchWorker` + confirm dialog.

## Files touched

- `platform_api/services/batch_service.py`, `draft_billing.py`
- `platform_api/repositories/batch_repo.py`
- `platform_api/routers/batch.py`, `generation.py`
- `platform_api/models/schemas.py`
- `platform_api/tests/test_delete_failed_batch.py`, `test_draft_split_deduct.py`
- `camxora_python/features/music/widgets/history_card.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/shared/services/platform_api.py`, `models/platform.py`
- `camxora_python/shared/workers/data_workers.py`

## Migration / deploy

- No DB migration.
- Deploy `platform_api` to sandbox and restart API.
- Desktop: restart local app to pick up History menu (no installer required for local dev).

## Tests

- `pytest platform_api/tests/test_delete_failed_batch.py platform_api/tests/test_draft_split_deduct.py` — 9 passed.

## Follow-ups

- Refine delete draft restore so post-fix full refunds do not over-release (today floors at 0; slight remaining-quota gift possible).
- Optional: soft-hide instead of hard-delete for audit retention.
