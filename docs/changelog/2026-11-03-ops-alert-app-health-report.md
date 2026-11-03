# Ops Telegram: per-app downtime reporting, retired portal, backups

**Branch:** `fix/ops-app-health-report`
**Date:** 2026-11-03

## Why

Production looked like it kept going down, but the platform was healthy. Direct
checks from outside and from the VPS returned 200 for the website, music web,
admin console, platform API and music API. Three separate things produced the
false picture:

- **The user portal is retired, not broken.** `camxora-portal` was stopped and
  disabled on 2026-10-30 10:56 and its `app.camxora.com` nginx server block was
  removed, so the hostname fell through to the default server and returned 404.
  The server-only `ops-alert.sh` still watched `camxora-portal` and paged
  "🔴 camxora-portal is inactive" **every 30 minutes**.
- **The nightly Music API backup had been failing since 2026-10-31.** The unit
  exited 127 because `/opt/camxora/repo/scripts/deploy/musicapi-backup.sh` was
  missing: it lives outside `DEPLOY_DIRS`, so the tarball deploy deleted it. The
  last good dump was 2026-11-01 08:23.
- **The 502s were deploy windows and provider timeouts.** 32 of 34 came from two
  API restarts on 2026-11-02 at 06:45:22 and 06:52:20 (desktop polling through
  nginx). The rest were `POST /api/v3/web-music/generate` returning 502 after a
  27 s upstream timeout — a provider failure mapped by the API, not an outage.

## Changes

### `feat(ops): report every app's downtime and issue to Telegram`
- New `scripts/deploy/ops-alert.sh` (the old script existed only on the host at
  `/opt/camxora/bin/ops-alert.sh`).
- Monitors every app with **unit + public endpoint**: Website, Music web, Admin
  console, Platform API, Music API, Music API playground, Music API admin, plus
  PostgreSQL, Redis, Nginx and both nightly backups and the off-host copy.
- Per-app `down_since` marker: every page states the concrete issue and the
  downtime, e.g. `Music web — down 1h 12m / issue: service inactive (failed);
  HTTP 502`.
- One consolidated DOWN message instead of one per check; hourly re-alert with a
  fresh duration; recovery message with the total downtime.
- Daily 09:00 Asia/Phnom_Penh all-app status with 24h downtime and last issue.
- Host checks retained (RAM, swap, disk, OOM, `camxora-api` memory).
- Production-only delivery, HTML escaping, and `parse_mode=HTML` (the old script
  sent literal `<b>` tags because it never set a parse mode).
- **`camxora-portal` / `app.camxora.com` removed** from monitoring.

### `feat(ops): install the monitor from the repo`
- `scripts/deploy/systemd/ops-alert.service` + `.timer` (5-minute cadence).
- `scripts/deploy/install_ops_alert_production.py`: uploads to `/tmp`, `bash -n`,
  installs by rename, removes the legacy host-only script, drops the stale
  portal state file, restarts the timer, prints the status.

### `fix(deploy): stop deploys deleting timer scripts`
- `DEPLOY_FILES` now includes `ops-alert.sh`, `musicapi-backup.sh`,
  `platform-db-backup.sh` and `backup-offhost.py` — the files systemd runs by
  absolute path from outside `DEPLOY_DIRS`.
- `scripts/deploy/install_musicapi_backup_production.py` restores the backup
  script and runs one dump.

### `fix(nginx): redirect the retired user portal`
- `app.camxora.com` now answers `301 https://music.camxora.com/` instead of
  falling through to the default server and returning 404. HTTP is included in
  the port-80 redirect list. The existing `api.camxora.com` certificate already
  covers the hostname.

### `feat(backup): nightly platform database backup`
- New `scripts/deploy/platform-db-backup.sh`: `pg_dump` of `camxora_platform`
  (2.1 GB) in custom format, archive verified with `pg_restore --list`, 14-day
  retention under `/opt/camxora/backups/platform`.
- `camxora-platform-db-backup.service` + `.timer` (daily 04:00, persistent,
  randomized 5 min).
- `scripts/deploy/install_platform_db_backup_production.py`.
- Both backup checks include **freshness**: the newest dump being older than 26h
  (or missing) is reported even when the unit is not marked failed, which
  catches a disabled timer or a deploy that removed the script.
- Restore-drill docs in both backup scripts now copy the archive to a
  postgres-readable path first (the platform backup dir is `0750
  camxora:camxora`, so `sudo -u postgres pg_restore` cannot traverse it).

### `feat(backup): off-host copy in a private B2 bucket`
- New `scripts/deploy/backup-offhost.py`: uploads the newest `sunoapi-*` and
  `camxora_platform-*` dumps to the private `camxora-db-backup` bucket with
  SSE-B2, skips objects already present with the same size, prunes remote
  copies older than 14 days, and writes `/var/lib/camxora-ops-alert/offhost.last`.
- Credential lives in `/opt/camxora/.backup-b2.env` (root 600) and is scoped to
  that bucket only (`listFiles`, `readFiles`, `writeFiles`, `deleteFiles`).
- `camxora-backup-offhost.service` + `.timer` (05:00, persistent).
- `ops-alert.sh` reports `Off-host backup` when the unit fails or the marker is
  older than 26h.

## Verification

- `bash -n scripts/deploy/ops-alert.sh` passes.
- Against a throwaway state dir on production: first failure stays quiet
  (streak 1), second failure pages the failed backup with its issue, and the
  recovery after the fix reports `back up after 56s`, then the next run is quiet.
- Live monitor status: all apps `🟢 up`.
- `app.camxora.com` (HTTPS and HTTP, root and deep paths) returns 301 to
  `https://music.camxora.com/`; the other hosts still return 200.
- **Restore drill passed** for both backups into scratch databases:
  - `camxora_platform-20261103T054458Z.dump` (222 MB) → 114 public tables,
    250 users, 25 `billing_payments`, `alembic_version` 178.
  - `sunoapi-20261103T052649Z.dump` (103 MB) → 28 public tables, 35 users.
  - Both scratch databases were dropped afterwards.
- **Off-host upload verified**: both objects landed in `camxora-db-backup` with
  SSE-B2, and their B2 `contentSha1` matches the local `sha1sum` exactly.

## Follow-ups

- Escrow the backup key outside the VPS; if the host dies, the on-host env file
  dies with it. The key shared during setup should be rotated once the pipeline
  is confirmed, then the new value written to `/opt/camxora/.backup-b2.env`.
- The old `repo-20260922-134107.tgz` (12.6 GB) was deleted from
  `/opt/camxora/backups`; disk went from 51% to 45% used.
- Production code ships one commit of `origin/main` through
  `build_source_bundle()`; the bootstrap installers in this branch are for
  units/secrets only and must not be used to hotfix deployed scripts.
