# Production outbound SMTP (Namecheap Private Email)

**Date:** 2026-07-26  
**Status:** script ready — waiting for SMTP password in secrets

## Summary

Production mail uses an SMTP relay (Namecheap Private Email / `mail.privateemail.com`), not a self-hosted mail server on the VPS. Camxora already sends verification and notification email via `platform_api` SMTP settings.

## Product impact

- Registration / email verification and transactional mail work on production once SMTP is configured.
- Without SMTP, those flows fail silently or cannot deliver codes.

## Technical impact

- Writes `PLATFORM_SMTP_*` + from-address into `/opt/camxora/repo/platform_api/.env` on the production VPS and restarts `camxora-api`.
- Script: `scripts/deploy/configure_smtp_production.py`

## Files touched

- `scripts/deploy/configure_smtp_production.py`
- `.deploy/secrets.env` (local only — SMTP block template; never commit)
- `docs/changelog/2026-07-26-production-smtp.md`

## Migration / deploy

1. In Namecheap Private Email, ensure mailbox `noreply@camxora.com` exists (or your chosen from-address).
2. Fill in `.deploy/secrets.env`:
   - `PLATFORM_SMTP_HOST=mail.privateemail.com`
   - `PLATFORM_SMTP_PORT=587`
   - `PLATFORM_SMTP_USER=noreply@camxora.com`
   - `PLATFORM_SMTP_PASSWORD=...`
   - `PLATFORM_SMTP_USE_TLS=true`
   - `PLATFORM_EMAIL_FROM_NAME=Camxora`
   - `PLATFORM_EMAIL_FROM_ADDRESS=noreply@camxora.com`
3. Run: `python scripts/deploy/configure_smtp_production.py`
4. Optional SPF/DKIM in DNS for `camxora.com` (Namecheap Private Email docs).

## Tests

- After configure: register/resend verification on `app.camxora.com` (or HTTP Host header until DNS/TLS is live).

## Follow-ups

- Production DNS + TLS still pending.
- Do not run a full MTA (Postfix) on the Camxora VPS for outbound mail.
