# Paid plan fulfillment 500s on period grant (desktop "Upgrade required")

## Summary

Every paid plan checkout fulfilled through the CutLuy/billing flow was marked
`status = 'paid'` but **never fulfilled** (`fulfilled_at` stayed `NULL`), so no
license was activated. Desktop users whose $79 / Starter / Creator / Studio
checkout went through that flow were then blocked from the desktop app with the
**Choose Your Plan / Upgrade required** dialog, because the desktop gate
(`has_paid_desktop_access`, `onboarding_paid` in `/users/me`) correctly saw no
paid entitlement.

Root cause: `_fulfill_paid_payment()` in `platform_api/routers/billing.py`
builds `PeriodGrantService` with an already-acquired transaction connection:

```python
credit_repo=_CreditRepository(pool=conn),
```

`CreditRepository.add_credits()` (and `atomic_deduct` / `refund`) called
`self._pool.acquire()`, but an `asyncpg.Connection` has no `acquire()`. The new
`ensure_period_grant()` step therefore raised
`AttributeError: 'Connection' object has no attribute 'acquire'`, the webhook
returned HTTP 500, and the fulfillment transaction rolled back.

Introduced by `00f2fa52` (2026-09-29) which added the unconditional
`await grant_service.ensure_period_grant(user_id)` on the fulfillment path.

## Product impact

- Paid checkouts (desktop `$79 Monthly · 2-channel` and billing-checkout web
  plans) fulfill again: the license is assigned and the period grant is minted.
- Desktop users with a paid plan can sign in without the upgrade dialog once
  their pending payment is replayed (see Migration / deploy).
- Users already blocked: `mr.zhiwei@gmail.com` (paid 2026-10-02),
  `sophay@camxora.com` (paid 2026-09-29); both `paid` / `fulfilled_at IS NULL`.

## Technical impact

- `CreditRepository` now reuses an injected `asyncpg.Connection` instead of
  requiring a pool. A new `_connection()` helper borrows from a pool when one is
  passed, or yields the injected connection so wallet writes stay in the
  caller's transaction. Pool callers keep the same transaction behaviour.
- No schema or migration changes.

## Files touched

- `platform_api/repositories/credit_repo.py`
- `platform_api/tests/test_credit_repo.py`
- `platform_api/CHANGELOG.md`

## Migration / deploy

- Server-only change; deploy `platform_api` and restart `camxora-api`.
- Replay the stuck payments so `_fulfill_paid_payment` runs again on the fixed
  code (the CutLuy webhook is idempotent; CutLuy retries may also re-deliver the
  `payment.completed` event). Verify with:

  ```sql
  SELECT email, external_payment_id, status, fulfilled_at
  FROM billing_payments bp JOIN users u ON u.id = bp.user_id
  WHERE bp.status = 'paid' AND bp.fulfilled_at IS NULL;
  ```

## Tests

- `python -m pytest tests/test_credit_repo.py tests/test_v3_period_grant.py \
  tests/test_period_grant_carryover.py tests/test_billing_plan_fulfillment.py \
  tests/test_credit_pack_service.py tests/test_wallet_sync.py \
  tests/test_v3_credits_only.py tests/test_web_music_subscription_credit_reset.py -q`
  → 70 passed.
- Added `TestInjectedConnection` reproducing the `pool.acquire()` AttributeError
  for `add_credits`, `atomic_deduct`, and `refund`.

## Follow-ups

- `platform_api/routers/webhooks_cutluy.py` (`/webhooks/cutluy`) is still dead:
  its `_get_subscription_service` / `_get_topup_service` stubs raise
  `NotImplementedError` because `app.dependency_overrides` does not apply to
  direct calls. CutLuy appears to deliver to both that URL and
  `/billing/webhooks/cutluy`; only the billing route fulfills plans. Wire the
  stubs to their real services (or drop the duplicate route) in a separate change.
