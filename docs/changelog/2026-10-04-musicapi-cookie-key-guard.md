# musicapi deploy: cookie-key guard + secrets backup

## Summary
Hardened the musicapi remote installer so it can no longer silently regenerate
`MUSICAPI_COOKIE_ENCRYPTION_KEY` over existing encrypted Suno accounts, and it
now keeps timestamped backups of `/opt/camxora/.deploy-secrets` before rewriting
it.

## Product impact
Prevents a silent outage where every stored Suno account cookie becomes
undecryptable and the API crash-loops (nginx 502) after a routine deploy. No
user-facing behaviour change when the key is already persisted.

## Technical impact
`scripts/deploy/camxora-musicapi-remote.sh`:
- Tracks whether the cookie key was generated (`COOKIE_KEY_GENERATED`).
- Backs up `.deploy-secrets` to `.deploy-secrets.bak.<UTC>` before overwriting
  (keeps the five most recent).
- Before writing `.env`/restarting, if a key was freshly generated but
  `suno_accounts` already holds encrypted `client_cookie` rows, it restores the
  previous secrets file and aborts with a clear message.

## Files touched
- `scripts/deploy/camxora-musicapi-remote.sh`

## Migration/deploy
No schema change. Ship via the normal musicapi sandbox deploy. On a healthy
redeploy `COOKIE_KEY_GENERATED=0` (the persisted key is reused) and the guard is
a no-op. On abort, the running service is left untouched.

## Tests
- `bash -n scripts/deploy/camxora-musicapi-remote.sh` (syntax).
- Sandbox incident that motivated this: the 2026-10-04 deploy generated a new
  key, the service crash-looped with
  `COOKIE_ENCRYPTION_KEY does not match the key these rows were encrypted with`;
  recovery restored the Sep-29 key into `.deploy-secrets` and `.env`.

## Follow-ups
- Store `MUSICAPI_COOKIE_ENCRYPTION_KEY` in the local
  `.deploy/secrets.{sandbox,production}.env` for durable, versioned custody.
- The production deploy path shares this script, so it is covered.
