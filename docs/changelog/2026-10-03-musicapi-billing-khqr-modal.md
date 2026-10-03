# Billing: render the KHQR inline in a modal (no ChmabaPay redirect)

## Summary

On `/dashboard/billing`, **Buy Credits** redirected the payer to ChmabaPay's
hosted checkout page instead of showing the KHQR code. The core API already
received the KHQR payload (`qr_string`) from `POST /payments/chmaba/create`, but
the user app ignored it and only followed `checkout_url`.

The billing page now opens an inline modal that shows the KHQR code, an expiry
countdown, and live payment status. ChmabaPay is only used as a fallback if the
provider returns no QR.

## Product impact

- Payer clicks **Buy Credits** and a modal appears with a scannable KHQR code,
  the pack amount/credits, and a countdown — they stay on `musicapi.camxora.com`.
- The modal polls for payment, then refreshes the credits balance and transaction
  history and closes automatically once paid.
- If the code expires, the modal says so and the payer can start a new payment.
- No pricing, credit, or ledger behavior changes.

## Technical impact

- `musicapi/src/server.ts`
  - `POST /payments/chmaba/create` now also returns
    `qr_url: /payments/chmaba/qr/<transaction_id>`.
  - New `GET /payments/chmaba/qr/:id`: auth-gated and ownership-checked; proxies
    ChmabaPay's public, stateless renderer
    (`GET /v1/khqr/render.svg?payload=<qr_string>`, falling back to
    `GET /pay/<provider_payment_id>/qr.svg`) and returns it as
    `image/svg+xml`. Keeps the raw KHQR payload and the provider origin
    server-side. Uses the configured `CHMABA_API_BASE_URL`; no API key needed
    for the public renderer.
- `musicapi/web-user/app/dashboard/billing/page.tsx`
  - `buy()` opens the modal when the create response carries `qr_url`; only
    falls back to `window.location.assign(checkout_url)` when it does not.
  - Extracted a reusable `load()` so the modal can refresh after payment.
- `musicapi/web-user/components/billing/khqr-modal.tsx` (new)
  - Renders the QR via `qr_url`, polls
    `GET /payments/chmaba/status/:id` every 3s (the route reconciles against
    ChmabaPay's authoritative check-status endpoint), shows pending/scanned/
    paid/expired states, and auto-closes ~2.5s after payment.
- `musicapi/web-user/lib/api.ts`
  - Added `backendUrl(path)` for same-origin backend assets (`<img src>`).
- `musicapi/REQUIREMENTS.md` — §3.7 updated to describe the inline modal.

No schema change, no migration.

## Files touched

- `musicapi/src/server.ts`
- `musicapi/web-user/app/dashboard/billing/page.tsx`
- `musicapi/web-user/components/billing/khqr-modal.tsx`
- `musicapi/web-user/lib/api.ts`
- `musicapi/REQUIREMENTS.md`
- `docs/changelog/2026-10-03-musicapi-billing-khqr-modal.md`

## Migration / deploy

1. Deploy the musicapi core API (new `qr_url` field + `GET /payments/chmaba/qr/:id`).
2. Rebuild `web-user` (billing page + modal + `backendUrl` helper).
3. No `web-admin` change and no migration.
4. Requires `CHMABA_API_KEY` + `CHMABA_STORE_ID` to be set (checkout stays 503
   otherwise, unchanged).

## Tests

- `musicapi`: `npm run typecheck` → clean.
- `musicapi/web-user`: `npm run typecheck` → clean; `npm run build` → success;
  `eslint` on changed files → clean.
- `GET https://pay.chmaba.com/v1/khqr/render.svg?payload=…` → `200 image/svg+xml`
  (verified live; used to confirm the proxy target).

## Follow-ups

- No automated test hits the QR proxy or the modal; coverage is CI typecheck/build
  plus a live sandbox smoke.
- The ChmabaPay hosted checkout URL is retained in the API response as a fallback.
