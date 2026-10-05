# Plan quota enforcement bypass — 450/month is not a hard cap

**Date:** 2026-10-05 · **Type:** bug / fix proposal · **Area:** `platform_api` (subscription quota enforcement)

## Symptom

Subscription users on **"Monthly · 2-channel"** (`monthly_song_limit = 450`,
`daily_song_limit_per_channel = 150`, `profile_allowance = 2`) generate **far more than 450
songs/month**, with no block:

| user | Aug | Sep | Oct | total | one-day burst |
|---|---:|---:|---:|---:|---|
| somvannda | 1,720 | 894 | 246 | 3,012 | — |
| **mr.zhiwei** | **280** | **945** | 0 | **1,225** | **465 songs in 2 min (Sep 30 18:02–18:03)** |
| sophay | 310 | 455 | 210 | 975 | — |
| edmbass1 | 290 | 480 | 10 | 780 | — |

Consequence: users exceed their plan massively, and (because the legacy path billed 0
credits) **credits never burn** → inflated wallet balances across the board.

## Root causes (with code)

### 1. The monthly limit is only a **soft cap** for subscription plans
`platform_api/services/usage_enforcement_service.py::_enforce_plan_quotas` (≈L2046):

```python
if monthly_count + max(1, additional_count) > monthly_limit:
    # Subscription plans allow wallet overage once included quota is consumed.
    if is_subscription_plan(plan):
        return                      # <-- no block; falls through to wallet
    raise QuotaExceededError(...)
```

So a subscription plan **never blocks on the monthly limit** — it is allowed to run wallet
**overage**. Combined with the 0-credit legacy billing (below), the overage was **free**,
i.e. effectively unlimited.

### 2. The daily bank allows bursts
Same file (≈L1979–1989):

```python
daily_limit, banked_units, daily_count = await self._resolve_daily_bank_state(...)
effective_daily = daily_limit + banked_units          # <-- bank added on top
...
if daily_count + requested > effective_daily:  # only then block
```

Unused daily allowance accrues into `daily_quota_bank` (`banked_units`). mr.zhiwei banked:

```
music  banked_units 6,234 / 6,448     (two channels)
```

So the "150/channel/day" cap is really `150 + banked`, which let him submit **31 batches ×
15 songs = 465 songs** at once on Sep 30.

### 3. Overlapping `plan_usage` rows fragment the monthly counter
`platform_api/repositories/license_repo.py` — `plan_usage` is keyed by
`(user_id, license_id, period_start)`, and `_period_start` uses
`period_start_for_subscription(plan, activated_at)`. When the activation anchor shifts,
**overlapping rows** appear:

| period_start | period_end | songs_used |
|---|---|---:|
| 2026-08-02 | 2026-08-31 | 280 |
| 2026-09-01 | 2026-09-30 | **30** |
| 2026-09-02 | 2026-10-01 | **392** |

`get_current_usage` reads `ORDER BY period_start DESC LIMIT 1`, so only the newest row is
used and the older row is ignored → the effective monthly count is **understated** (392
instead of the true Sep total).

### 4. Legacy 0-credit billing (pre-2026-09-22) — companion fix
Before 2026-09-22, `music via suno` debits were written with **amount = 0** (6,031 of 6,062),
so overage songs cost nothing. Historical: ~5,363 songs were never charged. (Tracked
separately — see the credit-reconciliation report.)

## Impact
- Plan limits are effectively unenforceable for subscriptions → unlimited generation.
- Wallet credits do not burn → large balances / reconciliation work.
- Real **Suno provider cost** is incurred and **not billed** to the user.

## Proposed fix

1. **Make the monthly limit a hard cap for subscription plans** (or, if overage is
   intended, gate it on `wallet_balance > cost` and *actually deduct*). Suggested: add a
   `monthly_overage_allowed` plan flag; default **off** so `450` blocks.
   - File: `usage_enforcement_service.py::_enforce_plan_quotas`.
2. **Cap the daily bank** so it can't be hoarded:
   - `banked_units = min(banked_units, daily_limit * MAX_BANK_DAYS)` (e.g. 3).
   - Or disable banking for paid plans / only bank up to 1 day.
   - Files: `daily_quota_bank_service.py`, `daily_quota_bank_repo.py`.
3. **Fix monthly counting across overlapping periods**:
   - Sum usage over **all** `plan_usage` periods that overlap the current period (or over
     `usage_tracking` by month), instead of the latest row only.
   - Prevent overlap: keep a single row per license per *billing month*, and clean up
     existing overlapping rows.
   - Files: `license_repo.py` (`get_current_usage`, `get_or_create_usage`),
     `billing_period_service.py` (`period_start_for_subscription`).
4. **Charge overage to the wallet** (pair with the 0-credit billing fix) so overage is paid.
5. **Tests**: at exactly `monthly_song_limit`, an extra batch is refused (subscription);
   a single day cannot exceed `daily_limit × MAX_BANK_DAYS`.

## Evidence (reproduce)
```sql
-- monthly fragmentation
SELECT period_start, period_end, songs_used
FROM plan_usage WHERE user_id = 'a1678130-5557-4573-8151-56a1def96d10'
ORDER BY period_start;

-- one-day burst (465 songs in 18:00)
SELECT to_char(created_at,'HH24:00') h, count(*)
FROM songs WHERE user_id='a1678130-5557-4573-8151-56a1def96d10'
  AND created_at::date='2026-09-30' GROUP BY 1 ORDER BY 1;

-- banked daily allowance
SELECT operation_type, banked_units, last_accrual_date
FROM daily_quota_bank WHERE user_id='a1678130-5557-4573-8151-56a1def96d10';
```

## References
- `platform_api/services/usage_enforcement_service.py` — `_enforce_plan_quotas`, `_resolve_daily_bank_state`, `_period_start`
- `platform_api/services/batch_service.py` — `_enforce_batch_daily_quotas`, preflight
- `platform_api/repositories/license_repo.py` — `plan_usage` read/write
- `platform_api/repositories/daily_quota_bank_repo.py`, `platform_api/services/daily_quota_bank_service.py`
- `platform_api/services/billing_period_service.py` — `period_start_for_subscription`
