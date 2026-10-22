# musicapi: redeemable promo codes (checkout + standalone credits)

## Summary

Promo codes existed in the database and the admin console but could not be used
by customers: `musicapi` checkout had no code field, and no code could grant
credits without a purchase. This change closes both gaps on the musicapi
surface and ships a ready-made mail template for each kind.

> Surface note: this is `musicapi.camxora.com` + `admin.musicapi.camxora.com`.
> The consumer product at `music.camxora.com` runs on `platform_api` /
> `music_web` and is **not** changed by this work.

## Product impact

- Billing (`musicapi.camxora.com/dashboard/billing`) has an optional promo-code
  field: percent-off updates each pack price, bonus codes add credits, and the
  server recomputes the charge at checkout.
- Campaign links `/dashboard/billing?code=…` apply the code automatically and
  strip it from the URL so a refresh cannot replay a used code.
- New `musicapi.camxora.com/dashboard/redeem` page claims a standalone credit
  code with no purchase, shows the credits granted and the new balance, and
  accepts `?code=` deep links.
- Admin (`admin.musicapi.camxora.com/admin/mail/promos`) can create the new
  “Redeem for credits” kind, for public or per-recipient campaign codes.
- The credit ledger shows a `promo` type (filter + badge) distinct from
  purchases, referrals and admin adjustments.
- A `credit_code` email template links the Redeem page and prints
  `{{discount_credits}}`.

## Technical impact

- `0038_promo_standalone_credit.sql` widens `promo_codes.kind` with `credit`
  and `credit_transactions.type` with `promo`.
- `src/promo.ts`: shared `lookupPromoForUser`; `validateStandalonePromo`;
  checkout quotes reject standalone codes; `redeemPromo` reports whether it
  actually claimed the code and accepts a NULL `payment_transaction_id`.
- `src/server.ts`: `POST /me/promo/redeem` claims inside one transaction —
  `SELECT … FOR UPDATE`, cap/expiry/ownership re-check, unique
  `(code_id, user_id)` insert, counter bump, `promo` ledger grant. Concurrent or
  retried claims cannot double-grant.
- `web-user`: promo field + per-pack preview; `?code=` auto-apply; Redeem page
  and sidebar entry.
- `web-admin`: new kind in codes/campaigns; `promo` ledger tone and filter.
- `0039_mail_credit_code_template.sql` inserts the `credit_code` template only
  when absent, so an operator's edited copy survives a deploy; the seed script
  carries the same row for fresh databases.

## Files touched

- `musicapi/migrations/0038_promo_standalone_credit.sql`
- `musicapi/migrations/0039_mail_credit_code_template.sql`
- `musicapi/scripts/mail-templates-seed.sql`
- `musicapi/src/promo.ts`
- `musicapi/src/server.ts`
- `musicapi/test/promo.test.ts`
- `musicapi/web-user/app/dashboard/billing/page.tsx`
- `musicapi/web-user/app/dashboard/layout.tsx`
- `musicapi/web-user/app/dashboard/redeem/page.tsx`
- `musicapi/web-admin/app/admin/mail/campaigns/page.tsx`
- `musicapi/web-admin/app/admin/mail/promos/page.tsx`
- `musicapi/web-admin/app/admin/transactions/page.tsx`
- `musicapi/web-admin/app/admin/users/[id]/page.tsx`
- `docs/changelog/2026-10-22-musicapi-redeem-codes.md` (this file)

## Migration / deploy

- Merged as PR #439 (`d261853f`).
- Sandbox: `sync_musicapi_sandbox.py` on 2026-10-22 — `0038` + `0039` applied,
  services restarted, health `{"ok":true,...}`.
- Production: `deploy_musicapi_production.py --yes` on 2026-10-22 — `0038` +
  `0039` applied, all units active, health OK, `credit_code` template present.
- Verified live: `musicapi.camxora.com` health/portal/billing/redeem `200`,
  `/backend/me/promo/redeem` and `/validate` `401` anon, admin login `200`.

## Tests

- `npm run test:unit` → 121/121 pass (new: standalone code refused at checkout,
  `credit` preset coercion).
- `tsc --noEmit` clean in `musicapi`, `web-user`, `web-admin`; ESLint clean on
  touched files.
- Fresh-database run: 42 migrations apply, re-run applies 0; constraints accept
  `credit`/`promo` and reject unknown values.
- Mail seed run twice: 13 templates, no duplicates; `credit_code` links
  `/dashboard/redeem?code={{code}}`.
- CI on PR #439: 10/10 checks green.

## Follow-ups

- If redeem codes are wanted on the consumer site (`music.camxora.com`), that is
  a separate implementation on `platform_api` / `music_web`; this work does not
  reach it.
- The seeded percent-off promo template is hardcoded to “20% off”; use the
  `credit_code` template for standalone credit campaigns.
- Refunds reverse granted credits but do not return a consumed code.
