# API v3 Cutover Runbook

**Status:** executed on production 2026-09-22
**Related:** [`API_V3_PRODUCTION_CUTOVER_PLAN.md`](./API_V3_PRODUCTION_CUTOVER_PLAN.md), [`API_V3_HOTFIX_RECONCILIATION.md`](./API_V3_HOTFIX_RECONCILIATION.md), `platform_api/CHANGELOG.md`

## What is live

- `/api/v3` is the canonical surface; `/api/v1` and `/api/v2` remain dual-mounted for rollback.
- Alembic head: `121_upload_job_permanent_failed`.
- `credits_only_v3_charge` = **On** (admin `system_settings`, overrides `PLATFORM_CREDITS_ONLY_V3_CHARGE`).
- nginx production routes stream/WS under `/api/v3`.
- Clients `admin_portal`, `music_web` built from the v3 RC.

## Deploy sequence (performed)

1. **Snapshots** (prod): `pg_dump -Fc` + repo tarball into `/opt/camxora/backups/`.
2. **Migrations** `116→121` (surgical upload of `migrations/versions/116..121`, then `alembic upgrade head`).
3. **API**: `scripts/deploy/sync_platform_api_production.py` from a clean RC checkout.
4. **Clients**: `sync_admin_portal_production.py`, `sync_music_web_production.py`.
5. **Plans/data**: per-op credit fields + desktop `monthly_credits` (song_limit × 10), hidden `$79` = 3000, `Free` plan row.
6. **Leftover conversion**:
   - Web: `run_web_ledger_conversion_production.py --i-mean-production [--apply]`.
   - Desktop: `_credits_only_sandbox_cutover.py` with `APPLY=1` (desktop plan quota × 10).
7. **Flag**: set `credits_only_v3_charge = true`.
8. **nginx**: apply `nginx-camxora-production.conf` (v3 stream/WS), `nginx -t`, reload.
9. **kie**: add key to Key Pool; add to image fallback chain (draft pricing auto-created).

## Rollback (one command sequence)

```bash
# 1) Billing flag off
sudo -u postgres psql -d camxora_platform -c \
  "UPDATE system_settings SET value='false', updated_at=NOW() WHERE key='credits_only_v3_charge';"

# 2) Restore repo (code)
sudo tar -xzf /opt/camxora/backups/repo-<stamp>.tgz -C /opt/camxora

# 3) Restore database (DESTRUCTIVE — resets to snapshot)
sudo systemctl stop camxora-api
sudo -u postgres pg_restore --clean --if-exists -d camxora_platform \
  /opt/camxora/backups/camxora_platform-<stamp>.dump
sudo systemctl start camxora-api

# 4) Restore previous nginx (v1 stream/WS) and reload
#    keep /api/v1 + /api/v2 dual-mount
sudo nginx -t && sudo systemctl reload nginx
```

Flag-only rollback (no data loss) is sufficient when only the billing model is the problem.

## Post-cutover checks

- `GET /api/v3/health` = `healthy`; services include `kie`.
- `GET /api/v3/plans/public` includes `Free` + paid plans.
- Desktop/web generate → wallet debit matches `credit_pricing`.
- Callback routes exist: `/api/v3/callbacks/suno`, `/api/v3/youtube/oauth/callback`, `/api/v3/webhooks/cutluy`.
- Watch 24–72h: 5xx rate, wallet drift, Suno failures, CutLuy fulfillment.

## Leftover conversion reference

- Web leftover: `web_subscriptions.monthly_credits_granted − monthly_credits_used + topup_credits_balance` → credits (`v3_web_remaining`), then remaining zeroed.
- Desktop leftover: `(monthly_song_limit + topup − used) × 10` credits (`v3_quota_conversion`), tracked in `billing_conversion_runs` (idempotent per user).
- Both are additive; wallets are never reduced.

## Still outstanding

- Repoint external dashboards (CutLuy webhook, Google OAuth redirect, Suno callback) to `…/api/v3/…`.
- Publish mandatory desktop update (`camxora_python` ≥ 1.3.2) off `/api/v1`.
- Review/approve the draft `kie` credit pricing.
- Retire `/api/v1` + `/api/v2` after the rollback window; rotate secrets.
