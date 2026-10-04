# musicapi: show "Healthy" alongside the captcha auto-solve chip

## Summary

PR #225 made a captcha-required account healthy when a 2Captcha key is
configured, but on the Suno Accounts page it rendered the sky
**"Captcha auto-solve"** chip *instead of* the green **"Healthy"** badge. That
reads as if the account is somehow less healthy, even though it is fully usable
and counted healthy in `GET /admin/stats`.

This shows **"Healthy"** first (an enabled, funded account), then the
informational captcha chip. An account with no solver configured and a required
captcha still shows amber **"Captcha required"** and no "Healthy" badge, because
generation on it would actually fail.

## Product impact

- `ksomvannda@gmail.com` (captcha-required, solver configured) now shows
  **"Healthy"** + **"Captcha auto-solved"** instead of the chip alone.
- Accounts with no solver and a required captcha are unchanged (amber
  "Captcha required", not healthy).
- `GET /admin/stats` `account_health.healthy` is unchanged.

## Technical impact

- `musicapi/web-admin/app/admin/accounts/page.tsx` — `healthBadges()` reworked:
  health is computed first (`!disabled && !low_credits && (!captcha_required ||
  captcha_solver)`), then the captcha note is appended.

Cosmetic only — no API, schema or config change.

## Files touched

- `musicapi/web-admin/app/admin/accounts/page.tsx`
- `docs/changelog/2026-10-04-musicapi-captcha-badge-healthy.md`

## Tests

- `npm run typecheck` in `musicapi/web-admin` → clean.
