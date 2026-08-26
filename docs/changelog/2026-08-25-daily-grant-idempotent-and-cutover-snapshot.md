# Fix stacked Free daily grants + cutover credit snapshots

## Summary

Free daily mint credited the wallet **before** inserting the `daily_grant` lot. When the lot insert failed (tag not allowed, then races), `GET /api/v3/me/credits` kept adding 50. Sandbox `duke@test.com` stacked **83 × 50 = 4,150**.

Mint now inserts the unique lot first. No lot → no credits. Cutover scripts dump every user wallet before and after leftover apply and fail if anyone’s balance moved except leftover / period grant / pack / at most one 50-credit daily grant.

## Product impact

- Free users keep **50 credits per day**, not 50 per poll.
- Production leftover cutover will refuse to finish if wallets drift for any other reason.

## Technical impact

- `PeriodGrantService.ensure_daily_grant` / `ensure_period_grant`: `insert_lot_if_absent` (ON CONFLICT DO NOTHING) then `add_credits`.
- Snapshot SQL covers all `users` + wallet + lots + grant/conversion/pack/debit txn sums.
- Diff allows leftover conversion and one daily grant of 50. **+4,150 daily grant fails.**

## Files touched

- `platform_api/services/v3/period_grant_service.py`
- `platform_api/services/v3/store.py`
- `platform_api/tests/test_v3_period_grant.py`
- `platform_api/tests/test_credits_cutover_snapshot.py`
- `scripts/deploy/_credits_cutover_snapshot.py`
- `scripts/deploy/run_credits_cutover_snapshot_sandbox.py`
- `scripts/deploy/run_credits_cutover_snapshot_production.py`
- `scripts/deploy/diff_credits_cutover_snapshots.py`
- `scripts/deploy/_clawback_stacked_daily_grant.py`
- `scripts/deploy/run_clawback_stacked_daily_grant_sandbox.py`
- Cutover host scripts (sandbox + production leftover) now dump/diff wallets around apply

## Migration/deploy

No new Alembic revision. Sync `platform_api` to sandbox, restart API, then:

```
python scripts/deploy/run_clawback_stacked_daily_grant_sandbox.py
python scripts/deploy/run_credits_cutover_snapshot_sandbox.py --phase before
```

Production snapshot / leftover apply still require `--i-mean-production`. Do not run until asked.

## Tests

- `test_daily_grant_does_not_credit_when_lot_insert_fails`
- `test_daily_grant_race_conflict_does_not_credit`
- Snapshot diff: unchanged wallets pass; leftover +2200 passes; stacked 4150 fails.

## Follow-ups

- After sandbox clawback, poll `/api/v3/me/credits` for `duke@test.com` and confirm wallet stays 50.
- Use the snapshot pair on the production leftover job, not a full tree sync from a mixed workspace.
