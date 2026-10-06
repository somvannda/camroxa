# SMTP provisioning scripts: safe payload transport — 2026-10-06

**Surfaces:** `scripts/deploy/configure_smtp_production.py`, `scripts/deploy/configure_smtp_sandbox.py`.

## Why

Both scripts built a NUL-separated payload and passed it through `repr()` on the
remote command line. The shell doesn't carry NUL, so the separators arrived as a
literal `x00` string: the remote parser saw **one** malformed pair and wrote a
corrupted line, e.g.

```
PLATFORM_SMTP_HOST=smtp.resend.comx00PLATFORM_SMTP_PORT=587x00...
```

It also leaked the SMTP password into the command line. This is almost certainly
why production `platform_api/.env` had **no** working `PLATFORM_SMTP_*` keys.

The production script additionally loaded **sandbox** secrets
(`load_secrets()` default) and both restarted the service as `camxora`
(polkit-denied).

## What changed

- Both scripts upload the keys as `/tmp/smtp_updates.json` (SFTP, binary) and run
  a small remote reader that upserts them into `platform_api/.env` — no NUL/argv,
  no shell quoting, no secret on the command line.
- Production uses `load_production_secrets()` + `resolve_production_ssh()` and
  asserts `82.197.71.248`; sandbox uses `load_sandbox_secrets()` +
  `resolve_sandbox_ssh()` and asserts `46.250.235.83`.
- `systemctl restart camxora-api` now runs as the deploy user (outside the
  `camxora` shell).

## Verification

- `py_compile` OK for both.
- Sandbox: applied via this transport and confirmed `SMTP_LOGIN_OK`
  (`smtp.resend.com:587`, user `resend`, TLS, from `noreply@camxora.com`).

## Security

The broken run printed the Resend API key in cleartext — **rotate it** and update
`.deploy/secrets.*.env`, then re-run `configure_smtp_production.py` /
`configure_smtp_sandbox.py`.
