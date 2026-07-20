# CamXora deployment operations

**Purpose:** Runbook for sandbox and production deploys — nginx, AI routing, and common production incidents.  
**Last updated:** 2026-07-16  
**Related:** [`SANDBOX_DEPLOYMENT_GUIDE.md`](./SANDBOX_DEPLOYMENT_GUIDE.md), [`PRODUCTION_INFRASTRUCTURE_PLAN.md`](./PRODUCTION_INFRASTRUCTURE_PLAN.md)

---

## 1. Canonical nginx configs (source of truth)

| Environment | Repo file | Remote path |
|-------------|-----------|-------------|
| Sandbox | `scripts/deploy/nginx-camxora-sandbox.conf` | `/etc/nginx/sites-available/camxora-sandbox` |
| Production | `scripts/deploy/nginx-camxora-production.conf` | `/etc/nginx/sites-available/camxora-production` |

**Always edit the repo file first**, then apply to the server. Do not hand-edit nginx on the VPS without syncing back to the repo.

Apply to sandbox:

```bash
python scripts/deploy/apply_nginx.py --env sandbox
```

Apply to production (when prod VPS is ready):

```bash
python scripts/deploy/apply_nginx.py --env production
```

---

## 2. Required nginx proxy timeouts (image generation)

### Why this matters

Onboarding **channel logo/cover** and other image endpoints can take **60–180+ seconds**:

1. LLM prompt work (optional)
2. External image provider (FAL, SLAI, OpenAI)
3. Large base64 JSON response back to the browser

Nginx default `proxy_read_timeout` is **60 seconds**. When the API finishes after 60s but nginx already closed the client connection:

| Layer | What the user sees | What gets logged |
|-------|-------------------|------------------|
| Browser | **504 Gateway Timeout** | — |
| Admin audit log | — | **success** (API returned HTTP 200) |

The audit middleware records the **FastAPI response status**, not whether nginx delivered it to the client.

### Required settings

Every nginx `location` that proxies to `platform_api` (`127.0.0.1:8100`) **must** include:

```nginx
proxy_connect_timeout 300s;
proxy_send_timeout 300s;
proxy_read_timeout 300s;
```

This applies to:

- `api.*.camxora.com` → `location /`
- `app.*.camxora.com` → `location /api/` (same-origin portal API proxy)
- `admin.*.camxora.com` → `location /api/`

WebSocket blocks keep a separate long timeout:

```nginx
proxy_read_timeout 86400;
```

### Post-deploy verification

```bash
python scripts/deploy/verify_nginx_api_timeouts.py --env sandbox
```

Or manually on the server:

```bash
grep -n proxy_read_timeout /etc/nginx/sites-available/camxora-sandbox
nginx -t && systemctl reload nginx
```

Expected: `300s` on all API proxy locations (except WebSocket `86400`).

---

## 3. Required nginx upload body size

### Why this matters

Several admin flows upload large payloads. Nginx default `client_max_body_size` is **1 MB** → **413 Content Too Large** before the request reaches FastAPI.

| Flow | Typical size | Minimum nginx limit |
|------|----------------|---------------------|
| `POST /api/v1/channel-setup/create-profile` (logo + cover base64 JSON) | 2–5 MB per image | **50m** |
| `POST /api/v1/admin/desktop/software-update/upload` (desktop installer `.zip`/`.exe`/`.msi`) | up to **500 MB** (API limit) | **550m** |
| Admin image sample pack ZIP upload | varies | **550m** recommended on admin `/api/` |

### Required settings

Every nginx `location` that proxies to `platform_api` must set `client_max_body_size` high enough for the largest expected upload on that route.

**API + admin portal (sandbox example):**

```nginx
# api.sandbox.camxora.com — full API including direct admin calls
location / {
    client_max_body_size 550m;
    ...
}

# admin.sandbox.camxora.com — SPA + /api/ reverse proxy
location /api/ {
    client_max_body_size 550m;
    proxy_connect_timeout 600s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;
    ...
}
```

Create-profile-only hosts can keep **50m** if they never receive installer uploads.

Apply together with the timeout settings in §2.

---

## 4. AI routing by environment

Settings live in PostgreSQL `system_settings` (`ai_routing_assignments`, `ai_routing_*_fallback_chain`).

| Operation group | Sandbox (VPS) | Production (recommended) |
|-----------------|---------------|--------------------------|
| Channel text (`channel_name`, `channel_description`, `channel_keywords`, `channel_tags`) | `deepseek` / `deepseek-chat` | Admin-configured (often `deepseek` or `slai`) |
| Channel images (`channel_logo`, `channel_cover`) | `fal` / `flux-pro` | Admin-configured; ensure provider keys work from VPS |
| Image fallback chain | SLAI → FAL → OpenAI | Same chain; verify each provider from prod network |

### Sandbox routing sync

After changing local admin AI routing or onboarding fixes:

```bash
python scripts/deploy/migrate_ai_routing_sandbox.py
```

This copies local `ai_routing_*` settings and **patches sandbox-specific assignments** (DeepSeek for text, FAL for channel images).

### Production routing

Production should use **Admin → Settings → AI routing** as the source of truth. Before go-live:

1. Confirm API keys decrypt (`PLATFORM_ENCRYPTION_MASTER_KEY` matches the key used when keys were saved).
2. Run provider connectivity checks from the prod VPS.
3. Test `POST /api/v1/channel-setup/generate-logo` end-to-end (browser + audit log).

**Do not** run `migrate_ai_routing_sandbox.py` against production — it applies sandbox-specific provider overrides.

---

## 5. Incident: audit log “success” but browser 504

**Symptoms**

- User portal onboarding shows `504 Gateway Timeout` on `generate-logo` or `generate-cover`
- Admin audit log shows `api.post` → `channel-setup:generate-logo` → **success**
- Credits may show zero impact (onboarding uses `skip_pricing=True`)

**Root cause**

Nginx timed out before the API response reached the browser. The API may still have completed successfully.

**Fix**

1. Apply nginx config from repo (§1) with 300s timeouts.
2. Reload nginx: `nginx -t && systemctl reload nginx`
3. On sandbox, ensure channel image routing points to a working provider (§4).
4. Ask user to retry — check onboarding draft for saved logo URL before re-generating.

**Prevention**

- Include `verify_nginx_api_timeouts.py` in post-deploy checklist (§7).
- Never deploy nginx without API proxy timeout directives.

---

## 6. Deploy script index

| Script | Purpose |
|--------|---------|
| `scripts/deploy/deploy.py` | Full sandbox deploy (source tarball + remote setup) |
| `scripts/deploy/apply_nginx.py` | Push nginx config from repo → VPS |
| `scripts/deploy/verify_nginx_api_timeouts.py` | Confirm 300s timeouts on live nginx |
| `scripts/deploy/migrate_ai_routing_sandbox.py` | Sync AI routing to sandbox with env patches |
| `scripts/deploy/fix_generate_logo_sandbox.py` | One-shot: nginx timeouts + sandbox image routing |
| `scripts/deploy/hotfix_platform_api_sandbox.py` | Fast API-only tarball deploy |
| `scripts/deploy/rebuild_user_portal.py` | Rebuild user portal on sandbox |
| `scripts/deploy/migrate_platform_config.py` | Migrate plans, prompts, settings local → sandbox |

---

## 7. Post-deploy checklist (sandbox and production)

### Infrastructure

- [ ] `curl -sf https://api.<env>.camxora.com/health`
- [ ] `python scripts/deploy/verify_nginx_api_timeouts.py --env <sandbox|production>`
- [ ] VPS `timedatectl` shows `Asia/Phnom_Penh`; audit log timestamps display with **ICT** suffix
- [ ] WebSocket path has `proxy_read_timeout 86400`
- [ ] `app.<env>.camxora.com/api/v1/auth/signup-mode` returns JSON (same-origin proxy works)

### Onboarding / image generation

- [ ] `POST /api/v1/channel-setup/generate-names` → 200 (authenticated)
- [ ] `POST /api/v1/channel-setup/generate-logo` → 200 in browser (not 504)
- [ ] Audit log outcome matches browser result
- [ ] Admin → API Key Pool has working keys for routed providers

### Billing (if enabled)

- [ ] CutLuy webhook URL points to `https://api.<env>.camxora.com/api/v1/billing/webhooks/cutluy`
- [ ] Test payment → subscription active

---

## 8. Moving sandbox → production

Use this in addition to [`SANDBOX_DEPLOYMENT_GUIDE.md` §18](./SANDBOX_DEPLOYMENT_GUIDE.md#18-moving-sandbox--production-later):

1. Provision prod VPS (see `PRODUCTION_INFRASTRUCTURE_PLAN.md`).
2. Copy `scripts/deploy/nginx-camxora-production.conf` → apply with `apply_nginx.py --env production`.
3. Set `PLATFORM_ENVIRONMENT=production` in `platform_api/.env`.
4. Run `validate_production_settings` (strong JWT, no debug, Suno HMAC).
5. Configure AI routing in Admin (do **not** use sandbox routing migration script).
6. Run §7 checklist on production hostnames.
7. Separate PostgreSQL database; separate encryption master key if keys were encrypted on another env.

---

## 9. Timezone (Phnom Penh / ICT)

**Server:** VPS and PostgreSQL should use `Asia/Phnom_Penh` (`timedatectl set-timezone Asia/Phnom_Penh`).

**API storage:** Always write audit timestamps with timezone-aware UTC (`platform_api/utils/datetime_utils.py`). Do **not** use naive `datetime.utcnow()` with PostgreSQL `TIMESTAMPTZ` — Postgres treats naive values as **local** time, which shifts audit logs by 7 hours.

**Admin display:** Timestamps are formatted in `Asia/Phnom_Penh` with an **ICT** suffix (`admin_portal/src/lib/format-datetime.ts`).

**One-time correction** for rows stored before 2026-07-16:

```bash
python scripts/deploy/fix_audit_log_timezone_sandbox.py
```

---

*When you fix a production incident, update this file and the matching nginx config in the same PR.*
