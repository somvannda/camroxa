# ChmabaPay as a switchable KHQR provider (CutLuy kept)

**Date:** 2026-10-21  
**Surfaces:** platform_api, music_web, admin_portal

## Summary

`music.camxora.com` and `admin.camxora.com` can now take paid checkout through
either **CutLuy** or **ChmabaPay (`pay.chmaba.com`)**, selected in
**Admin → Settings → Payment**. The existing provider switch
(`billing.active_provider` + `billing.provider.<id>.enabled`) gains `chmaba` as
a third registry entry, so no new switching mechanism was introduced.

ChmabaPay is opt-in and starts **OFF**. The default provider logic is unchanged
(mock in debug, CutLuy in production), so deploying this cannot silently move
live money.

## Product impact

**Before:** only CutLuy could mint a KHQR; if the operator wanted ChmabaPay there
was no path beyond editing code.

**After:** the admin console exposes a ChmabaPay credentials card and an ON/OFF
tile. Turn ChmabaPay ON, pick it as the active provider, keep CutLuy OFF. Applies
to desktop/onboarding plan checkout, credit packs, add-ons and music-web top-ups.

## Technical impact

Provider plumbing:

- `services/billing_provider_service.py` (new) — single source of truth for the
  registry and the enabled/available/active rules, shared by the billing router
  and the v2 top-up service.
- `services/shared/chmaba_service.py` (new) — `POST /v1/payments`,
  `GET /v1/transactions/check-status/{id}`, DB-resolved credentials.
- `services/chmaba_webhook.py` (new) — `X-ChmabaPay-Signature` (`t=…,v1=…`,
  HMAC-SHA256, ±300 s, constant-time) plus `reference_id` scanning.
- `routers/billing.py` — `chmaba` branch in the provider registry, checkout
  creation, status refresh, `POST /billing/webhooks/chmaba` (+ `chmabapay`
  alias), and `POST|GET /billing/chmaba/payments` compatibility routes.
- `services/v2/topup_service.py` — resolves the provider per checkout, records
  it on `topup_purchases.payment_provider`, and polls the matching gateway.
  ChmabaPay uses the local top-up id as `reference_id`, so the webhook can bind
  to the exact row without trusting client metadata.
- `services/v2/payment_security.py` — ChmabaPay checkout-host allowlist
  (`*.chmaba.com` or the admin-configured API host).

Admin and user surfaces:

- `GET|PUT /api/v3/admin/billing/chmaba-config` — masked credentials endpoint.
  The API key and webhook secret cannot be set through generic
  `/admin/system-settings`, mirroring the CutLuy protection.
- `admin_portal` — new `use-billing-chmaba` hook, provider tile, credentials
  card and setup instructions.
- `music_web` — checkout URL allowlist accepts both providers; KHQR modal copy
  is provider-neutral.

Deploy plumbing:

- `PLATFORM_CHMABA_API_KEY|STORE_ID|WEBHOOK_SECRET|API_BASE_URL` are emitted by
  both remote installers and forwarded from `.deploy/secrets.*.env`.

## Migration/deploy

No schema migration required: `topup_purchases.payment_provider` already exists
(default `cutluy`) and `billing_payments.provider` is a free-form column.

Register the webhook in the ChmabaPay dashboard as:

```
https://api.camxora.com/api/v3/billing/webhooks/chmaba
```

One URL settles both ledgers: `billing_payments` (plan/add-on/pack checkout) and
`topup_purchases` (music-web credit packs).

## Tests

```
pytest platform_api/tests/test_chmaba_provider.py \
       platform_api/tests/test_web_music_owned_checkout.py \
       platform_api/tests/test_billing_config_service.py \
       platform_api/tests/test_billing_plan_fulfillment.py \
       platform_api/tests/test_billing_quota_renewal.py
npx tsc -b                      # admin_portal
npx tsc --noEmit --allowImportingTsExtensions   # music_web
```

## Follow-ups

- **Confirm the live ChmabaPay webhook envelope** before enabling it in
  production. `find_chmaba_reference_id` scans recursively for `reference_id`
  because the provider does not publish the field-by-field shape; if the real
  delivery only carries the provider payment id, plan fulfilment will not bind.
- ChmabaPay's `payment.reversed` event marks the ledger row `refunded` but does
  not claw back delivered credits; that remains a desk/ops action.
- `TopupService` falls back to CutLuy when the provider cannot be resolved, so
  a settings-table read failure degrades to the old path rather than failing
  checkout outright.
- Backfill `payment_provider` for historical `topup_purchases` rows only if
  reporting needs it; all existing rows are CutLuy.
