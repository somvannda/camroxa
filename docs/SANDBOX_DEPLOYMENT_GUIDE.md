# CamXora Sandbox Deployment Guide (Ubuntu 22/24)

**Target:** Shared VPS (4 vCPU, 8 GB RAM, 150 GB SSD) already running **botifyr.xyz**  
**Goal:** Run CamXora in **staging/sandbox** mode with **real CutLuy** payments, everything else dev/staging-safe  
**Domain:** `camxora.com` — use **subdomains** first (do not move production apex until stable)

**Companion docs:** [`PLATFORM_GAPS_AND_RECOMMENDATIONS.md`](./PLATFORM_GAPS_AND_RECOMMENDATIONS.md), [`DEPLOYMENT_OPERATIONS.md`](./DEPLOYMENT_OPERATIONS.md) (nginx timeouts, AI routing, post-deploy checks)

---

## 1. Recommended sandbox URLs

| Service | URL | Internal port |
|---------|-----|---------------|
| Marketing site | `https://sandbox.camxora.com` | 3100 |
| User portal | `https://app.sandbox.camxora.com` | 3101 |
| Admin portal | `https://admin.sandbox.camxora.com` | static files |
| Platform API | `https://api.sandbox.camxora.com` | 8100 |

Ports **8100 / 3100 / 3101** avoid clashing with typical botifyr stacks (often 80/443/3000/8000). Adjust if your VPS already uses these.

**DNS (at your registrar / Cloudflare):**

```
A    sandbox.camxora.com        → YOUR_VPS_IP
A    app.sandbox.camxora.com    → YOUR_VPS_IP
A    admin.sandbox.camxora.com  → YOUR_VPS_IP
A    api.sandbox.camxora.com    → YOUR_VPS_IP
```

---

## 2. Server prerequisites

SSH into the VPS as a sudo user.

### 2.1 System packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential nginx certbot python3-certbot-nginx \
  postgresql postgresql-contrib redis-server ufw
```

### 2.2 Node.js 20 LTS

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node -v   # v20.x
npm -v
```

### 2.3 Python 3.11+

Ubuntu 22.04 may need deadsnakes:

```bash
sudo apt install -y python3.11 python3.11-venv python3.11-dev
python3.11 --version
```

Ubuntu 24.04: `sudo apt install -y python3.11 python3.11-venv` (or default python3 if ≥3.11).

### 2.4 Firewall (adjust if botifyr already configured UFW)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

---

## 3. PostgreSQL & Redis (CamXora-isolated)

Use a **separate database** from botifyr.

```bash
sudo -u postgres psql <<'SQL'
CREATE USER camxora WITH PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
CREATE DATABASE camxora_platform OWNER camxora;
GRANT ALL PRIVILEGES ON DATABASE camxora_platform TO camxora;
SQL
```

Redis: use **database index 1** (botifyr often uses 0):

```bash
sudo systemctl enable redis-server postgresql
sudo systemctl start redis-server postgresql
redis-cli ping   # PONG
```

---

## 4. Deploy application code

### 4.1 Create deploy user & directory

```bash
sudo adduser --disabled-password --gecos "" camxora
sudo usermod -aG www-data camxora
sudo mkdir -p /opt/camxora
sudo chown camxora:camxora /opt/camxora
```

### 4.2 Clone repository

```bash
sudo -u camxora -H bash -lc '
  cd /opt/camxora
  git clone https://github.com/YOUR_ORG/MusicGenerator.git repo
  cd repo
  git checkout cursor/channel-pricing-and-plan-tiers
'
```

Replace branch/URL with your actual remote.

---

## 5. Platform API setup

### 5.1 Python virtualenv & install

```bash
sudo -u camxora -H bash -lc '
  cd /opt/camxora/repo/platform_api
  python3.11 -m venv .venv
  source .venv/bin/activate
  pip install -U pip wheel
  pip install -e ".[dev]"
'
```

### 5.2 Environment file

```bash
sudo -u camxora -H nano /opt/camxora/repo/platform_api/.env
```

```bash
# --- Core ---
PLATFORM_ENVIRONMENT=staging
PLATFORM_DEBUG=false
PLATFORM_HOST=127.0.0.1
PLATFORM_PORT=8100

# --- Database ---
PLATFORM_DATABASE_URL=postgresql+asyncpg://camxora:CHANGE_ME_STRONG_PASSWORD@127.0.0.1:5432/camxora_platform

# --- Redis (DB index 1) ---
PLATFORM_REDIS_URL=redis://127.0.0.1:6379/1

# --- Auth (generate: openssl rand -hex 32) ---
PLATFORM_JWT_SECRET=PASTE_64_CHAR_HEX_HERE

# --- CORS (sandbox origins) ---
PLATFORM_CORS_ORIGINS=["https://sandbox.camxora.com","https://app.sandbox.camxora.com","https://admin.sandbox.camxora.com"]

# --- Public callbacks ---
PLATFORM_SUNO_CALLBACK_BASE_URL=https://api.sandbox.camxora.com
PLATFORM_SUNO_CALLBACK_HMAC_SECRET=PASTE_SUNO_HMAC_SECRET

# --- CutLuy (PRODUCTION keys — real micro-payments) ---
PLATFORM_CUTLUY_API_BASE_URL=https://cutluy.com
PLATFORM_CUTLUY_SECRET_KEY=ck_live_YOUR_KEY
PLATFORM_CUTLUY_PAYMENT_LINK_ID=YOUR_PAYMENT_LINK_ID
PLATFORM_CUTLUY_WEBHOOK_SECRET=whsec_YOUR_WEBHOOK_SECRET

# --- AI providers (staging keys / budgets) ---
# Suno generation goes through Camxora's own musicapi, which talks to the Suno
# interface directly. Keep this on our own host; the Key Pool base_url override
# exists only as an emergency escape hatch.
PLATFORM_SUNO_API_BASE_URL=https://musicapi.camxora.com
# Add musicapi keys via Admin → API Key Pool (provider "suno") after first login

PLATFORM_DEEPSEEK_API_BASE_URL=https://api.deepseek.com
PLATFORM_SLAI_API_BASE_URL=https://your-slai-endpoint
PLATFORM_FAL_API_BASE_URL=https://fal.run

# --- Email (optional for sandbox) ---
PLATFORM_SMTP_HOST=smtp.yourprovider.com
PLATFORM_SMTP_PORT=587
PLATFORM_SMTP_USER=noreply@camxora.com
PLATFORM_SMTP_PASSWORD=...
PLATFORM_SMTP_USE_TLS=true
PLATFORM_EMAIL_FROM_ADDRESS=noreply@camxora.com

# --- Encryption for API key pool (openssl rand -hex 32) ---
PLATFORM_ENCRYPTION_MASTER_KEY=PASTE_64_CHAR_HEX_HERE
```

Lock permissions:

```bash
chmod 600 /opt/camxora/repo/platform_api/.env
```

### 5.3 Run migrations

```bash
sudo -u camxora -H bash -lc '
  cd /opt/camxora/repo/platform_api
  source .venv/bin/activate
  alembic upgrade head
'
```

Confirm revision includes **056_license_pending_plan_change** (and **055**).

### 5.4 systemd service

```bash
sudo tee /etc/systemd/system/camxora-api.service <<'UNIT'
[Unit]
Description=CamXora Platform API
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
User=camxora
Group=camxora
WorkingDirectory=/opt/camxora/repo/platform_api
EnvironmentFile=/opt/camxora/repo/platform_api/.env
ExecStart=/opt/camxora/repo/platform_api/.venv/bin/uvicorn platform_api.main:app \
  --host 127.0.0.1 --port 8100 --workers 2 \
  --log-config platform_api/log_config.json --log-level info
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable camxora-api
sudo systemctl start camxora-api
sudo systemctl status camxora-api
curl -s http://127.0.0.1:8100/health | jq .
```

If **8 GB RAM** is tight with botifyr, reduce to `--workers 1`.

---

## 6. Admin portal (static build)

### 6.1 Build

```bash
sudo -u camxora -H bash -lc '
  cd /opt/camxora/repo/admin_portal
  npm ci
  echo "VITE_API_BASE_URL=https://api.sandbox.camxora.com" > .env.production
  npm run build
'
```

Output: `/opt/camxora/repo/admin_portal/dist`

For sandbox admin, nginx serves static files directly (no Vite dev server in production).

---

## 7. Website & user portal (Next.js)

### 7.1 Website

```bash
sudo -u camxora -H bash -lc '
  cd /opt/camxora/repo/website
  npm ci
  cat > .env.production <<EOF
NEXT_PUBLIC_PLATFORM_API_BASE_URL=https://api.sandbox.camxora.com/api/v1
EOF
  npm run build
'
```

### 7.2 User portal

```bash
sudo -u camxora -H bash -lc '
  cd /opt/camxora/repo/user_portal
  npm ci
  cat > .env.production <<EOF
NEXT_PUBLIC_PLATFORM_API_BASE_URL=https://api.sandbox.camxora.com/api/v1
NEXT_PUBLIC_MARKETING_BASE_URL=https://sandbox.camxora.com
EOF
  npm run build
'
```

### 7.3 systemd services (Next.js production mode)

**Website — port 3100**

```bash
sudo tee /etc/systemd/system/camxora-website.service <<'UNIT'
[Unit]
Description=CamXora Marketing Website
After=network.target

[Service]
User=camxora
Group=camxora
WorkingDirectory=/opt/camxora/repo/website
Environment=NODE_ENV=production
Environment=PORT=3100
ExecStart=/usr/bin/npm run start -- -p 3100 -H 127.0.0.1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
```

**User portal — port 3101**

```bash
sudo tee /etc/systemd/system/camxora-portal.service <<'UNIT'
[Unit]
Description=CamXora User Portal
After=network.target

[Service]
User=camxora
Group=camxora
WorkingDirectory=/opt/camxora/repo/user_portal
Environment=NODE_ENV=production
Environment=PORT=3101
ExecStart=/usr/bin/npm run start -- -p 3101 -H 127.0.0.1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable camxora-website camxora-portal
sudo systemctl start camxora-website camxora-portal
```

---

## 8. Nginx reverse proxy

Create CamXora config **alongside** existing botifyr nginx sites (do not overwrite botifyr).

**Source of truth:** `scripts/deploy/nginx-camxora-sandbox.conf` in the repo.

Apply after any edit:

```bash
python scripts/deploy/apply_nginx.py --env sandbox
python scripts/deploy/verify_nginx_api_timeouts.py --env sandbox
```

### 8.1 Required API proxy timeouts

Every nginx location that proxies to `platform_api` (port **8100**) **must** set:

```nginx
proxy_connect_timeout 300s;
proxy_send_timeout 300s;
proxy_read_timeout 300s;
```

Image generation during onboarding (`/api/v1/channel-setup/generate-logo`, `generate-cover`) often takes **60–180+ seconds**. Nginx’s default **60s** `proxy_read_timeout` causes **504 Gateway Timeout** in the browser while the API still returns **200** and the admin audit log shows **success**.

See [`DEPLOYMENT_OPERATIONS.md`](./DEPLOYMENT_OPERATIONS.md) §2 and §4 for the full incident write-up.

### 8.2 User portal same-origin API

`app.sandbox.camxora.com` proxies `/api/` to the platform API so the portal uses same-origin cookies:

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8100;
    # ... standard headers ...
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
}
```

### 8.3 TLS (Let's Encrypt)

```bash
sudo certbot --nginx \
  -d api.sandbox.camxora.com \
  -d sandbox.camxora.com \
  -d app.sandbox.camxora.com \
  -d admin.sandbox.camxora.com
```

Certbot updates nginx to HTTPS automatically.

---

## 9. CutLuy webhook (production)

In [CutLuy Dashboard](https://cutluy.com) → Webhooks:

| Setting | Value |
|---------|-------|
| URL | `https://api.sandbox.camxora.com/api/v3/webhooks/cutluy` (music) or `https://api.sandbox.camxora.com/api/v3/billing/webhooks/cutluy` (desktop billing) |
| Events | Payment completed / failed (as offered) |
| Secret | Copy to `PLATFORM_CUTLUY_WEBHOOK_SECRET` |

Restart API after updating env:

```bash
sudo systemctl restart camxora-api
```

**Test:** Create a plan payment in user portal for minimum amount; confirm webhook fulfills license in Admin → Subscriptions.

---

## 10. Suno callback

Configure Suno provider dashboard (or your proxy) to send callbacks to:

```
https://api.sandbox.camxora.com/api/v1/callbacks/suno
```

Set `PLATFORM_SUNO_CALLBACK_HMAC_SECRET` to match Suno signing config.

---

## 11. First-time bootstrap (Admin)

1. Open `https://app.sandbox.camxora.com` → register first user  
2. Promote to admin in PostgreSQL (one-time):

```bash
sudo -u postgres psql camxora_platform -c \
  "UPDATE users SET role = 'admin' WHERE email = 'you@example.com';"
```

3. Open `https://admin.sandbox.camxora.com` → login  
4. **Plans:** Create subscription rows (2/6/10 ch × 30/180/365 days) + `profile_addon` rows  
5. **Billing term discounts:** Save % → click **Sync 6-month & annual prices**  
6. **API Key Pool:** Add Suno / LLM / image keys  
7. **Settings → CutLuy:** Verify keys if not using env-only  
8. Create test subscription or run CutLuy checkout from user portal  

---

## 12. Desktop client (`camxora_python`) — sandbox installer

**Policy:** End users must **not** switch API URLs in Settings. Each release artifact bakes in one environment via build-time env (see `camxora_python/.env.sandbox.example`).

### 12.1 Build sandbox desktop installer

On your build machine (Windows):

```powershell
cd camxora_python
.\scripts\build-desktop.ps1 -Environment sandbox
```

This copies `.env.sandbox.example` → `.env.sandbox` if missing, bakes env into the PyInstaller bundle, and outputs `dist/Camxora/Camxora.exe`. See also [DESKTOP_RELEASE.md](./DESKTOP_RELEASE.md).

Ship the entire `dist/Camxora/` folder to testers. It always talks to `api.sandbox.camxora.com`. Footer shows **Sandbox API** (hidden on production builds).

### 12.2 Production desktop (later — separate artifact)

When going live, build a **second** installer with `.env.production.example` values:

```
CAMXORA_BUILD_ENV=production
CAMXORA_API_BASE_URL=https://api.camxora.com/api/v1
CAMXORA_PORTAL_BASE_URL=https://app.camxora.com
```

Never publish one installer that toggles sandbox ↔ production at runtime.

### 12.3 Desktop vs portal responsibilities

| Task | Where |
|------|--------|
| Register / login | Desktop or portal |
| Plan purchase / add-ons | **Portal only** (`app.sandbox.camxora.com`) |
| Channel onboarding (logos, covers) | **Portal only** |
| Create new profiles | **Portal only** |
| Edit existing profile settings | Desktop Settings (existing profiles) |
| Batch generate / upload | Desktop |

WebSocket base derives from the baked-in API URL. No desktop install on VPS required.

---

## 13. Resource budget (8 GB RAM + botifyr)

| Service | Est. RAM |
|---------|----------|
| botifyr (existing) | ~1–2 GB |
| PostgreSQL | ~1–1.5 GB |
| Redis | ~128 MB |
| camxora-api (1–2 workers) | ~0.8–1.5 GB |
| website + portal (Next) | ~0.8–1.2 GB |
| nginx | ~64 MB |

**If RAM spikes:**

- Set API `--workers 1`
- Disable unused botifyr services during CamXora tests
- Add 2 GB swap:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 14. Updates & redeploy

```bash
sudo -u camxora -H bash -lc '
  cd /opt/camxora/repo
  git pull
  cd platform_api && source .venv/bin/activate && alembic upgrade head
  cd ../admin_portal && npm ci && npm run build
  cd ../website && npm ci && npm run build
  cd ../user_portal && npm ci && npm run build
'
sudo systemctl restart camxora-api camxora-website camxora-portal
python scripts/deploy/apply_nginx.py --env sandbox
python scripts/deploy/verify_nginx_api_timeouts.py --env sandbox
```

---

## 15. Backups (minimum)

Daily Postgres dump:

```bash
sudo tee /etc/cron.d/camxora-pg-backup <<'CRON'
0 3 * * * camxora pg_dump -h 127.0.0.1 -U camxora camxora_platform | gzip > /opt/camxora/backups/pg-$(date +\%F).sql.gz
CRON
sudo mkdir -p /opt/camxora/backups && sudo chown camxora:camxora /opt/camxora/backups
```

Copy backups off-VPS (S3, B2, another server).

---

## 16. Post-deploy verification checklist

```bash
curl -s https://api.sandbox.camxora.com/health
curl -s https://api.sandbox.camxora.com/api/v1/plans/public | head
curl -s https://api.sandbox.camxora.com/api/v1/plans/public/term-discounts
```

Browser:

- [ ] `https://sandbox.camxora.com/pricing` — plans load  
- [ ] `https://app.sandbox.camxora.com` — login/register  
- [ ] `https://admin.sandbox.camxora.com` — admin login  
- [ ] CutLuy payment → webhook → active subscription  
- [ ] Add-on purchase → pending slots → portal onboarding → active quotas  
- [ ] Desktop **sandbox installer** login (API URL locked — no Settings override)  
- [ ] Desktop dashboard shows video/merge remaining  
- [ ] Desktop Profile page shows add-on slots (read-only)  
- [ ] Portal onboarding creates profiles; desktop does **not** offer create-profile  
- [ ] Portal onboarding **generate logo/cover** completes without 504 (`verify_nginx_api_timeouts.py`)  
- [ ] Suno callback updates task (after desktop batch test)  

---

## 17. Security hardening for sandbox admin

Restrict admin by IP (optional):

```nginx
# Inside admin.sandbox.camxora.com server block:
allow YOUR.HOME.IP;
deny all;
```

Or use Cloudflare Access / VPN.

---

## 18. Moving sandbox → production later

**Full cutover plan (config migration, no user data):** [`PRODUCTION_CUTOVER.md`](./PRODUCTION_CUTOVER.md).

1. Clone env files with `PLATFORM_ENVIRONMENT=production`  
2. New hostnames: `api.camxora.com`, `app.camxora.com`, `admin.camxora.com`, `music.camxora.com`, `www.camxora.com`  
3. Apply production nginx from repo: `python scripts/deploy/apply_nginx.py --env production`  
4. Run `python scripts/deploy/verify_nginx_api_timeouts.py --env production` (same 300s rule as sandbox)  
5. Migrate **system config** from sandbox (plans, pricing, catalogs) — **not** users/batches — see cutover doc §4–§7  
6. Configure AI routing in Admin — **do not** run `migrate_ai_routing_sandbox.py` on production  
7. Run `validate_production_settings` checks (no debug, strong JWT, Suno HMAC)  
8. Separate PostgreSQL database on the new VPS; prefer a **new** encryption master key  
9. Enable monitoring (Uptime Kuma, healthchecks.io)

Also: [`DEPLOYMENT_OPERATIONS.md`](./DEPLOYMENT_OPERATIONS.md) §7–§8.

---

## 19. Troubleshooting

| Symptom | Fix |
|---------|-----|
| CORS error in browser | Add origin to `PLATFORM_CORS_ORIGINS`; restart API |
| Pricing page empty | API unreachable from website; check `NEXT_PUBLIC_PLATFORM_API_BASE_URL` |
| CutLuy paid but no license | Check webhook logs; verify signature secret; `billing_payments` table |
| 502 from nginx | `systemctl status camxora-api camxora-website camxora-portal` |
| 504 on generate-logo/cover; audit log shows success | Nginx `proxy_read_timeout` too low — apply repo nginx config (300s). See `DEPLOYMENT_OPERATIONS.md` §4 |
| 413 on create-profile | Nginx `client_max_body_size` too low (default 1m) — logo + cover base64 JSON needs 50m. See `DEPLOYMENT_OPERATIONS.md` §2 |
| Migrations fail | `alembic current`; resolve conflicts; never run on botifyr DB |
| OOM kills | Reduce uvicorn workers; add swap; stop dev servers |

---

*Last updated: 2026-07-16. Adjust ports and paths to match your VPS layout.*
