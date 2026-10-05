# Desktop $79 plan — October credit reconcile (5,150 − October usage)

**Date:** 2026-10-05 · **Scope:** production `camxora_platform` · plan `0dec7f5e…` ("Monthly · 2-channel")

## Decision

1. **Plan credit = 5,150** (unchanged). The `monthly_credits` was briefly raised to **6,275**
   (5,150 + 1,125 price-delta) during the 7.5→10 pricing change; reverted to **5,150**, which
   already covers the plan's 450 generations (music 4,500 + draft/album ~22 + images).
2. **Monthly rule for a paying subscriber:** `wallet = 5,150 − (their October credit usage)`.
3. **Lapsed users** (no October license/payment) get **no October allowance** and were not touched.

## Final October balances

| user | Oct generations | Oct credits used | wallet before | **wallet now** |
|---|---:|---:|---:|---:|
| somvannda | 246 | 2,378.42 | 5,125.74 | **2,771.58** |
| sophay | 210 | 1,798.77 | 3,924.10 | **3,351.23** |
| edmbass1 | 10 | 91.94 | 6,378.06 | **5,058.06** |
| mr.zhiwei | 0 | 140.15 | 3,120.29 | **5,009.85** |

*"Oct credits used" = real October debits (music + lyric/title/album + images − refunds),
excluding reconcile/clawback rows.*

## Not on the October plan (untouched)

| user | license ended | wallet |
|---|---|---:|
| tepchanpanharith | 2026-10-02 | 1,190.00 |
| khunmao.kh | 2026-09-01 | 52.00 |
| chanchanharithtep168 | 2026-10-02 (revoked) | 50.00 |

## Ledger

- Each adjustment is a single `credit_transactions` row:
  `admin_adjustment: reconcile October plan (5150 - usage)` with
  `metadata.reason_code = oct2026_plan_5150_minus_usage` (reversible; target units recorded).
- This **absorbs** two earlier moves for these accounts:
  - the **+1,125** price-delta grant (Oct 5) — no longer applied; and
  - the earlier **−5,150** "extra monthly allowance" reconcile.

## Why (context)

The two monthly grants seen for some users (e.g. `mr.zhiwei`: Sep 2 period + Oct 2 period) were
**legitimate — one per paid month**, not the daily-stacking bug. The earlier flat −5,150 had
double-charged September's usage (September's allowance was deleted while its burn stayed).
This restates everything to a single, clear rule: **current month = 5,150 − current-month usage.**
