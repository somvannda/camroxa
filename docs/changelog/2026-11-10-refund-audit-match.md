# Refund audit: match auto-refunds and do not flag a successful retry

**Date:** 2026-11-10
**Branch:** `fix/refund-audit-match`
**Surfaces:** scripts/ops
**Status:** implemented (validated read-only against production); not deployed

## Summary

The daily `ops-alert.sh` guard reported **4 failed songs charged without a
refund**. Only **2** were real; the other 2 were artifacts of the audit query.
One of the two real ones was already refunded manually, and the remaining two
(the real ones) have now been refunded — see "Production action" below.

## Root causes

1. **Automatic refunds were invisible.** The query only counted a refund when
   `direction IN ('credit','refund') **AND** reason ILIKE '%refund%'`. The
   automatic paths write `suno_generation_failed`, `web_music_generation_failed`,
   `image_generation_failed` and `image_generation_deferred` — none contain the
   word "refund". A charge that was refunded seconds earlier was reported as
   unrefunded.
2. **A successful retry was counted as a failed charge.** Desktop charges are
   keyed by the song id and re-charged for every attempt; joining a charge to any
   failed task on that song flagged the successful retry too. The query now
   compares counts per reference: `charges - refunds - successes`.

## Fix

`scripts/ops/audit_failed_music_refunds.py` is rewritten as a per-reference
count:

- charges: `v3_music` debits for the reference inside the window;
- refunds: `direction='refund'` **or** a `%refund%` reason (covers both the
  automatic and the manual/ops paths);
- successes: successful `suno_tasks` rows for the reference (task id or song id);
- report only when `charges > refunds + successes`, the reference has a terminal
  failure, and no task on it is still in flight.

Charges with `ref_id IS NULL` (old desktop builds) cannot be matched by key; the
script now counts them separately as unverifiable instead of silently ignoring
them.

The same reason-filter bug was fixed in `scripts/ops/audit_orphan_music_charges.py`
and `scripts/ops/refund_failed_music_charges.py` (the latter could otherwise
refund a charge that an automatic refund had already settled).

## Validation (read-only, production)

- New audit, 7 days: **0** unrefunded charges, **0** unverifiable.
- New audit, 30 days: **0** unrefunded charges; **2,945** historical unkeyed
  desktop charges (29,450 credits) now surfaced as unverifiable instead of
  hidden.
- Old audit reproduced the 4-row result before the fix.

## Production action taken

Two genuinely unrefunded web-music charges were refunded through the idempotent
ledger path (`reason='v3_refund_music'`, `ref_id=<task id>`):

| user | charge | refund tx | balance |
|---|---|---|---|
| sommakara84@gmail.com | `6453807a…` (2026-11-06) | `b06116ed-6329-4d1e-827c-67f112dd2356` | 835.68 → 845.68 |
| pengchun.pc@gmail.com | `25e22411…` (2026-11-08) | `807275b7-54a2-4b02-8ac1-28da8b766e06` | 4976.88 → 4986.88 |

Both refunds landed in the existing live pack lot, so `wallet == SUM(live lots)`
still holds for both accounts.

## Follow-ups

- The remaining false positives (somvannda's desktop charges) disappear as soon
  as this query ships.
- Root cause of the web-music leak: `_refund_web_music_generation_on_failure`
  returns early for `is_pro` users. Fix separately.
- The 2,945 unkeyed desktop charges need the admin audit's time-correlation path;
  the ops guard cannot see them by key.
