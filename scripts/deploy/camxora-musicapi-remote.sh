#!/usr/bin/env bash
# CamXora musicapi remote installer (Ubuntu 22/24). Idempotent where practical.
#
# Installs the Suno core API + web-user + web-admin from an uploaded source
# tarball, then hands off to the versioned systemd units and nginx conf that
# ship with the same tarball. Driven by sync_musicapi_sandbox.py /
# deploy_musicapi_production.py over SSH; run standalone only for debugging.
#
# Required env:
#   MUSICAPI_ENV=sandbox|production   target environment (default: sandbox)
#   SYNC_FROM_LOCAL=1                 extract /tmp/musicapi-src.tar.gz -> /opt/camxora/repo
# Optional env (MUSICAPI_* — anything omitted is reused from
# /opt/camxora/.deploy-secrets, or generated on first deploy and persisted):
#   MUSICAPI_DB_PASSWORD, MUSICAPI_JWT_SECRET, MUSICAPI_COOKIE_ENCRYPTION_KEY,
#   MUSICAPI_SUNO_CLIENT_COOKIE, MUSICAPI_SUNO_COOKIE, MUSICAPI_SUNO_JWT,
#   MUSICAPI_SUNO_DEVICE_ID, MUSICAPI_SUNO_CAPTCHA_TOKEN, MUSICAPI_TWOCAPTCHA_KEY,
#   MUSICAPI_GOOGLE_CLIENT_ID, MUSICAPI_GOOGLE_CLIENT_SECRET,
#   MUSICAPI_BAKONG_API_TOKEN, MUSICAPI_BAKONG_ACCOUNT_ID,
#   MUSICAPI_FRONTEND_ORIGINS, MUSICAPI_LOG_LEVEL,
#   MUSICAPI_ALERT_TELEGRAM_BOT_TOKEN, MUSICAPI_ALERT_TELEGRAM_CHAT_ID
#     (health-alert bot; falls back to the platform's PLATFORM_TELEGRAM_* in
#      platform_api/.env when unset), MUSICAPI_BACKUP_DIR,
#   MUSICAPI_BACKUP_RETENTION_DAYS
#   ISSUE_CERT=1                      bootstrap Let's Encrypt on first deploy
set -euo pipefail

log() { echo "[musicapi-deploy] $*"; }
need_root() { if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then log "Run as root (or via sudo)"; exit 1; fi; }
need_root

MUSICAPI_ENV="${MUSICAPI_ENV:-sandbox}"
if [[ "${MUSICAPI_ENV}" != "sandbox" && "${MUSICAPI_ENV}" != "production" ]]; then
  log "MUSICAPI_ENV must be sandbox or production (got '${MUSICAPI_ENV}')"
  exit 1
fi

MUSICAPI_PORT=4003
WEB_USER_PORT=4001
WEB_ADMIN_PORT=4002
DEPLOY_ROOT="/opt/camxora"
REPO_DIR="${DEPLOY_ROOT}/repo"
MUSICAPI_DIR="${REPO_DIR}/musicapi"
SECRETS_FILE="${DEPLOY_ROOT}/.deploy-secrets"
DB_NAME="sunoapi"
DB_USER="musicapi"
TARBALL="/tmp/musicapi-src.tar.gz"

if [[ "${MUSICAPI_ENV}" == "production" ]]; then
  MUSICAPI_DOMAIN="camxora.com"
  # Production has no app.* host: the apex IS the user app portal + landing page,
  # and the core API is mounted by path (/backend, /v1, /api/v1, /payments).
  APP_HOST_PREFIX=""
else
  MUSICAPI_DOMAIN="sandbox.camxora.com"
  APP_HOST_PREFIX="app."
fi
API_HOST="musicapi.${MUSICAPI_DOMAIN}"
APP_HOST="${APP_HOST_PREFIX}musicapi.${MUSICAPI_DOMAIN}"
# Admin console host: the nested name (dot) in both environments. Production's is
# DNS-only (grey cloud) pointed straight at the origin, whose Let's Encrypt cert
# covers this name, so it does not need a one-level Cloudflare Universal SSL host.
ADMIN_HOST="admin.musicapi.${MUSICAPI_DOMAIN}"

# TLS/nginx host list, deduped (in production APP_HOST == API_HOST).
TLS_HOSTS=()
for _host in "${API_HOST}" "${APP_HOST}" "${ADMIN_HOST}"; do
  [[ " ${TLS_HOSTS[*]} " == *" ${_host} "* ]] || TLS_HOSTS+=("${_host}")
done

gen_hex() { openssl rand -hex "$1"; }

[[ -f "${TARBALL}" ]] || { log "Missing ${TARBALL} (upload the source tarball first)"; exit 1; }

# ---------------------------------------------------------------------------
# Generated secrets: driver value > previously persisted > fresh. Persisting
# keeps JWT sessions and encrypted Suno cookies valid across redeploys.
# ---------------------------------------------------------------------------
mkdir -p "${DEPLOY_ROOT}"
if [[ -f "${SECRETS_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${SECRETS_FILE}"
fi

COOKIE_KEY_GENERATED=0
MUSICAPI_DB_PASSWORD="${MUSICAPI_DB_PASSWORD:-$(gen_hex 24)}"
MUSICAPI_JWT_SECRET="${MUSICAPI_JWT_SECRET:-$(gen_hex 48)}"
if [[ -z "${MUSICAPI_COOKIE_ENCRYPTION_KEY:-}" ]]; then
  MUSICAPI_COOKIE_ENCRYPTION_KEY="$(gen_hex 32)"
  COOKIE_KEY_GENERATED=1
fi

# Keep a timestamped copy before rewriting: a regenerated cookie key is the only
# thing that can decrypt the stored Suno account cookies, so losing it is
# unrecoverable. Never overwrite without a rollback copy.
if [[ -f "${SECRETS_FILE}" ]]; then
  cp -p "${SECRETS_FILE}" "${SECRETS_FILE}.bak.$(date -u +%Y%m%dT%H%M%SZ)" 2>/dev/null || true
  # Keep the five most recent backups.
  ls -1t "${SECRETS_FILE}.bak."* 2>/dev/null | tail -n +6 | xargs -r rm -f 2>/dev/null || true
fi

{
  echo "# Generated $(date -u +%Y-%m-%dT%H:%M:%SZ) — keep private"
  echo "MUSICAPI_DB_PASSWORD=${MUSICAPI_DB_PASSWORD}"
  echo "MUSICAPI_JWT_SECRET=${MUSICAPI_JWT_SECRET}"
  echo "MUSICAPI_COOKIE_ENCRYPTION_KEY=${MUSICAPI_COOKIE_ENCRYPTION_KEY}"
} >"${SECRETS_FILE}.musicapi.tmp"
# Preserve any unrelated keys already in the shared secrets file.
if [[ -f "${SECRETS_FILE}" ]]; then
  grep -vE '^(#|MUSICAPI_DB_PASSWORD=|MUSICAPI_JWT_SECRET=|MUSICAPI_COOKIE_ENCRYPTION_KEY=)' \
    "${SECRETS_FILE}" >>"${SECRETS_FILE}.musicapi.tmp" || true
fi
mv "${SECRETS_FILE}.musicapi.tmp" "${SECRETS_FILE}"
chmod 600 "${SECRETS_FILE}"
chown root:root "${SECRETS_FILE}" 2>/dev/null || true

log "Installing/verifying system packages..."
export DEBIAN_FRONTEND=noninteractive
if ! command -v nginx >/dev/null 2>&1 || ! command -v psql >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq git curl build-essential nginx certbot python3-certbot-nginx \
    postgresql postgresql-contrib ca-certificates
fi
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]]; then
  log "Installing Node.js 20..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y -qq nodejs
fi
systemctl enable postgresql nginx >/dev/null 2>&1 || true
systemctl start postgresql nginx

if ! id camxora &>/dev/null; then
  adduser --disabled-password --gecos "" camxora
fi
usermod -aG www-data camxora 2>/dev/null || true
mkdir -p "${DEPLOY_ROOT}"
chown camxora:camxora "${DEPLOY_ROOT}"

log "PostgreSQL role/database..."
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 \
    -c "ALTER USER ${DB_USER} WITH PASSWORD '${MUSICAPI_DB_PASSWORD}';"
else
  sudo -u postgres psql -v ON_ERROR_STOP=1 \
    -c "CREATE USER ${DB_USER} WITH PASSWORD '${MUSICAPI_DB_PASSWORD}';"
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
fi
sudo -u postgres psql -v ON_ERROR_STOP=1 \
  -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
sudo -u postgres psql -d "${DB_NAME}" -v ON_ERROR_STOP=1 \
  -c "GRANT ALL ON SCHEMA public TO ${DB_USER};" 2>/dev/null || true

# Refuse to mint a fresh cookie key over existing encrypted Suno accounts. The
# new key cannot decrypt them, so the service would crash-loop on startup with
# "COOKIE_ENCRYPTION_KEY does not match the key these rows were encrypted with".
# Fail before writing .env / restarting and roll the secrets file back.
if [[ "${COOKIE_KEY_GENERATED}" == "1" ]] && command -v psql >/dev/null 2>&1; then
  existing_accounts="$(sudo -u postgres psql -d "${DB_NAME}" -tAc \
    "SELECT count(*) FROM suno_accounts WHERE COALESCE(client_cookie,'') <> ''" 2>/dev/null || true)"
  if [[ -n "${existing_accounts}" && "${existing_accounts}" != "0" ]]; then
    log "FATAL: ${DB_NAME}.suno_accounts has ${existing_accounts} encrypted account(s), but MUSICAPI_COOKIE_ENCRYPTION_KEY is absent from ${SECRETS_FILE}."
    log "A new key was generated and would make those cookies undecryptable."
    latest_backup="$(ls -1t "${SECRETS_FILE}.bak."* 2>/dev/null | head -n 1 || true)"
    if [[ -n "${latest_backup}" ]]; then
      cp -p "${latest_backup}" "${SECRETS_FILE}" || true
      log "Restored ${SECRETS_FILE} from ${latest_backup}; aborting before restart."
    fi
    log "Fix: add MUSICAPI_COOKIE_ENCRYPTION_KEY=<the key that encrypted them> to the deploy secrets (or re-run the Suno login flow), then redeploy."
    exit 1
  fi
fi

log "Extracting uploaded source tarball..."
mkdir -p "${REPO_DIR}"
# Replace the app tree wholesale (tar overwrites but never removes stale files),
# while scripts/deploy/ is extracted over the existing checkout in place so the
# platform's own deploy scripts are not wiped.
rm -rf "${MUSICAPI_DIR}"
tar -xzf "${TARBALL}" -C "${REPO_DIR}"
chown -R camxora:camxora "${REPO_DIR}"

DATABASE_URL="postgres://${DB_USER}:${MUSICAPI_DB_PASSWORD}@127.0.0.1:5432/${DB_NAME}"
MUSICAPI_FRONTEND_ORIGINS="${MUSICAPI_FRONTEND_ORIGINS:-https://${APP_HOST},https://${ADMIN_HOST}}"
MUSICAPI_LOG_LEVEL="${MUSICAPI_LOG_LEVEL:-info}"
MUSICAPI_ALERT_TELEGRAM_BOT_TOKEN="${MUSICAPI_ALERT_TELEGRAM_BOT_TOKEN:-}"
MUSICAPI_ALERT_TELEGRAM_CHAT_ID="${MUSICAPI_ALERT_TELEGRAM_CHAT_ID:-}"
BACKUP_DIR="${MUSICAPI_BACKUP_DIR:-/opt/camxora/backups/musicapi}"
BACKUP_RETENTION_DAYS="${MUSICAPI_BACKUP_RETENTION_DAYS:-14}"

log "Writing ${MUSICAPI_DIR}/.env..."
sudo -u camxora tee "${MUSICAPI_DIR}/.env" >/dev/null <<EOF
NODE_ENV=production
# Deployment target (sandbox|production). The runtime reads this to keep
# Telegram alert delivery production-only — sandbox shares the same alert
# bot/chat as production. Do not remove; see musicapi/src/config.ts.
MUSICAPI_ENV=${MUSICAPI_ENV}
PORT=${MUSICAPI_PORT}
BACKEND_URL=http://127.0.0.1:${MUSICAPI_PORT}
DATABASE_URL=${DATABASE_URL}
# Job transport. Default stays the in-memory driver; set
# MUSICAPI_QUEUE_DRIVER=redis so descriptor-backed jobs are re-queued across a
# restart instead of being failed out as "Interrupted by server restart."
# (which the failure-rate alert now ignores). Use a Redis DB index not used by
# platform_api.
QUEUE_DRIVER=${MUSICAPI_QUEUE_DRIVER:-memory}
REDIS_URL=${MUSICAPI_REDIS_URL:-redis://127.0.0.1:6379/2}
JWT_SECRET=${MUSICAPI_JWT_SECRET}
COOKIE_ENCRYPTION_KEY=${MUSICAPI_COOKIE_ENCRYPTION_KEY}
TRUST_PROXY=127.0.0.1
FRONTEND_ORIGINS=${MUSICAPI_FRONTEND_ORIGINS}
LOG_LEVEL=${MUSICAPI_LOG_LEVEL}
SUNO_CLIENT_COOKIE=${MUSICAPI_SUNO_CLIENT_COOKIE:-}
SUNO_COOKIE=${MUSICAPI_SUNO_COOKIE:-}
SUNO_JWT=${MUSICAPI_SUNO_JWT:-}
SUNO_DEVICE_ID=${MUSICAPI_SUNO_DEVICE_ID:-}
SUNO_CAPTCHA_TOKEN=${MUSICAPI_SUNO_CAPTCHA_TOKEN:-}
TWOCAPTCHA_KEY=${MUSICAPI_TWOCAPTCHA_KEY:-}
GOOGLE_CLIENT_ID=${MUSICAPI_GOOGLE_CLIENT_ID:-}
GOOGLE_CLIENT_SECRET=${MUSICAPI_GOOGLE_CLIENT_SECRET:-}
GOOGLE_REDIRECT_URI_USER=https://${APP_HOST}/auth/callback
BAKONG_API_TOKEN=${MUSICAPI_BAKONG_API_TOKEN:-}
BAKONG_ACCOUNT_ID=${MUSICAPI_BAKONG_ACCOUNT_ID:-}
BAKONG_MERCHANT_NAME=${MUSICAPI_BAKONG_MERCHANT_NAME:-Camxora Music API}
BAKONG_MERCHANT_CITY=${MUSICAPI_BAKONG_MERCHANT_CITY:-Phnom Penh}
BAKONG_USE_SIT=${MUSICAPI_BAKONG_USE_SIT:-false}
# ChmabaPay (task 3.7) hosted checkout. Emitted from the deploy secrets on every
# run because this file rewrites .env wholesale: without these lines a redeploy
# blanked the keys and checkout returned 503 until they were re-added by hand.
CHMABA_API_KEY=${MUSICAPI_CHMABA_API_KEY:-}
CHMABA_STORE_ID=${MUSICAPI_CHMABA_STORE_ID:-}
CHMABA_WEBHOOK_SECRET=${MUSICAPI_CHMABA_WEBHOOK_SECRET:-}
# Durable media storage (Backblaze B2 via S3). Reuses the platform's
# PLATFORM_STREAMING_B2_* secrets already present in this file; MUSICAPI_B2_*
# overrides let musicapi point at its own bucket/key later. Object keys are
# namespaced under MUSICAPI_B2_PREFIX so they never collide with platform ones.
MUSICAPI_B2_ENDPOINT=${MUSICAPI_B2_ENDPOINT:-${PLATFORM_STREAMING_B2_ENDPOINT:-}}
MUSICAPI_B2_REGION=${MUSICAPI_B2_REGION:-${PLATFORM_STREAMING_B2_REGION:-}}
MUSICAPI_B2_BUCKET=${MUSICAPI_B2_BUCKET:-${PLATFORM_STREAMING_B2_BUCKET:-}}
MUSICAPI_B2_KEY_ID=${MUSICAPI_B2_KEY_ID:-${PLATFORM_STREAMING_B2_KEY_ID:-}}
MUSICAPI_B2_APPLICATION_KEY=${MUSICAPI_B2_APPLICATION_KEY:-${PLATFORM_STREAMING_B2_APPLICATION_KEY:-}}
MUSICAPI_B2_PREFIX=${MUSICAPI_B2_PREFIX:-musicapi}
MUSICAPI_B2_PUBLIC_BASE_URL=${MUSICAPI_B2_PUBLIC_BASE_URL:-}
MUSICAPI_B2_URL_TTL_SECONDS=${MUSICAPI_B2_URL_TTL_SECONDS:-604800}
# Ops observability (task 4.6): health-alert bot + backup retention. The backup
# and healthcheck systemd units read these from this EnvironmentFile.
ALERT_TELEGRAM_BOT_TOKEN=${MUSICAPI_ALERT_TELEGRAM_BOT_TOKEN}
ALERT_TELEGRAM_CHAT_ID=${MUSICAPI_ALERT_TELEGRAM_CHAT_ID}
BACKUP_DIR=${BACKUP_DIR}
BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS}
EOF
chmod 600 "${MUSICAPI_DIR}/.env"
chown camxora:camxora "${MUSICAPI_DIR}/.env"

log "Building core API (tsc -> dist/)..."
sudo -u camxora -H bash -lc "
  set -e
  cd '${MUSICAPI_DIR}'
  npm ci --no-audit --no-fund || npm install --no-audit --no-fund
  npm run build
"

log "Applying database migrations..."
sudo -u camxora -H bash -lc "
  set -e
  cd '${MUSICAPI_DIR}'
  ./node_modules/.bin/tsx scripts/migrate.ts
"

if [[ "${MUSICAPI_SKIP_FRONTEND:-0}" == "1" ]]; then
  log "Skipping web-user/web-admin builds (MUSICAPI_SKIP_FRONTEND=1)."
else
  for app in web-user web-admin; do
    log "Building ${app} (Next.js)..."
    sudo -u camxora -H bash -lc "
      set -e
      cd '${MUSICAPI_DIR}/${app}'
      npm ci --no-audit --no-fund || npm install --no-audit --no-fund
      echo 'BACKEND_URL=http://127.0.0.1:${MUSICAPI_PORT}' > .env.production
      echo 'GOOGLE_SITE_VERIFICATION=${MUSICAPI_GOOGLE_SITE_VERIFICATION:-}' >> .env.production
      npm run build
    "
  done
fi

log "Preparing backup directory..."
mkdir -p "${BACKUP_DIR}"
chown camxora:camxora "${BACKUP_DIR}"

# MIDI microservice (Basic Pitch). Deploy server.py outside the repo tree so a
# redeploy's `rm -rf musicapi` never disturbs the running service; provision the
# venv only when missing (it is ~550MB).
log "Preparing MIDI microservice..."
install -d -o camxora -g camxora /opt/camxora/midi-service
install -m 644 "${MUSICAPI_DIR}/midi-service/server.py" /opt/camxora/midi-service/server.py
chown camxora:camxora /opt/camxora/midi-service/server.py
if [[ ! -x /opt/camxora/midi-service/.venv/bin/python ]]; then
  bash "${MUSICAPI_DIR}/midi-service/provision.sh" || log "WARN: MIDI provisioning failed"
fi

# LRC microservice (faster-whisper lyric alignment). Same pattern: server.py
# outside the repo tree, venv + model provisioned only when missing. The core
# API degrades to plain lyrics when it is absent, so this is best-effort.
log "Preparing LRC microservice..."
install -d -o camxora -g camxora /opt/camxora/lrc-service
install -m 644 "${MUSICAPI_DIR}/lrc-service/server.py" /opt/camxora/lrc-service/server.py
chown camxora:camxora /opt/camxora/lrc-service/server.py
if [[ ! -x /opt/camxora/lrc-service/.venv/bin/python ]]; then
  bash "${MUSICAPI_DIR}/lrc-service/provision.sh" || log "WARN: LRC provisioning failed"
fi

log "Installing systemd units..."
REPO_DIR="${REPO_DIR}" bash "${REPO_DIR}/scripts/deploy/systemd/install_musicapi_services.sh"

log "Running first DB backup + health probe (timers take over from here)..."
systemctl start camxora-musicapi-backup.service || log "WARN: initial backup failed"
systemctl start camxora-musicapi-healthcheck.service || log "WARN: health probe reported unhealthy"

log "Configuring nginx (${MUSICAPI_ENV})..."
NGINX_SRC="${REPO_DIR}/scripts/deploy/nginx-musicapi-${MUSICAPI_ENV}.conf"
NGINX_SITE="/etc/nginx/sites-available/musicapi-${MUSICAPI_ENV}"
NGINX_LINK="/etc/nginx/sites-enabled/musicapi-${MUSICAPI_ENV}"
CERT="/etc/letsencrypt/live/musicapi.${MUSICAPI_DOMAIN}/fullchain.pem"
[[ -f "${NGINX_SRC}" ]] || { log "Missing ${NGINX_SRC}"; exit 1; }

if [[ ! -f "${CERT}" && "${ISSUE_CERT:-0}" == "1" ]]; then
  log "Bootstrapping TLS for ${TLS_HOSTS[*]}..."
  BOOT_SITE="/etc/nginx/sites-available/musicapi-${MUSICAPI_ENV}-bootstrap"
  BOOT_LINK="/etc/nginx/sites-enabled/musicapi-${MUSICAPI_ENV}-bootstrap"
  cat >"${BOOT_SITE}" <<BOOT
server {
    listen 80;
    server_name ${TLS_HOSTS[*]};
    location / { return 404; }
}
BOOT
  ln -sf "${BOOT_SITE}" "${BOOT_LINK}"
  nginx -t && systemctl reload nginx
  if [[ -n "${CERTBOT_EMAIL:-}" ]]; then
    CERTBOT_ARGS=(-m "${CERTBOT_EMAIL}")
  else
    CERTBOT_ARGS=(--register-unsafely-without-email)
  fi
  CERTBOT_HOSTS=()
  for _host in "${TLS_HOSTS[@]}"; do CERTBOT_HOSTS+=(-d "${_host}"); done
  certbot --nginx "${CERTBOT_HOSTS[@]}" \
    --expand --non-interactive --agree-tos --redirect "${CERTBOT_ARGS[@]}" || {
      log "WARN: certbot failed — check that A records for ${TLS_HOSTS[*]} point here."
    }
  rm -f "${BOOT_LINK}" "${BOOT_SITE}"
fi

if [[ -f "${CERT}" ]]; then
  cp "${NGINX_SRC}" "${NGINX_SITE}"
  ln -sf "${NGINX_SITE}" "${NGINX_LINK}"
  nginx -t
  systemctl reload nginx
else
  log "WARN: no cert at ${CERT}; skipping HTTPS vhost (re-run with ISSUE_CERT=1 once DNS resolves)."
fi

log "Health checks..."
sleep 4
curl -sf "http://127.0.0.1:${MUSICAPI_PORT}/health" | head -c 200 || log "WARN: core /health failed"
curl -sf -o /dev/null "http://127.0.0.1:${WEB_USER_PORT}/" || log "WARN: web-user did not answer"
curl -sf -o /dev/null "http://127.0.0.1:${WEB_ADMIN_PORT}/" || log "WARN: web-admin did not answer"
systemctl is-active camxora-musicapi camxora-musicapi-web-user camxora-musicapi-web-admin nginx postgresql || true
systemctl list-timers camxora-musicapi-backup.timer camxora-musicapi-healthcheck.timer --no-pager || true
ls -lh "${BACKUP_DIR}" || true

log "Done."
log "Secrets saved: ${SECRETS_FILE}"
log "  API:   https://${API_HOST}/health"
log "  User:  https://${APP_HOST}"
log "  Admin: https://${ADMIN_HOST}"
echo "MUSICAPI_${MUSICAPI_ENV^^}_DEPLOYED"
