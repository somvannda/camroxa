# Production outbound SMTP (free/cheap relay)

**Date:** 2026-07-26  
**Status:** script ready — waiting for free SMTP credentials

## Summary

Production mail uses a **free/cheap SMTP relay** (Resend or Brevo recommended), not Namecheap Private Email and not a self-hosted MTA on the VPS. Camxora already sends verification/notification mail via `PLATFORM_SMTP_*`.

## Product impact

- Registration verification and transactional email work once SMTP is configured.
- Avoids mailbox subscription cost.

## Technical impact

- `scripts/deploy/configure_smtp_production.py` writes SMTP settings into prod `platform_api/.env` and restarts `camxora-api`.

## Recommended providers (free tier)

| Provider | SMTP host | Auth | Notes |
|----------|-----------|------|--------|
| **Resend** | `smtp.resend.com` | user `resend`, password = API key | Simple; verify domain DNS |
| **Brevo** | `smtp-relay.brevo.com` | SMTP login + key | Generous free daily limit |
| Amazon SES | region endpoint | IAM SMTP user | Very cheap at scale; more setup |

Do **not** run Postfix/Exim on the Camxora VPS for outbound — poor deliverability without warm IP/rDNS.

## Migration / deploy

1. Create free Resend or Brevo account; add/verify `camxora.com` (SPF/DKIM DNS).
2. Fill `.deploy/secrets.env` `PLATFORM_SMTP_*` (never commit).
3. `python scripts/deploy/configure_smtp_production.py`

## Files touched

- `scripts/deploy/configure_smtp_production.py`
- `.deploy/secrets.env.example`
- `docs/changelog/2026-07-26-production-smtp.md`

## Follow-ups

- Production DNS + TLS still pending for public HTTPS.
- After SMTP is live, smoke-test register verification email.
