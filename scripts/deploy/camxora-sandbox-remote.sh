#!/usr/bin/env bash
# CamXora sandbox full-stack install (Ubuntu 22/24). Idempotent where practical.
set -euo pipefail

log() { echo "[camxora-deploy] $*"; }
need_root() { if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then log "Run as root (or via sudo)"; exit 1; fi; }
need_root

: "${GIT_REPO:?GIT_REPO required}"
: "${GIT_BRANCH:=main}"
: "${ADMIN_EMAIL:?ADMIN_EMAIL required}"
: "${CERTBOT_EMAIL:=${ADMIN_EMAIL}}"

API_WORKERS="${API_WORKERS:-4}"
DEPLOY_ROOT="/opt/camxora"
REPO_DIR="${DEPLOY_ROOT}/repo"
SECRETS_FILE="${DEPLOY_ROOT}/.deploy-secrets"
API_PORT=8100
WEBSITE_PORT=3100
PORTAL_PORT=3101
MUSIC_PORT=3102

gen_hex() { openssl rand -hex 32; }

if [[ -f "${SECRETS_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${SECRETS_FILE}"
fi

DB_PASSWORD="${DB_PASSWORD:-$(gen_hex)}"
PLATFORM_JWT_SECRET="${PLATFORM_JWT_SECRET:-$(gen_hex)}"
PLATFORM_ENCRYPTION_MASTER_KEY="${PLATFORM_ENCRYPTION_MASTER_KEY:-$(gen_hex)}"
PLATFORM_SUNO_CALLBACK_HMAC_SECRET="${PLATFORM_SUNO_CALLBACK_HMAC_SECRET:-$(gen_hex)}"

mkdir -p "${DEPLOY_ROOT}/backups"
chmod 755 "${DEPLOY_ROOT}"

cat >"${SECRETS_FILE}" <<EOF
# Generated $(date -u +%Y-%m-%dT%H:%M:%SZ) — keep private
DB_PASSWORD=${DB_PASSWORD}
PLATFORM_JWT_SECRET=${PLATFORM_JWT_SECRET}
PLATFORM_ENCRYPTION_MASTER_KEY=${PLATFORM_ENCRYPTION_MASTER_KEY}
PLATFORM_SUNO_CALLBACK_HMAC_SECRET=${PLATFORM_SUNO_CALLBACK_HMAC_SECRET}
# Shared secret for the music-web geo gate (X-Origin-Verify). Empty = gate off.
EDGE_VERIFY_SECRET=${EDGE_VERIFY_SECRET:-}
ADMIN_EMAIL=${ADMIN_EMAIL}
EOF
chmod 600 "${SECRETS_FILE}"
chown root:root "${SECRETS_FILE}" 2>/dev/null || true

log "Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl build-essential nginx certbot python3-certbot-nginx \
  postgresql postgresql-contrib redis-server ufw jq ca-certificates gnupg

if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]]; then
  log "Installing Node.js 20..."
  # Add the NodeSource repo via its signing key and verify packages against it,
  # instead of piping a remote setup script straight into bash.
  command -v gpg >/dev/null 2>&1 || apt-get install -y -qq gnupg
  install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | gpg --batch --yes --dearmor -o /etc/apt/keyrings/nodesource.gpg
  echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list
  apt-get update -qq
  apt-get install -y -qq nodejs
fi

PY=python3.11
if ! command -v "${PY}" >/dev/null 2>&1; then
  apt-get install -y -qq software-properties-common
  add-apt-repository -y ppa:deadsnakes/ppa || true
  apt-get update -qq
  apt-get install -y -qq python3.11 python3.11-venv python3.11-dev
fi

systemctl enable postgresql redis-server nginx
systemctl start postgresql redis-server nginx

log "PostgreSQL user/database..."
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='camxora'" | grep -q 1; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
CREATE USER camxora WITH PASSWORD '${DB_PASSWORD}';
SQL
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='camxora_platform'" | grep -q 1; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
CREATE DATABASE camxora_platform OWNER camxora;
GRANT ALL PRIVILEGES ON DATABASE camxora_platform TO camxora;
SQL
fi

if ! id camxora &>/dev/null; then
  adduser --disabled-password --gecos "" camxora
fi
usermod -aG www-data camxora 2>/dev/null || true
mkdir -p "${DEPLOY_ROOT}"
chown camxora:camxora "${DEPLOY_ROOT}"

CLONE_URL="${GIT_REPO}"
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  CLONE_URL="${GIT_REPO/https:\/\//https://${GITHUB_TOKEN}@}"
fi

if [[ "${SYNC_FROM_LOCAL:-}" == "1" ]]; then
  log "Extracting uploaded source tarball..."
  REPO_BACKUP=""
  if [[ -d "${REPO_DIR}" ]]; then
    REPO_BACKUP="${DEPLOY_ROOT}/repo.bak.$(date -u +%Y%m%dT%H%M%SZ)"
    log "Backing up previous checkout to ${REPO_BACKUP}..."
    mv "${REPO_DIR}" "${REPO_BACKUP}"
  fi
  mkdir -p "${REPO_DIR}"
  tar -xzf /tmp/camxora-src.tar.gz -C "${REPO_DIR}"
  # The musicapi core shares this checkout directory but is deployed by its own
  # script (scripts/deploy/camxora-musicapi-remote.sh); the platform tarball does
  # NOT contain it. Restore it from the backup so this deploy never removes it
  # out from under the running camxora-musicapi service — that breaks its
  # absolute node_modules paths (e.g. ffmpeg-static) and every generation fails
  # with audio_ingest_failed.
  if [[ -n "${REPO_BACKUP}" && -e "${REPO_BACKUP}/musicapi" && ! -e "${REPO_DIR}/musicapi" ]]; then
    log "Restoring musicapi checkout from ${REPO_BACKUP}..."
    mv "${REPO_BACKUP}/musicapi" "${REPO_DIR}/musicapi"
  fi
  chown -R camxora:camxora "${REPO_DIR}"
elif [[ ! -d "${REPO_DIR}/.git" ]]; then
  log "Cloning repository..."
  sudo -u camxora -H git clone --branch "${GIT_BRANCH}" "${CLONE_URL}" "${REPO_DIR}"
else
  log "Updating repository..."
  sudo -u camxora -H bash -lc "cd '${REPO_DIR}' && git fetch origin && git checkout '${GIT_BRANCH}' && git pull --ff-only origin '${GIT_BRANCH}'"
fi

log "Platform API venv + install..."
sudo -u camxora -H bash -lc "
  cd '${REPO_DIR}/platform_api'
  if [[ ! -d .venv ]]; then ${PY} -m venv .venv; fi
  source .venv/bin/activate
  pip install -U pip wheel -q
  pip install -e . -q
"

CORS='["https://sandbox.camxora.com","https://app.sandbox.camxora.com","https://admin.sandbox.camxora.com","https://music.sandbox.camxora.com"]'
sudo -u camxora tee "${REPO_DIR}/platform_api/.env" >/dev/null <<EOF
PLATFORM_ENVIRONMENT=staging
PLATFORM_DEBUG=false
PLATFORM_HOST=127.0.0.1
PLATFORM_PORT=${API_PORT}
PLATFORM_DATABASE_URL=postgresql+asyncpg://camxora:${DB_PASSWORD}@127.0.0.1:5432/camxora_platform
PLATFORM_REDIS_URL=redis://127.0.0.1:6379/1
PLATFORM_JWT_SECRET=${PLATFORM_JWT_SECRET}
PLATFORM_CORS_ORIGINS=${CORS}
PLATFORM_SUNO_CALLBACK_BASE_URL=https://api.sandbox.camxora.com
PLATFORM_SUNO_API_BASE_URL=https://musicapi.camxora.com
PLATFORM_SUNO_CALLBACK_HMAC_SECRET=${PLATFORM_SUNO_CALLBACK_HMAC_SECRET}
PLATFORM_MUSIC_WEB_TRUSTED_EDGE_SECRET=${EDGE_VERIFY_SECRET:-}
PLATFORM_CUTLUY_API_BASE_URL=https://cutluy.com
PLATFORM_CUTLUY_SECRET_KEY=${PLATFORM_CUTLUY_SECRET_KEY:-}
PLATFORM_CUTLUY_PAYMENT_LINK_ID=${PLATFORM_CUTLUY_PAYMENT_LINK_ID:-}
PLATFORM_CUTLUY_WEBHOOK_SECRET=${PLATFORM_CUTLUY_WEBHOOK_SECRET:-}
PLATFORM_ENCRYPTION_MASTER_KEY=${PLATFORM_ENCRYPTION_MASTER_KEY}
PLATFORM_SLAI_API_BASE_URL=https://api.slai.shop
# Transactional email (Resend SMTP relay).
PLATFORM_SMTP_HOST=${PLATFORM_SMTP_HOST:-}
PLATFORM_SMTP_PORT=${PLATFORM_SMTP_PORT:-587}
PLATFORM_SMTP_USER=${PLATFORM_SMTP_USER:-}
PLATFORM_SMTP_PASSWORD=${PLATFORM_SMTP_PASSWORD:-}
PLATFORM_SMTP_USE_TLS=${PLATFORM_SMTP_USE_TLS:-true}
PLATFORM_EMAIL_FROM_NAME=${PLATFORM_EMAIL_FROM_NAME:-Camxora}
PLATFORM_EMAIL_FROM_ADDRESS=${PLATFORM_EMAIL_FROM_ADDRESS:-noreply@camxora.com}
# Google sign-in for music web (same OAuth client as musicapi.camxora.com).
PLATFORM_GOOGLE_CLIENT_ID=${MUSICAPI_GOOGLE_CLIENT_ID:-${PLATFORM_GOOGLE_CLIENT_ID:-}}
PLATFORM_GOOGLE_CLIENT_SECRET=${MUSICAPI_GOOGLE_CLIENT_SECRET:-${PLATFORM_GOOGLE_CLIENT_SECRET:-}}
PLATFORM_GOOGLE_REDIRECT_URIS=${PLATFORM_GOOGLE_REDIRECT_URIS:-https://music.sandbox.camxora.com/auth/callback,http://localhost:3001/auth/callback}
PLATFORM_MUSIC_WEB_EMAIL_SIGNUP_ENABLED=${PLATFORM_MUSIC_WEB_EMAIL_SIGNUP_ENABLED:-true}
EOF
chmod 600 "${REPO_DIR}/platform_api/.env"
chown camxora:camxora "${REPO_DIR}/platform_api/.env"

log "Running migrations..."
sudo -u postgres psql camxora_platform -c \
  "ALTER TABLE IF EXISTS alembic_version ALTER COLUMN version_num TYPE VARCHAR(128);"
sudo -u camxora -H bash -lc "
  cd '${REPO_DIR}/platform_api'
  source .venv/bin/activate
  alembic upgrade head
"

log "Building admin portal..."
sudo -u camxora -H bash -lc "
  set -e
  cd '${REPO_DIR}/admin_portal'
  npm ci --no-audit --no-fund
  echo 'VITE_API_BASE_URL=' > .env.production
  npm run build
  chmod -R 755 dist
"

log "Building website..."
sudo -u camxora -H bash -lc "
  set -e
  cd '${REPO_DIR}/website'
  npm ci --no-audit --no-fund
  cat > .env.production <<ENVEOF
NEXT_PUBLIC_PLATFORM_API_BASE_URL=https://api.sandbox.camxora.com/api/v1
NEXT_PUBLIC_CAMXORA_ENV=sandbox
NEXT_PUBLIC_SITE_URL=https://sandbox.camxora.com
NEXT_PUBLIC_USER_PORTAL_URL=https://app.sandbox.camxora.com
ENVEOF
  npm run build
"

log "Building user portal..."
sudo -u camxora -H bash -lc "
  set -e
  cd '${REPO_DIR}/user_portal'
  npm ci --no-audit --no-fund
  cat > .env.production <<ENVEOF
NEXT_PUBLIC_PLATFORM_API_BASE_URL=https://api.sandbox.camxora.com/api/v1
NEXT_PUBLIC_CAMXORA_ENV=sandbox
NEXT_PUBLIC_WEBSITE_URL=https://sandbox.camxora.com
NEXT_PUBLIC_USER_PORTAL_URL=https://app.sandbox.camxora.com
ENVEOF
  npm run build
"

log "Building music web (public streaming)..."
sudo -u camxora -H bash -lc "
  set -e
  cd '${REPO_DIR}/music_web'
  npm ci --no-audit --no-fund
  cat > .env.production <<ENVEOF
NEXT_PUBLIC_API_BASE_URL=https://api.sandbox.camxora.com
ENVEOF
  npm run build
"

log "Installing systemd units..."
tee /etc/systemd/system/camxora-api.service >/dev/null <<UNIT
[Unit]
Description=CamXora Platform API
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
User=camxora
Group=camxora
WorkingDirectory=${REPO_DIR}
Environment=PYTHONPATH=${REPO_DIR}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=${REPO_DIR}/platform_api/.env
ExecStart=${REPO_DIR}/platform_api/.venv/bin/uvicorn platform_api.main:app \\
  --host 127.0.0.1 --port ${API_PORT} --workers ${API_WORKERS} \\
  --log-level info
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
UNIT

tee /etc/systemd/system/camxora-worker-draft@.service >/dev/null <<UNIT
[Unit]
Description=CamXora Job Worker (%i / draft stage)
After=network.target postgresql.service redis-server.service camxora-api.service
Wants=postgresql.service redis-server.service

[Service]
User=camxora
Group=camxora
WorkingDirectory=${REPO_DIR}
Environment=PYTHONPATH=${REPO_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=CAMXORA_WORKER_JOB_TYPES=draft
Environment=CAMXORA_WORKER_NAME=draft@%i
EnvironmentFile=${REPO_DIR}/platform_api/.env
ExecStart=${REPO_DIR}/platform_api/.venv/bin/python -m platform_api.worker
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
UNIT

tee /etc/systemd/system/camxora-worker-suno@.service >/dev/null <<UNIT
[Unit]
Description=CamXora Job Worker (%i / suno stage)
After=network.target postgresql.service redis-server.service camxora-api.service
Wants=postgresql.service redis-server.service

[Service]
User=camxora
Group=camxora
WorkingDirectory=${REPO_DIR}
Environment=PYTHONPATH=${REPO_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=CAMXORA_WORKER_JOB_TYPES=suno
Environment=CAMXORA_WORKER_NAME=suno@%i
EnvironmentFile=${REPO_DIR}/platform_api/.env
ExecStart=${REPO_DIR}/platform_api/.venv/bin/python -m platform_api.worker
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
UNIT

tee /etc/systemd/system/camxora-worker-images@.service >/dev/null <<UNIT
[Unit]
Description=CamXora Job Worker (%i / images stage)
After=network.target postgresql.service redis-server.service camxora-api.service
Wants=postgresql.service redis-server.service

[Service]
User=camxora
Group=camxora
WorkingDirectory=${REPO_DIR}
Environment=PYTHONPATH=${REPO_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=CAMXORA_WORKER_JOB_TYPES=images
Environment=CAMXORA_WORKER_NAME=images@%i
EnvironmentFile=${REPO_DIR}/platform_api/.env
ExecStart=${REPO_DIR}/platform_api/.venv/bin/python -m platform_api.worker
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
UNIT

# Legacy single worker (kept for rollback; prefer stage templates)
tee /etc/systemd/system/camxora-worker.service >/dev/null <<UNIT
[Unit]
Description=CamXora Platform Job Worker (all types)
After=network.target postgresql.service redis-server.service camxora-api.service
Wants=postgresql.service redis-server.service

[Service]
User=camxora
Group=camxora
WorkingDirectory=${REPO_DIR}
Environment=PYTHONPATH=${REPO_DIR}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=${REPO_DIR}/platform_api/.env
ExecStart=${REPO_DIR}/platform_api/.venv/bin/python -m platform_api.worker
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
UNIT

tee /etc/systemd/system/camxora-website.service >/dev/null <<UNIT
[Unit]
Description=CamXora Marketing Website
After=network.target

[Service]
User=camxora
Group=camxora
WorkingDirectory=${REPO_DIR}/website
Environment=NODE_ENV=production
Environment=PORT=${WEBSITE_PORT}
ExecStart=/usr/bin/npm run start -- -p ${WEBSITE_PORT} -H 127.0.0.1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

tee /etc/systemd/system/camxora-portal.service >/dev/null <<UNIT
[Unit]
Description=CamXora User Portal
After=network.target

[Service]
User=camxora
Group=camxora
WorkingDirectory=${REPO_DIR}/user_portal
Environment=NODE_ENV=production
Environment=PORT=${PORTAL_PORT}
Environment=PLATFORM_API_INTERNAL_URL=http://127.0.0.1:${API_PORT}/api/v1
Environment=TZ=Asia/Phnom_Penh
ExecStart=/usr/bin/npm run start -- -p ${PORTAL_PORT} -H 127.0.0.1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

tee /etc/systemd/system/camxora-music.service >/dev/null <<UNIT
[Unit]
Description=CamXora Music Streaming Web
After=network.target

[Service]
User=camxora
Group=camxora
WorkingDirectory=${REPO_DIR}/music_web
Environment=NODE_ENV=production
Environment=PORT=${MUSIC_PORT}
ExecStart=/usr/bin/npm run start -- -p ${MUSIC_PORT} -H 127.0.0.1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable camxora-api \
  camxora-worker-draft@{1..4} \
  camxora-worker-suno@{1..2} \
  camxora-worker-images@{1..2} \
  camxora-website camxora-portal camxora-music
systemctl disable camxora-worker 2>/dev/null || true
systemctl restart camxora-api camxora-website camxora-portal camxora-music

log "Configuring nginx..."
NGINX_SRC="${REPO_DIR}/../nginx-camxora-sandbox.conf"
if [[ -f /tmp/nginx-camxora-sandbox.conf ]]; then
  cp /tmp/nginx-camxora-sandbox.conf /etc/nginx/sites-available/camxora-sandbox
elif [[ -f "${REPO_DIR}/scripts/deploy/nginx-camxora-sandbox.conf" ]]; then
  cp "${REPO_DIR}/scripts/deploy/nginx-camxora-sandbox.conf" /etc/nginx/sites-available/camxora-sandbox
else
  log "WARN: nginx-camxora-sandbox.conf missing — using HTTP-only fallback"
  tee /etc/nginx/sites-available/camxora-sandbox >/dev/null <<'NGINX'
server {
    listen 80;
    server_name api.sandbox.camxora.com;

    location / {
        proxy_pass http://127.0.0.1:8100;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location /api/v1/ws {
        proxy_pass http://127.0.0.1:8100;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}

server {
    listen 80;
    server_name sandbox.camxora.com;

    location / {
        proxy_pass http://127.0.0.1:3100;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name app.sandbox.camxora.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location / {
        proxy_pass http://127.0.0.1:3101;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name admin.sandbox.camxora.com;

    root /opt/camxora/repo/admin_portal/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}

server {
    listen 80;
    server_name music.sandbox.camxora.com;

    location / {
        proxy_pass http://127.0.0.1:3102;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX
fi

ln -sf /etc/nginx/sites-available/camxora-sandbox /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

log "TLS via certbot (requires DNS A records pointing here)..."
if certbot certificates 2>/dev/null | grep -q api.sandbox.camxora.com; then
  certbot renew --quiet || true
else
  certbot --nginx \
    -d api.sandbox.camxora.com \
    -d sandbox.camxora.com \
    -d app.sandbox.camxora.com \
    -d admin.sandbox.camxora.com \
    --non-interactive --agree-tos -m "${CERTBOT_EMAIL}" --redirect || {
      log "WARN: certbot failed — check DNS (music.sandbox is optional). HTTP still works on port 80."
    }
# After adding music.sandbox.camxora.com DNS A record, run:
# certbot --nginx -d music.sandbox.camxora.com --expand --non-interactive
fi

log "Health checks..."
sleep 3
curl -sf "http://127.0.0.1:${API_PORT}/health" | head -c 200 || log "WARN: API health check failed"
systemctl is-active camxora-api camxora-website camxora-portal camxora-music nginx postgresql redis-server || true

log "Done."
log "Secrets saved: ${SECRETS_FILE}"
log "Next: register at https://app.sandbox.camxora.com then run:"
log "  sudo -u postgres psql camxora_platform -c \"UPDATE users SET role = 'admin' WHERE email = '${ADMIN_EMAIL}';\""
