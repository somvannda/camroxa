# Credit invariants: count period grants, and flag no-expiry lots separately

**Date:** 2026-11-11
**Branch:** `fix/credit-invariant-scope`
**Surfaces:** platform_api
**Status:** implemented (tests pass, validated read-only on production); not deployed

## Summary

The daily `CREDIT INVARIANTS` alert counted **every** live `tag='grant'` lot as
a "stacked grant". That was correct when the only grant lots came from the
monthly plan allowance, but since the credits-only cutover (migration 174) the
refund path also mints `grant` lots. On production the check was reporting **50
users**, of which **zero** had stacked period grants — 8 were refund artifacts
(now repaired) and 42 were historical monthly grants with a single grant each.

The real regression it should catch — refund lots minted with
`expires_at = NULL`, which can never expire — was not checked at all.

## Fix

- `_MULTI_LOT_SQL` now requires `period_start IS NOT NULL`, i.e. it counts
  period grants only, which is what "more than one live grant lot" was meant to
  detect. It also ignores lots whose expiry has passed.
- New `_NON_EXPIRING_GRANT_SQL` reports `tag='grant'` lots with
  `remaining_units > 0 AND expires_at IS NULL`. This is the guard for the
  `_restore_lots` bug fixed in `fix/refund-lot-expiry`; any new row here means
  the refund writer regressed.
- `has_credit_violations` treats either list as a violation, and the Telegram
  message labels the two cases separately: "multiple live period grant lots"
  and "grant lots with no expiry".

## Validation

- `tests/test_credit_invariants.py`: 9 passed, including the new no-expiry
  violation and two SQL regression guards (`period_start IS NOT NULL`, and the
  no-expiry query targets `tag='grant'`).
- Read-only production query with both new statements after the 2026-11-11 lot
  repair: **0** rows for each.

## Follow-ups

- Deploy with the other credit branches; the alert stays silent only once the
  scoped query is running.
- No data change is required by this patch.
