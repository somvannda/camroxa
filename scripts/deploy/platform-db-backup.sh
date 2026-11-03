#!/usr/bin/env bash
# Nightly logical backup of the CamXora platform Postgres database
# (`camxora_platform`: accounts, licences, subscriptions, billing, admin data).
#
# The musicapi backup covers `sunoapi` only; before this unit existed the
# platform DB had no scheduled backup at all, just one-off manual dumps taken
# before risky deploys.
#
# Dumps in PostgreSQL custom format (internally compressed, so `pg_restore
# --list` verifies the archive without a separate decompress), prunes snapshots
# older than BACKUP_RETENTION_DAYS, and exits non-zero on any failure so systemd
# records the unit as failed.
#
# Driven by camxora-platform-db-backup.timer (daily). Run standalone as the
# `camxora` user to test:  bash scripts/deploy/platform-db-backup.sh
#
# Env (read from platform_api/.env, or the environment when set):
#   PLATFORM_DATABASE_URL  postgresql+asyncpg://user:pass@host:port/camxora_platform
#   BACKUP_DIR             default /opt/camxora/backups/platform
#   BACKUP_RETENTION_DAYS  default 14
#
# ---------------------------------------------------------------------------
# Restore drill (run on the host; ALWAYS into a scratch DB, never
# `camxora_platform`):
#
#   LATEST="$(ls -1t /opt/camxora/backups/platform/camxora_platform-*.dump | head -n1)"
#   sudo -u postgres createdb camxora_platform_restore_check
#   sudo -u postgres pg_restore --no-owner --no-privileges --exit-on-error \
#     -d camxora_platform_restore_check "$LATEST"
#   sudo -u postgres psql -d camxora_platform_restore_check -c '\dt'
#   sudo -u postgres dropdb camxora_platform_restore_check
#
# The drill is green when pg_restore exits 0 and `\dt` lists the app tables.
# This is a nightly logical snapshot with BACKUP_RETENTION_DAYS history; there
# is no WAL archiving / point-in-time recovery.
# ---------------------------------------------------------------------------
set -euo pipefail

log() { echo "[platform-db-backup] $*"; }

BACKUP_DIR="${BACKUP_DIR:-/opt/camxora/backups/platform}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
ENV_FILE="${PLATFORM_ENV_FILE:-/opt/camxora/repo/platform_api/.env}"

if [[ -z "${PLATFORM_DATABASE_URL:-}" && -z "${DATABASE_URL:-}" && -f "${ENV_FILE}" ]]; then
  PLATFORM_DATABASE_URL="$(grep -E '^PLATFORM_DATABASE_URL=' "${ENV_FILE}" | tail -n1 | cut -d= -f2-)"
  if [[ -z "${PLATFORM_DATABASE_URL}" ]]; then
    DATABASE_URL="$(grep -E '^DATABASE_URL=' "${ENV_FILE}" | tail -n1 | cut -d= -f2-)"
  fi
fi
DB_URL="${PLATFORM_DATABASE_URL:-${DATABASE_URL:-}}"
DB_URL="${DB_URL%\"}"; DB_URL="${DB_URL#\"}"
DB_URL="${DB_URL%\'}"; DB_URL="${DB_URL#\'}"
DB_URL="${DB_URL/postgresql+asyncpg:\/\//postgresql://}"
[[ -n "${DB_URL}" ]] || { log "PLATFORM_DATABASE_URL not set (and ${ENV_FILE} has none)"; exit 1; }

command -v pg_dump >/dev/null 2>&1 || { log "pg_dump not found - install postgresql-client"; exit 1; }
command -v psql >/dev/null 2>&1 || { log "psql not found - install postgresql-client"; exit 1; }

mkdir -p "${BACKUP_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="${BACKUP_DIR}/camxora_platform-${STAMP}.dump"

# Exclude any table the connecting role cannot read so one stray scratch table
# cannot fail the whole dump.
EXCLUDES=()
if UNREADABLE="$(psql "${DB_URL}" -Atc "
  SELECT format('%I.%I', n.nspname, c.relname)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind IN ('r', 'p')
    AND n.nspname NOT IN ('pg_catalog', 'information_schema')
    AND NOT has_table_privilege(current_user, c.oid, 'SELECT')
  ORDER BY 1;" 2>/dev/null)"; then
  while IFS= read -r tbl; do
    [[ -n "${tbl}" ]] && EXCLUDES+=(--exclude-table="${tbl}")
  done <<< "${UNREADABLE}"
else
  log "WARN: could not list unreadable tables; dumping without exclusions"
fi
if (( ${#EXCLUDES[@]} > 0 )); then
  log "Skipping ${#EXCLUDES[@]} table(s) the app role cannot read"
fi

log "Dumping database -> ${TARGET}"
pg_dump --format=custom --compress=6 --no-owner --no-privileges \
  ${EXCLUDES[@]+"${EXCLUDES[@]}"} \
  --file="${TARGET}" "${DB_URL}"

# Verify the archive is readable before trusting it.
pg_restore --list "${TARGET}" >/dev/null
log "Backup OK ($(du -h "${TARGET}" | cut -f1))"

log "Pruning snapshots older than ${BACKUP_RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'camxora_platform-*.dump' \
  -mtime "+${BACKUP_RETENTION_DAYS}" -print -delete || true

log "Retained $(find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'camxora_platform-*.dump' | wc -l) snapshot(s) in ${BACKUP_DIR}"
