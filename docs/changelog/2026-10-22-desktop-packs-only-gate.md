# Desktop 1.4.9 — packs-only access, inline profiles, no profile cap

**Date:** 2026-10-22
**Surfaces:** `camxora_python` (desktop), `platform_api`

## What changed

### Desktop access now follows live pack credits

`GET /api/v3/users/me` exposes `desktop_access`. It is true when the wallet has
credits **and** a live `credit_wallet_lots` row (`tag='pack'`, `remaining_units > 0`,
`expires_at > NOW()`). Pack credits already expire 30 days after purchase and every
new purchase re-stamps live lots, so access ends automatically with the term or
when the balance reaches zero.

Legacy paid licenses and paid web subscriptions remain eligible so grandfathered
accounts are not locked out.

### Inline channel-profile creation

Settings → Profiles now creates profiles in place: "New Profile" opens a blank
draft, the name is the only required field, and logo/cover/folder/template can be
added before or after creation. The portal redirect and onboarding modal are gone.

### Profile limit removed

`ProfileService.create_profile()` no longer enforces the retired plan channel
allowance, and `ensure_profile_capacity()` is a no-op. Name uniqueness and the
100-character limit still apply. Desktop shows `N profiles used.` without a cap.

### Buy Credits dialog

The old Monthly/Yearly subscription dialog is replaced by the web-music pack grid
(Small / Medium / Pro / Large) with credits, songs equivalent, and 30-day term
copy. CTA opens `music.camxora.com` pricing.

## Verification

- Desktop: `test_settings_view`, `test_desktop_entitlement`, `test_upgrade_plans_dialog` — 22 passed.
- Platform API: `test_users_router`, `test_auth_router` — 35 passed.
- Sandbox: live-pack non-admin account returns `desktop_access=true`; profile
  creation succeeds at 10 profiles.
- Production: file-scoped deploy of `license_repo.py`, `users.py`,
  `profile_service.py`; `/health` OK; live account check returned `desktop_access=true`.

## Notes

- Deploying the desktop client is required for the new UI. The production API fix
  alone unblocks existing clients' profile creation but cannot change their
  subscription dialog.
