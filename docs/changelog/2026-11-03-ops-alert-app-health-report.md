# Ops Telegram: per-app downtime reporting, retired portal, backup restore

**Branch:** `fix/ops-app-health-report`
**Date:** 2026-11-03

## Why

Production looked like it kept going down, but the platform was healthy. Direct
checks from outside and from the VPS returned 200 for the website, music web,
admin console, platform API and music API. Three separate things produced the
false picture:

- **The user portal is retired, not broken.** `camxora-portal` was stopped and
  disabled on 2026-10-30 10:56 and its `app.camxora.com` nginx server block was
  removed, so the hostname falls to the default server and returns 404. The
  server-only `ops-alert.sh` still watched `camxora-portal` and paged
  "🔴 camxora-portal is inactive" **every 30 minutes** (state file rewritten at
  05:09 on 2026-11-03).
- **The nightly Music API backup had been failing since 2026-10-31.** The unit
  exited 127 because `/opt/camxora/repo/scripts/deploy/musicapi-backup.sh` was
  missing: it lives outside `DEPLOY_DIRS`, so the tarball deploy deleted it. The
  last good dump was 2026-11-01 08:23.
- **The 502s were deploy windows and provider timeouts.** 32 of 34 came from two
  API restarts on 2026-11-02 at 06:45:22 and 06:52:20 (desktop polling through
  nginx). The remaining ones were `POST /api/v3/web-music/generate` returning
  502 after a 27 s upstream timeout — a provider failure mapped by the API, not
  an outage.

## Changes

### `feat(ops): version the Telegram ops monitor and report every app`
- New `scripts/deploy/ops-alert.sh` (the old script existed only on the host at
  `/opt/camxora/bin/ops-alert.sh`).
- Monitors every app with **unit + public endpoint**: Website, Music web, Admin
  console, Platform API, Music API, Music API playground, Music API admin, plus
  PostgreSQL, Redis, Nginx and the nightly DB backup.
- Per-app `down_since` marker, so every page states the concrete issue and the
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

### `fix(deploy): stop tarball deploys deleting timer scripts`
- `DEPLOY_FILES` now includes `scripts/deploy/ops-alert.sh` and
  `scripts/deploy/musicapi-backup.sh`, the two files systemd runs by absolute
  path from outside `DEPLOY_DIRS`.
- `scripts/deploy/install_musicapi_backup_production.py` restores the backup
  script and runs one dump.

### `fix(nginx): redirect the retired user portal`
- `app.camxora.com` now answers `301 https://music.camxora.com/` instead of
  falling through to the default server and returning 404. HTTP is included in
  the port-80 redirect list. The existing `api.camxora.com` certificate already
  covers the hostname.

## Verification

- `bash -n scripts/deploy/ops-alert.sh` passes.
- Against a throwaway state dir on production: first failure stays quiet
  (streak 1), second failure pages the failed backup with its issue, and the
  recovery after the fix reports `back up after 56s`, then the next run is quiet.
- After the deploy, the monitor reports every app `🟢 up`.
- Backup: `sunoapi-20261103T052649Z.dump`, 103 MB, `pg_restore --list` verified
  by the script.
- `app.camxora.com` (HTTPS and HTTP, root and deep paths) returns 301 to
  `https://music.camxora.com/`; the other hosts still return 200.

## Follow-ups

- **`camxora_platform` (2.1 GB) has no scheduled backup** — only one-off manual
  dumps from Sep 22, Oct 4 and Oct 30. Needs its own timer.
- Backups are on the same VPS and unencrypted. Add an off-host copy to a private
  Backblaze B2 bucket/prefix and encrypt at rest.
