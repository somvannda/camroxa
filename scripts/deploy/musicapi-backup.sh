#!/usr/bin/env bash
# Nightly logical backup of the CamXora Music API Postgres database.
#
# Dumps the database in PostgreSQL custom format (internally compressed, so
# `pg_restore --list` can verify the archive without a separate decompress),
# prunes snapshots older than BACKUP_RETENTION_DAYS, and exits non-zero on any
# failure so systemd records the unit as failed.
#
# Driven by camxora-musicapi-backup.timer (daily). Run standalone as the
# `camxora` user to test:  bash scripts/deploy/musicapi-backup.sh
#
# Env (systemd feeds musicapi/.env via EnvironmentFile):
#   DATABASE_URL            postgres://user:pass@host:port/db
#   BACKUP_DIR              default /opt/camxora/backups/musicapi
#   BACKUP_RETENTION_DAYS   default 14
#
# ---------------------------------------------------------------------------
# Restore drill (run on the host; ALWAYS into a scratch DB, never `sunoapi`):
#
#   LATEST="$(ls -1t /opt/camxora/backups/musicapi/sunoapi-*.dump | head -n1)"
#   sudo -u postgres createdb sunoapi_restore_check
#   sudo -u postgres pg_restore --no-owner --no-privileges --exit-on-error \
#     -d sunoapi_restore_check "$LATEST"
#   sudo -u postgres psql -d sunoapi_restore_check -c '\dt'   # app tables listed
#   sudo -u postgres dropdb sunoapi_restore_check
#
# The drill is green when pg_restore exits 0 and `\dt` lists the app tables.
# This is a nightly logical snapshot with BACKUP_RETENTION_DAYS history; there
# is no WAL archiving / point-in-time recovery.
# ---------------------------------------------------------------------------
set -euo pipefail

log() { echo "[musicapi-backup] $*"; }

BACKUP_DIR="${BACKUP_DIR:-/opt/camxora/backups/musicapi}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
ENV_FILE="${MUSICAPI_ENV_FILE:-/opt/camxora/repo/musicapi/.env}"

# systemd supplies DATABASE_URL via EnvironmentFile; fall back to reading .env so
# the script also works when invoked by hand.
if [[ -z "${DATABASE_URL:-}" && -f "${ENV_FILE}" ]]; then
  DATABASE_URL="$(grep -E '^DATABASE_URL=' "${ENV_FILE}" | tail -n1 | cut -d= -f2-)"
fi
[[ -n "${DATABASE_URL:-}" ]] || { log "DATABASE_URL not set (and ${ENV_FILE} has none)"; exit 1; }

command -v pg_dump >/dev/null 2>&1 || { log "pg_dump not found - install postgresql-client"; exit 1; }

mkdir -p "${BACKUP_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="${BACKUP_DIR}/sunoapi-${STAMP}.dump"

log "Dumping database -> ${TARGET}"
pg_dump --format=custom --compress=6 --no-owner --no-privileges \
  --file="${TARGET}" "${DATABASE_URL}"

# Verify the archive is readable before trusting it.
pg_restore --list "${TARGET}" >/dev/null
log "Backup OK ($(du -h "${TARGET}" | cut -f1))"

log "Pruning snapshots older than ${BACKUP_RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'sunoapi-*.dump' \
  -mtime "+${BACKUP_RETENTION_DAYS}" -print -delete || true

log "Retained $(find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'sunoapi-*.dump' | wc -l) snapshot(s) in ${BACKUP_DIR}"
