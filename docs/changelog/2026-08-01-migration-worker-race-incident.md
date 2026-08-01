# Production incident: concurrent-worker migration race caused a ~30 minute 500 storm

**Date:** 2026-08-01
**Status:** fixed, deployed to sandbox and production

## Summary

Right after today's v1.0.9 production deploy (`platform_api` sync + `alembic upgrade
head`), the affected user's desktop app started getting `500 An unexpected error
occurred` on almost every authenticated endpoint (`/settings`, `/profiles`,
`/progress`, `/batches/preflight`, `/music/downloads/pending`, `/music/history`,
`/image-jobs/.../output`) for roughly 30 minutes. Root cause: `platform_api`'s
lifespan runs `alembic upgrade heads` on **every** worker process's startup, with
no coordination between workers. `API_WORKERS` was bumped from 1 to 2 earlier
today (separate fix, see `2026-08-01-production-api-single-worker-bottleneck.md`),
so this was the first production restart where two workers raced to run the same
migration DDL concurrently — confirmed directly in `journalctl` (both PIDs
running `Running upgrade 074_suno_audio_ids -> 075_distrokid_addon` at the exact
same timestamp). That DDL invalidated cached query plans on the other worker's
already-open connection-pool connections, causing widespread, sustained request
failures until connections eventually cycled or the process was restarted again.

A second, unrelated finding during investigation: the systemd service had no
`PYTHONUNBUFFERED=1`, so stdout was block-buffered — none of the error
tracebacks from this incident were visible in `journalctl` until the process was
restarted. This made the incident far harder to diagnose than it should have
been and is fixed here too.

## Product impact

**Before:** After any deploy with `API_WORKERS` > 1, users could see a burst of
500s across nearly every screen (Settings, Profiles, Progress, batch creation,
MP3/image downloads, history) for an extended window (~30 min observed), not a
brief blip. The desktop app's own resilience logic ("Pipeline helper paused",
"Auto-video paused", "API recovered — resuming...") mitigated it by pausing/
resuming automatically, but the user still saw sustained failures and reported
"we are slow / not stable" during this window.

**After:** Deploys that trigger `alembic upgrade heads` on multiple workers now
serialize automatically — the first worker runs the upgrade, the rest block on a
Postgres advisory lock and then run it themselves as a fast no-op (DB already at
head). No concurrent DDL, no poisoned connections.

## Technical impact

- `platform_api/migrations/runner.py`: `run_pending_migrations()` now opens a
  dedicated `asyncpg` connection, acquires `pg_advisory_lock(<fixed key>)` before
  calling `alembic upgrade heads`, and releases it (`pg_advisory_unlock`) in a
  `finally` block — even on failure. Session-level advisory lock also
  auto-releases if the process dies without a clean shutdown.
- Both `scripts/deploy/camxora-production-remote.sh` and
  `camxora-sandbox-remote.sh` (full-provision systemd unit templates) now include
  `Environment=PYTHONUNBUFFERED=1` so this can't regress on a future
  re-provision. Live production and sandbox `camxora-api.service` files were
  also patched directly and restarted.
- No schema change. No desktop change.

## Files touched

- `platform_api/migrations/runner.py` — advisory-lock guard around migrations.
- `platform_api/tests/test_migrations_runner.py` — new tests: lock acquired
  before / released after upgrade, lock still released if upgrade raises.
- `scripts/deploy/camxora-production-remote.sh`,
  `scripts/deploy/camxora-sandbox-remote.sh` — `PYTHONUNBUFFERED=1` in the
  templated systemd unit.

## Migration / deploy

- Deployed to **production**: synced `platform_api`, restarted `camxora-api`.
  Verified via live `journalctl` that two workers now acquire the advisory lock
  sequentially instead of running migrations concurrently. `/health` → 200,
  `alembic_version` = `079_image_job_storage_key`.
- Deployed to **sandbox**: synced `platform_api`, added `PYTHONUNBUFFERED=1` to
  the live service file, restarted. Sandbox runs `--workers 1` so it was never
  at risk of this specific race, but gets the same fix and unbuffered logging
  for consistency. `/health` → 200, `alembic_version` = `079_image_job_storage_key`,
  no advisory locks held (`pg_locks` clean).

## Incident details

- **Detection:** user-reported desktop log (`camxora-20260801 (3).log`) showing
  continuous `500` responses from ~21:24 to ~21:53 local time (UTC+7), i.e.
  16:24–16:53 CEST on the production host — which lines up exactly with the
  `systemctl restart camxora-api` from today's `sync_platform_api_production.py`
  run at 16:24:34 CEST.
- **Root cause confirmation:** `journalctl` showed both uvicorn worker PIDs
  (206279, 206280) executing the identical `alembic upgrade` step lines at the
  same second. Nginx access/error logs corroborated sustained `500`s (consistent
  175-byte JSON error bodies) for the affected account (`somvannda@gmail.com`)
  across many different endpoints, ruling out an endpoint-specific bug.
- **Reproduction:** direct in-process calls to `SettingsService.get_merged_settings`
  and `BatchRepository.list_pending_suno_downloads` for the affected user
  succeeded outside of HTTP context, and a minted JWT hitting the live endpoints
  post-fix returned correct `200`/`422` responses — confirming the bug was
  transient (tied to the poisoned-connection window), not a logic defect in
  the new v1.0.9 endpoints themselves.
- **Verification:** after deploying the advisory-lock fix and restarting
  production, `journalctl` showed the two workers now acquire
  `pg_advisory_lock` one after another (no more simultaneous DDL), and a live
  authenticated request against `/settings` succeeded normally.

## Tests

- `platform_api/tests/test_migrations_runner.py` — 2 new tests, both passing:
  advisory lock acquired before / released after a successful upgrade; lock
  still released if the upgrade raises.
- Live verification against production and sandbox (see above) — not part of
  the automated suite, documented here for audit purposes.

## Follow-ups

- Consider moving `alembic upgrade heads` out of the app's request-serving
  lifespan entirely and into the deploy script as a required pre-restart step
  (`run_alembic_upgrade_{sandbox,production}.py` already exist and are run
  today) — the advisory lock makes concurrent-worker startup safe, but a
  migration that takes a long time will still delay every worker's first
  request by however long the lock wait takes.
- The `platform_worker` queue process from `docs/PLATFORM_WORKERS_REQUIREMENTS.md`
  would remove background/heavy work from the same process pool entirely,
  reducing exposure to this whole class of startup-migration/worker-count
  interaction.
