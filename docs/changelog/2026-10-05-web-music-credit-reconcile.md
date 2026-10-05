# Web-music credit reconciliation — 2026-10-05

**Artifact:** [`docs/reconcile/2026-10-05-web-music-credit-reconcile.html`](../reconcile/2026-10-05-web-music-credit-reconcile.html)
(snapshot generated 2026-10-05T08:08:01 CEST from production `camxora_platform`)

## Why

A period-grant bug minted the **monthly** allowance **once per day** (each lot living a
full billing cycle), so grants **stacked** in wallets — a Free user could hold thousands
of credits instead of 50, a Creator instead of 3,500.

## What was done (companion scripts, #287)

- `scripts/deploy/_clawback_stacked_period_grant.py` — removed the **duplicate stacked
  grants**, leaving **one** allowance:
  - 7 Free users → kept **50** (tepchanpanharith, pich.sou11, iamduke1987, rinmakara2050,
    ponlorkleav168, sokha7939, vaththary), total **−29,682.78** across all 10.
  - 3 paid web-sub users → kept their paid allowance (sommakara84 3,500;
    teangchunpanhavorn 1,000; touchphinnarith90 1,000).
- `scripts/deploy/_reconcile_web_music_paid.py` — set paid users to
  `allowance + non-grant − net generations` (i.e. charge real usage, keep unused).

Non-grant credits (packs / top-ups / quota-conversion) were **never touched**.

## Final agreed balances (verified against wallets)

| user | allowance − used | final |
|---|---:|---:|
| sommakara84 | 3,500 − 852.50 | 2,647.50 |
| teangchunpanhavorn | 1,000 + 1,001 − 258 | 1,743.00 |
| touchphinnarith90 | 1,000 − 342.50 | 657.50 |
| pich.sou11 (lapsed sub) | 50 + 826 | 876.00 |

## Decisions

1. **Bug duplicates → removed** (correct; the extra copies were never paid for).
2. **Lapsed users forfeit unused allowance**, back to Free 50; **paid extras kept**
   (`pich.sou11` → 876; `tepchanpanharith` → 1,190). Clawback **stands**; no restore.
3. **Desktop / $79 license plans are excluded** from these scripts (they only exclude
   *active* licenses — a lapsed license like `tepchanpanharith` falls into the Free bucket).

## Flagged for review (not changed)

Three **active** $79 users hold **two 5,150 grants (10,300 total)** and were **not**
clawed (active-license exclusion): `mr.zhiwei`, `edmbass1`, `sophay`. Confirm whether the
two overlapping monthly allowances are intended (early-renewal overlap) or should be
reconciled like the others.
