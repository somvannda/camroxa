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
#   MUSICAPI_FRONTEND_ORIGINS, MUSICAPI_LOG_LEVEL
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
else
  MUSICAPI_DOMAIN="sandbox.camxora.com"
fi
API_HOST="musicapi.${MUSICAPI_DOMAIN}"
APP_HOST="app.musicapi.${MUSICAPI_DOMAIN}"
ADMIN_HOST="admin.musicapi.${MUSICAPI_DOMAIN}"

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

MUSICAPI_DB_PASSWORD="${MUSICAPI_DB_PASSWORD:-$(gen_hex 24)}"
MUSICAPI_JWT_SECRET="${MUSICAPI_JWT_SECRET:-$(gen_hex 48)}"
MUSICAPI_COOKIE_ENCRYPTION_KEY="${MUSICAPI_COOKIE_ENCRYPTION_KEY:-$(gen_hex 32)}"

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

log "Writing ${MUSICAPI_DIR}/.env..."
sudo -u camxora tee "${MUSICAPI_DIR}/.env" >/dev/null <<EOF
NODE_ENV=production
PORT=${MUSICAPI_PORT}
BACKEND_URL=http://127.0.0.1:${MUSICAPI_PORT}
DATABASE_URL=${DATABASE_URL}
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
GOOGLE_REDIRECT_URI_ADMIN=https://${ADMIN_HOST}/auth/callback
BAKONG_API_TOKEN=${MUSICAPI_BAKONG_API_TOKEN:-}
BAKONG_ACCOUNT_ID=${MUSICAPI_BAKONG_ACCOUNT_ID:-}
BAKONG_MERCHANT_NAME=${MUSICAPI_BAKONG_MERCHANT_NAME:-Camxora Music API}
BAKONG_MERCHANT_CITY=${MUSICAPI_BAKONG_MERCHANT_CITY:-Phnom Penh}
BAKONG_USE_SIT=${MUSICAPI_BAKONG_USE_SIT:-false}
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

for app in web-user web-admin; do
  log "Building ${app} (Next.js)..."
  sudo -u camxora -H bash -lc "
    set -e
    cd '${MUSICAPI_DIR}/${app}'
    npm ci --no-audit --no-fund || npm install --no-audit --no-fund
    echo 'BACKEND_URL=http://127.0.0.1:${MUSICAPI_PORT}' > .env.production
    npm run build
  "
done

log "Installing systemd units..."
REPO_DIR="${REPO_DIR}" bash "${REPO_DIR}/scripts/deploy/systemd/install_musicapi_services.sh"

log "Configuring nginx (${MUSICAPI_ENV})..."
NGINX_SRC="${REPO_DIR}/scripts/deploy/nginx-musicapi-${MUSICAPI_ENV}.conf"
NGINX_SITE="/etc/nginx/sites-available/musicapi-${MUSICAPI_ENV}"
NGINX_LINK="/etc/nginx/sites-enabled/musicapi-${MUSICAPI_ENV}"
CERT="/etc/letsencrypt/live/musicapi.${MUSICAPI_DOMAIN}/fullchain.pem"
[[ -f "${NGINX_SRC}" ]] || { log "Missing ${NGINX_SRC}"; exit 1; }

if [[ ! -f "${CERT}" && "${ISSUE_CERT:-0}" == "1" ]]; then
  log "Bootstrapping TLS for ${API_HOST} ${APP_HOST} ${ADMIN_HOST}..."
  BOOT_SITE="/etc/nginx/sites-available/musicapi-${MUSICAPI_ENV}-bootstrap"
  BOOT_LINK="/etc/nginx/sites-enabled/musicapi-${MUSICAPI_ENV}-bootstrap"
  cat >"${BOOT_SITE}" <<BOOT
server {
    listen 80;
    server_name ${API_HOST} ${APP_HOST} ${ADMIN_HOST};
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
  certbot --nginx -d "${API_HOST}" -d "${APP_HOST}" -d "${ADMIN_HOST}" \
    --expand --non-interactive --agree-tos --redirect "${CERTBOT_ARGS[@]}" || {
      log "WARN: certbot failed — check that A records for ${API_HOST}, ${APP_HOST}, ${ADMIN_HOST} point here."
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

log "Done."
log "Secrets saved: ${SECRETS_FILE}"
log "  API:   https://${API_HOST}/health"
log "  User:  https://${APP_HOST}"
log "  Admin: https://${ADMIN_HOST}"
echo "MUSICAPI_${MUSICAPI_ENV^^}_DEPLOYED"
