# `credit_transactions.reason` was too narrow for an admin adjustment

**Date:** 2026-11-03
**Surfaces:** `platform_api`
**Migration:** `178_credit_txn_reason_text`

---

## Summary

`POST /credits/adjust` accepts a reason of up to **255** characters and stores it
in `credit_transactions.reason` prefixed with `admin_adjustment: ` (~18 chars).
The column was created as `VARCHAR(100)` in `001_initial_schema` and never
widened, so any reason longer than **81 characters** failed the insert with
`value too long for type character varying(100)`.

The failure landed inside `CreditRepository.add_credits`, *after* the
`credit_wallets` balance check, so the request returned a 500 with no adjustment
applied — a confusing dead end for an operator whose only mistake was writing a
detailed reason.

## Fix

`credit_transactions.reason` is now `TEXT`, matching the sibling ledger tables
that already store a free-text reason (`credit_grant_claims`, `admin_pending_ops`).
`VARCHAR` → `TEXT` is a binary-compatible change in PostgreSQL: no table rewrite,
no downtime.

No application code changed. The 255-character route validation stays as the one
bound.

## Files touched

**platform_api**
- `migrations/versions/178_credit_txn_reason_text.py` — widen to `TEXT`;
  downgrade truncates with `left(reason, 100)` so it stays runnable once a long
  reason exists.
- `tests/test_credit_txn_reason_width.py` (new) — the route accepts 255 chars and
  the prefixed reason exceeds the old width; 256 chars is still rejected; the
  migration widens the column and the downgrade truncates.

## Deploy

1. `alembic upgrade head` in `platform_api` (applies `178`).
2. Deploy `platform_api`.

No frontend change.

## Sandbox smoke test

1. Adjust a wallet with a ~200-character reason — succeeds, and the ledger row
   keeps the whole reason.
2. Adjust with a reason of 256+ characters — still 422, not a 500.

## Notes

- Downgrading is lossy by design; expiry-free restore is not possible for reasons
  already longer than 100 characters.
- `usage_transaction_labels.py` formats `admin_adjustment: <reason>` for display
  and is unaffected.
