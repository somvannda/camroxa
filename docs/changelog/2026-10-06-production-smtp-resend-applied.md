# Production SMTP (Resend) actually configured — 2026-10-06

**Surfaces:** production `platform_api/.env`, `scripts/deploy/configure_smtp_production.py`.

## Why

Production `platform_api/.env` had **no `PLATFORM_SMTP_*` keys**, even though the
Resend credentials existed in `.deploy/secrets.production.env`. Email therefore
could not send from production — this affected the existing verification-code
mail **and** the new web-music renewal reminders (both use
`services/email_service.py`, which speaks SMTP).

Camxora's mail provider is **Resend via its SMTP relay**
(`smtp.resend.com:587`, user `resend`, password = Resend API key, STARTTLS),
per `docs/changelog/2026-07-26-production-smtp.md`.

## What changed

- Applied the Resend SMTP keys to production `platform_api/.env`
  (`PLATFORM_SMTP_HOST/PORT/USER/PASSWORD/USE_TLS`, `PLATFORM_EMAIL_FROM_NAME/ADDRESS`)
  and restarted `camxora-api`.
- Fixed `scripts/deploy/configure_smtp_production.py`:
  - it called `load_secrets()` which **defaults to the sandbox** environment
    (would mis-target); it now uses `load_production_secrets()` +
    `resolve_production_ssh()` and asserts `82.197.71.248`;
  - the remote `systemctl restart` ran as `camxora` (polkit-denied); it now runs
    as the deploy user after the env write.

## Verification

- Remote credential check against `smtp.resend.com:587` (STARTTLS + login, no
  send): `SMTP_LOGIN_OK`; `pass_set=True`, `from=noreply@camxora.com`.
- `camxora-api` restarted and `active`.

## Follow-ups

- Confirm real delivery end-to-end (send a verification code / a test reminder
  and check the Resend dashboard + domain SPF/DKIM for `camxora.com`).
- Mirror the same SMTP keys to **sandbox** if its `.env` is also missing them.
- Watch for `web_subscriptions.renewal_reminder_sent_at` populating once a
  subscriber enters the 7-day window.
