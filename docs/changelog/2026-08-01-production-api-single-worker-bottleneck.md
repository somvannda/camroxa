# Production platform_api was running a single uvicorn worker — bumped to 2

**Date:** 2026-08-01
**Status:** implemented and applied to production

## Summary

The desktop client kept reporting API timeouts (`GET /users/me`, `POST /auth/refresh`) and mid-transfer connection drops (large profile-cover downloads) across v1.0.5–v1.0.7, always while the same account had an active batch (image generation, Suno streaming uploads) running. Investigation traced this to `platform_api` running as a **single uvicorn worker process** in production — confirmed live, not just in the deploy script defaults — while all heavy background work (image job orchestration, Suno streaming uploads, YouTube uploads, batch orchestration) runs as in-process `asyncio.create_task()` / `BackgroundTasks` on that same one process, since the separate `platform_worker` queue process described in `docs/PRODUCTION_INFRASTRUCTURE_PLAN.md` was never built. A busy batch could therefore add enough contention to occasionally starve completely unrelated, trivial requests (auth/session) sharing the same single event loop.

## Product impact

**Before:** users running a batch could see the desktop client stall or fail with timeouts on ordinary actions (login refresh, loading their profile, downloading images) — not because of client bugs or network flakiness, but because one shared server process was doing everything at once.

**After:** `platform_api` runs 2 uvicorn worker processes in production, so a batch actively doing image/Suno/YouTube work no longer serializes all HTTP traffic behind it — a second process is available for simple requests regardless of what the first is doing.

## Technical impact

- `scripts/deploy/camxora-production-remote.sh` / `scripts/deploy/camxora-sandbox-remote.sh`: `API_WORKERS` fallback default changed from `1` → `2` (only takes effect if the deploy secrets file doesn't explicitly set it — belt-and-suspenders).
- `.deploy/secrets.production.env` (local, gitignored): `API_WORKERS` explicitly set `1` → `2`.
- `.deploy/secrets.production.env.example`: documented `API_WORKERS=2` with the reasoning, so a future from-scratch production setup doesn't silently regress to the single-worker default.
- **Applied live:** `/etc/systemd/system/camxora-api.service` on the production VPS edited in place (`--workers 1` → `--workers 2`), `systemctl daemon-reload` + `systemctl restart camxora-api.service`. Verified: 2 `uvicorn` worker processes running, local `/health` → 200 in ~0.6s, public `https://api.camxora.com/health` → 200 in ~0.36s, no errors in the post-restart journal (both workers ran their startup migration check cleanly).
- Live server headroom confirmed before making this change: 6 vCPU (only 1 ever used), 11GB RAM (249MB used), load average 0.3–0.4, Postgres `max_connections=100` (asyncpg pool is `min_size=2, max_size=10` per worker process, so 2 workers = up to 20 connections — well within budget). This is a low-risk change given the spare capacity.

No API contract, schema, or client-code changes — this is a deploy/ops-only fix.

## Files touched

- `scripts/deploy/camxora-production-remote.sh`
- `scripts/deploy/camxora-sandbox-remote.sh`
- `.deploy/secrets.production.env` (local only, not committed)
- `.deploy/secrets.production.env.example`
- `platform_api/CHANGELOG.md`
- Live: `/etc/systemd/system/camxora-api.service` on the production VPS (backed up to `camxora-api.service.bak-workers1` before editing).

## Migration / deploy

- No migration needed. No redeploy needed for this fix specifically — applied directly via systemd + confirmed with `.deploy/secrets.production.env` updated so the *next* full redeploy also carries `--workers 2` instead of reverting to 1.
- Sandbox (`.deploy/secrets.sandbox.env`) still has `API_WORKERS=1` explicitly set — not changed this round since the reported instability was against production. Same fix can be applied there on request.

## Tests

- No unit tests apply to this ops-only change. Verified live instead: `systemctl status camxora-api.service` (active, 2 uvicorn child processes), `curl http://127.0.0.1:8100/health` (200), `curl https://api.camxora.com/health` (200), `journalctl -u camxora-api.service` (clean startup, both workers completed their alembic migration check with no errors).

## Follow-ups

- **Structural fix (bigger effort, not done here):** build the `platform_worker` queue process from `docs/PRODUCTION_INFRASTRUCTURE_PLAN.md` so heavy jobs (image generation, Suno polling/streaming, YouTube uploads) run in a dedicated process instead of sharing uvicorn's event loop with auth/session HTTP traffic at all. 2 workers reduces the blast radius of this problem; it doesn't eliminate the underlying architecture gap.
- Both `platform_api` uvicorn workers independently run `alembic upgrade heads` on startup. This was already true before this change (unrelated to the worker-count bump) and completed cleanly on this restart, but with more workers there's more chance of two processes racing on a migration lock on a future deploy — worth checking alembic's lock behavior or gating migrations to run once (e.g. in the deploy script, before starting the service) rather than on every worker's app startup.
- Consider raising Postgres `max_connections` and/or lowering the asyncpg per-worker pool `max_size` if `API_WORKERS` is increased further later — current headroom (100 max, ~20 in use at 2 workers) is comfortable but not unlimited.
- Apply the same `API_WORKERS` fix to sandbox if/when sandbox stability becomes a concern (currently still `1` there).
