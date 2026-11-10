# Web-music failures always refund; reconcile covers web tasks

**Date:** 2026-11-10
**Branch:** `fix/web-music-refund`
**Surfaces:** platform_api
**Status:** implemented (tests pass); not deployed

## Summary

A failed Web Create generation was charged 10 credits and, in practice, **never
refunded automatically**. In 30 days, 5 web-music tasks failed, all 5 were
charged, and **0** were refunded by the automatic path — the 3 that ever got
their credits back were refunded by hand as `v3_refund_music`. The other 2 are
the charges paid out on 2026-11-10 (see `2026-11-10-refund-audit-match.md`).

## Root causes

1. **`is_pro` gate.** `_refund_web_music_generation_on_failure` returned early
   when the user held a live pack. That was a leftover from the retired plan
   model where Pro generations were included rather than charged. It meant the
   only customers never refunded were the paying ones. Production check: the 2
   unrefunded failures had a live pack at failure time; the 3 earlier ones were
   Free users and were still not refunded.
2. **The reconcile sweep cannot see web tasks.** `reconcile_pending_suno_tasks`
   only calls `handle_suno_task_update` when `song_id and batch_id` are set.
   Web Create tasks have neither, so a missed Suno callback left the charge in
   place forever. This is what hit the 3 Free users.
3. **The "already failed" guard never fired.** It upper-cased the prior status
   and compared it to the lower-case enum (`"FAILED" == "failed"`). Harmless
   because `refund_once` dedupes, but it was dead code.

## Fix

- New `platform_api/services/web_music_refund.py` owns the refund and the
  preview-slot release, so both terminal-status paths share one idempotent
  helper (`refund_once`, reason `web_music_generation_failed`, ref = task id).
- `callbacks.py` delegates to it; the `is_pro` gate is gone.
- `reconcile_pending_suno_tasks` now refunds a failed task whose `source` is
  `web_music` even when it has no song/batch id (`list_reconcilable_suno_tasks`
  returns `source`).
- `usage_transaction_labels` knows `web_music_generation_failed` so the admin
  ledger shows a proper label.

## Tests

- New `tests/test_web_music_refund.py`: paying user refunded, reconcile path
  (no prior status) refunded, already-failed skipped, duplicate settlement
  reported as not applied.
- Callback / web-music / reconcile / batch selection: **201 passed**.

## Follow-ups

- The reconcile sweep is still triggered reactively (history/download reads),
  not on a schedule. A scheduled sweep would close the last gap for users who
  never return to the page.
- `WEB_MUSIC_CREDITS_PER_SONG` (10) is used for the refund amount. If a future
  pricing change charges a different amount per model, the refund should use the
  charged amount from the ledger instead of the constant.
