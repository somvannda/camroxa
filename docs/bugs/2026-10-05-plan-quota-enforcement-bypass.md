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

## Fix — status

### ✅ Implemented (this PR)
1. **Monthly limit is now a HARD cap for subscription plans** unless the deployment
   opts into wallet overage:
   - New setting `PLATFORM_PLAN_MONTHLY_OVERAGE_ALLOWED` (default **false**).
   - `usage_enforcement_service._enforce_plan_quotas` and the
     `allow_monthly_overage` flag now read it (`is_subscription_plan(plan) and
     get_settings().plan_monthly_overage_allowed`). At/over the limit the request is
     refused with `MONTHLY_QUOTA_EXCEEDED` instead of silently running wallet overage.
   - Files: `platform_api/config.py`, `platform_api/services/usage_enforcement_service.py`.
2. **Daily bank is capped** at `MAX_BANK_DAYS` (3) days of unused allowance, so it can no
   longer be hoarded into a burst:
   - `daily_quota_bank_service.accrue_and_get_banked_units` stops accruing once
     `banked_units >= daily_limit * MAX_BANK_DAYS`.
   - File: `platform_api/services/daily_quota_bank_service.py`.
3. **Authoritative monthly song count (fix B)** — the song quota now counts **real
   generations** (`songs` rows with `status='suno_success'` whose generation date is in the
   period) instead of the fragile incremental `usage_tracking` counter, in both the
   preflight (`_enforce_plan_quotas`) and the atomic reserve (`try_increment_usage`, via
   `monthly_count_override`). This is the change that actually stops the `422 vs 945`
   under-count.
   - Files: `platform_api/repositories/usage_tracking_repo.py`
     (`count_generated_songs_for_period`), `platform_api/services/usage_enforcement_service.py`.
4. **Tests**: `platform_api/tests/test_plan_quota_hard_cap.py` (hard cap blocks by default,
   overage only when opted in, bank capped, authoritative song count drives the cap) + the
   3 existing overage tests updated to opt in.

### ⏳ Remaining
5. **Stable quota-period anchor (fix A).** The period still re-anchors when `activated_at`
   moves on renewal (`compute_billing_period`), so the window can shift by a day. Pin it to
   the license's **original** activation and run a **dry-run report** of how many periods
   shift before applying.
   - ⚠️ A naive "sum all overlapping `period_start_date` rows" is **wrong** — it breaks the
     activation-aligned rule (caught by
     `test_quota_period_follows_license_activation_not_calendar_month`). Do not ship it.
6. **Charge overage / legacy 0-credit songs to the wallet** — pair with the billing fix.

### Rollout note
Default is a hard cap and the song count is now authoritative. If a plan should keep wallet
overage, set `PLATFORM_PLAN_MONTHLY_OVERAGE_ALLOWED=true`. The stable-anchor fix (#5) is the
remaining follow-up.

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
