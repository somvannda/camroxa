# Desktop entitlement ignores paid web subscriptions

## Summary

A desktop user with a paid web subscription (e.g. the hidden **Monthly · 2-channel**
$79 plan, `web_subscriptions`) could log in successfully but was then shown the
**Choose Your Plan** / upgrade popup.

Root cause: `GET /api/v1/users/me` (and `PATCH /api/v1/users/me`) resolved
`plan_name` and `onboarding_paid` from the legacy `licenses` table only. Paid
web subscribers live in `web_subscriptions` (CutLuy checkout), so the response
returned `plan_name = null` and `onboarding_paid = false`. The desktop client
checks `onboarding_paid` in `user_can_use_desktop_studio()`, so it treated the
paid account as unpaid and opened the upgrade dialog.

## Product impact

- Paid web subscribers can now use the desktop app after login without being
  asked to upgrade. No desktop client release needed — the client already treats
  `onboarding_paid = true` as paid.
- `plan_name` is now populated for web subscribers in `/users/me` responses.

## Technical impact

- Added `_fetch_active_web_plan(pool, user_id)` in `platform_api/routers/users.py`:
  returns the active, non-expired `web_subscriptions` row's `plans.name` and
  whether `price_cents > 0`.
- `get_me` and `update_me` now fall back to that web plan name when the license
  row has none, and OR `web_plan_paid` into `onboarding_paid`.
- This matches the entitlement rule already used by the desktop login gate
  (`has_paid_desktop_access`) and by the admin endpoints, which already resolved
  plans from license-then-web-subscription.
- The onboarding-AI guard (`user_has_paid_for_onboarding`) still reads licenses /
  billing payments only — see Follow-ups.

## Files touched

- `platform_api/routers/users.py`
- `platform_api/tests/test_users_router.py`

## Migration / deploy

- No migration. Server-only change; deploy `platform_api` and restart the API
  service.

## Tests

- `python -m pytest tests/test_users_router.py -q` → 9 passed.
- `python -m pytest tests/test_onboarding_entitlement_service.py -q` → 10 passed.
- Added `test_recognizes_paid_web_subscription` reproducing the $79 plan name.

## Follow-ups

- `services/onboarding_entitlement_service.user_has_paid_for_onboarding` still
  ignores `web_subscriptions`, so a web subscriber can hit
  `ONBOARDING_PAYMENT_REQUIRED` in onboarding-AI gating. Align it with the same
  web-subscription fallback.
