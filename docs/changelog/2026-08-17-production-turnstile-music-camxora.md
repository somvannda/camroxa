# Production Turnstile for music.camxora.com

## Summary

Prepared production Turnstile configuration and rebuilt `music_web` with the production site key. API `.env` keys were **not** left in place because production `platform_api` on `main` does not yet include Turnstile `Settings` fields — adding them caused a pydantic startup failure (502). API was rolled back and is healthy again.

## Order of operations

1. Merge PR #58 and deploy `platform_api` to production (Turnstile in `config.py`, `turnstile_service.py`, auth router).
2. Add `music.camxora.com` to the Turnstile widget **Allowed hostnames** in the Cloudflare dashboard.
3. Run:

```bash
python scripts/deploy/apply_turnstile_production.py --rebuild-music-web
```

## Changes (repo)

- `scripts/deploy/apply_turnstile_production.py` — upserts `CLOUDFLARE_TURNSTILE_*` with preflight check for Turnstile support in deployed API code.
- `scripts/deploy/restore_production_api_turnstile_env_rollback.py` — emergency removal of Turnstile env lines if API fails to start.
- `.deploy/secrets.production.env.example` — Turnstile placeholders.
- `.gitignore` — ignore `secrets.production.env` and `secrets.sandbox.env`.

## Already applied on production (2026-08-17)

- **Alembic** upgraded `083` → `103_merge_credit_refund_heads` (web music schema, credits, subscriptions, LRC B2, refund idempotency).
- **`platform_api`** synced with web music + Turnstile + CutLuy + credit hardening from `feature/web-music-credits-hardening`.
- **`music_web`** rebuilt at https://music.camxora.com (create, pricing, playlists, login/register with Turnstile site key).
- **Turnstile API `.env`** applied (`CLOUDFLARE_TURNSTILE_*` + hostnames including `music.camxora.com`).
- Smoke: `api.camxora.com/health` **200**, `music.camxora.com/login` **200**, `music.camxora.com/pricing` **200**.

## Manual step (Cloudflare dashboard)

Add **`music.camxora.com`** to the Turnstile widget Allowed hostnames (required for login/register verification).

## Migration fix (repo)

Removed broken merge stubs (`e5077c52f2b7`, `fffddbe8fbb3`, `ff781163cfbb`, `1f0ad008d202`) that referenced non-existent `084_provider_balance_events`. `103_merge_credit_refund_heads` is now a linear continuation of `102`.
