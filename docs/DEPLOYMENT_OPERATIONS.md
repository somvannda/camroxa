# CamXora deployment operations

**Purpose:** Runbook for sandbox and production deploys â€” nginx, AI routing, and common production incidents.  
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

Onboarding **channel logo/cover** and other image endpoints can take **60â€“180+ seconds**:

1. LLM prompt work (optional)
2. External image provider (FAL, SLAI, OpenAI)
3. Large base64 JSON response back to the browser

Nginx default `proxy_read_timeout` is **60 seconds**. When the API finishes after 60s but nginx already closed the client connection:

| Layer | What the user sees | What gets logged |
|-------|-------------------|------------------|
| Browser | **504 Gateway Timeout** | â€” |
| Admin audit log | â€” | **success** (API returned HTTP 200) |

The audit middleware records the **FastAPI response status**, not whether nginx delivered it to the client.

### Required settings

Every nginx `location` that proxies to `platform_api` (`127.0.0.1:8100`) **must** include:

```nginx
proxy_connect_timeout 300s;
proxy_send_timeout 300s;
proxy_read_timeout 300s;
```

This applies to:

- `api.*.camxora.com` â†’ `location /`
- `app.*.camxora.com` â†’ `location /api/` (same-origin portal API proxy)
- `admin.*.camxora.com` â†’ `location /api/`

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

Several admin flows upload large payloads. Nginx default `client_max_body_size` is **1 MB** â†’ **413 Content Too Large** before the request reaches FastAPI.

| Flow | Typical size | Minimum nginx limit |
|------|----------------|---------------------|
| `POST /api/v1/channel-setup/create-profile` (logo + cover base64 JSON) | 2â€“5 MB per image | **50m** |
| `POST /api/v1/admin/desktop/software-update/upload` (desktop installer `.zip`/`.exe`/`.msi`) | up to **500 MB** (API limit) | **550m** |
| Admin image sample pack ZIP upload | varies | **550m** recommended on admin `/api/` |

### Required settings

Every nginx `location` that proxies to `platform_api` must set `client_max_body_size` high enough for the largest expected upload on that route.

**API + admin portal (sandbox example):**

```nginx
# api.sandbox.camxora.com â€” full API including direct admin calls
location / {
    client_max_body_size 550m;
    ...
}

# admin.sandbox.camxora.com â€” SPA + /api/ reverse proxy
location /api/ {
    client_max_body_size 550m;
    proxy_connect_timeout 600s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;
    ...
}
```

Create-profile-only hosts can keep **50m** if they never receive installer uploads.

Apply together with the timeout settings in Â§2.

---

## 4. AI routing by environment

Settings live in PostgreSQL `system_settings` (`ai_routing_assignments`, `ai_routing_*_fallback_chain`).

| Operation group | Sandbox (VPS) | Production (recommended) |
|-----------------|---------------|--------------------------|
| Channel text (`channel_name`, `channel_description`, `channel_keywords`, `channel_tags`) | `deepseek` / `deepseek-chat` | Admin-configured (often `deepseek` or `slai`) |
| Channel images (`channel_logo`, `channel_cover`) | `fal` / `flux-pro` | Admin-configured; ensure provider keys work from VPS |
| Image fallback chain | SLAI â†’ FAL â†’ OpenAI | Same chain; verify each provider from prod network |

### Sandbox routing sync

After changing local admin AI routing or onboarding fixes:

```bash
python scripts/deploy/migrate_ai_routing_sandbox.py
```

This copies local `ai_routing_*` settings and **patches sandbox-specific assignments** (DeepSeek for text, FAL for channel images).

### Production routing

Production should use **Admin â†’ Settings â†’ AI routing** as the source of truth. Before go-live:

1. Confirm API keys decrypt (`PLATFORM_ENCRYPTION_MASTER_KEY` matches the key used when keys were saved).
2. Run provider connectivity checks from the prod VPS.
3. Test `POST /api/v1/channel-setup/generate-logo` end-to-end (browser + audit log).

**Do not** run `migrate_ai_routing_sandbox.py` against production â€” it applies sandbox-specific provider overrides.

---

## 5. Incident: audit log â€œsuccessâ€ but browser 504

**Symptoms**

- User portal onboarding shows `504 Gateway Timeout` on `generate-logo` or `generate-cover`
- Admin audit log shows `api.post` â†’ `channel-setup:generate-logo` â†’ **success**
- Credits may show zero impact (onboarding uses `skip_pricing=True`)

**Root cause**

Nginx timed out before the API response reached the browser. The API may still have completed successfully.

**Fix**

1. Apply nginx config from repo (Â§1) with 300s timeouts.
2. Reload nginx: `nginx -t && systemctl reload nginx`
3. On sandbox, ensure channel image routing points to a working provider (Â§4).
4. Ask user to retry â€” check onboarding draft for saved logo URL before re-generating.

**Prevention**

- Include `verify_nginx_api_timeouts.py` in post-deploy checklist (Â§7).
- Never deploy nginx without API proxy timeout directives.

---

## 6. Deploy script index

| Script | Purpose |
|--------|---------|
| `scripts/deploy/deploy_production.py` | Full production deploy from a commit of `origin/main` (fetch â†’ gate â†’ package â†’ verify) |
| `scripts/deploy/sync_platform_api_production.py` | API-only production sync from `origin/main`, scoped manifest verify |
| `scripts/deploy/sync_music_web_production.py` | music_web-only production sync from `origin/main` |
| `scripts/deploy/release_source.py` | Package one commit + `.deploy-manifest.json` (no working-tree deploys) |
| `scripts/deploy/verify_release_manifest.py` | Verify deployed bytes on the server; prune stale files |
| `scripts/deploy/check_deploy_guards.py` | Preflight: worktree/server invariants, no deploy (`--verify-live` re-hashes the live tree) |
| `scripts/deploy/check_deploy_hygiene.py` | CI gate: no deploy script may write source into the checkout unverified |
| `scripts/deploy/deploy.py` | Full sandbox deploy (source tarball + remote setup) |
| `scripts/deploy/apply_nginx.py` | Push nginx config from repo â†’ VPS |
| `scripts/deploy/verify_nginx_api_timeouts.py` | Confirm 300s timeouts on live nginx |
| `scripts/deploy/migrate_ai_routing_sandbox.py` | Sync AI routing to sandbox with env patches |
| `scripts/deploy/fix_generate_logo_sandbox.py` | One-shot: nginx timeouts + sandbox image routing |
| `scripts/deploy/hotfix_platform_api_sandbox.py` | Fast API-only tarball deploy |
| `scripts/deploy/rebuild_user_portal.py` | Rebuild user portal on sandbox |
| `scripts/deploy/migrate_platform_config.py` | Migrate plans, prompts, settings local â†’ sandbox |

---

## 7. Verified source deploys (how production stops shipping old code)

**Rule:** production ships **one commit of `origin/main`**. It never ships a
working tree, a feature branch, or a tag on an unmerged branch. This is enforced
in code, not by convention.

### Pipeline

1. `scripts/deploy/deploy_production.py` runs `git fetch --prune origin`, then
   resolves the source ref (default `origin/main`).
2. `release_source.build_archive_from_commit()` packages that commit with
   `git archive` â€” only committed content, LF-normalized text â€” and writes
   `.deploy-manifest.json` (sha256 per shipped file).
3. The archive is verified locally against its own manifest before upload.
4. `deploy_guards.enforce_deploy_gate(require_merged=True)` refuses a source
   commit that is not an ancestor of `origin/main`. A tag alone no longer
   bypasses this.
5. On the VPS, `scripts/deploy/verify_release_manifest.py` re-hashes every
   shipped file and **aborts before any build or restart** on mismatch.
6. Files the previous deploy shipped but this commit does not are pruned (from
   the previous checkout's manifest), so retired modules cannot shadow new ones.
7. `.deployed.json` (written **beside** the checkout, so the repo swap cannot
   move it away) records `commit`, `source_commit`, `source_ref`,
   `source_mode`, `source_files`, `deployed_by`, `deployed_at`, invariants.

### Why

Repeated incidents had one shape: the deploy packaged whatever files were in the
worktree the script was launched from, `tar -xzf`'d them over
`/opt/camxora/repo`, and a later deploy from another worktree reverted the fix.
Server-only hotfixes were also wiped by the next deploy. Production ran
`feat/postforme-publishing` (2026-11-02) although it was not merged to `main`.

### Commands

```bash
git fetch origin && git switch main && git pull --ff-only

python scripts/deploy/check_deploy_guards.py production   # preflight, no deploy
python scripts/deploy/deploy_production.py                # full, from origin/main
python scripts/deploy/sync_platform_api_production.py     # API only, from origin/main
python scripts/deploy/sync_music_web_production.py        # music_web only, from origin/main
python scripts/deploy/sync_admin_portal_production.py     # admin_portal only, from origin/main
python scripts/deploy/deploy_musicapi_production.py --yes # musicapi; HEAD must equal origin/main

ssh root@<prod-host> cat /opt/camxora/.deployed.json  # what is live
```

### Failure handling

| Symptom | Meaning | Action |
|---------|---------|--------|
| `Refusing deploy â€” deploy guards failed` | source commit not on `origin/main`, or dirty worktree in worktree mode | merge to `main`; do not override |
| `ARCHIVE_VERIFY_FAILED` | archive and manifest disagree before upload | rebuild; report the corrupt file |
| `DEPLOY_VERIFY_FAILED` / `missing deployed file` | server bytes differ from the commit | stop; investigate disk/extraction, then redeploy the same commit |
| `DEPLOY_LOCKED` | another deploy is running | wait for it |
| Invariants failed | a critical path was removed/reverted | fix on `main`, redeploy |

**Never** edit files on the VPS to "fix" an incident: the next deploy removes
them. Commit, merge, deploy.

### Drift detection (is production still the commit we shipped?)

```bash
# worktree gate + server invariants + live tree re-hash against the manifest
python scripts/deploy/check_deploy_guards.py production --verify-live

# CI/report: which deploy scripts bypass the verified-source pipeline?
python scripts/deploy/check_deploy_hygiene.py            # report
python scripts/deploy/check_deploy_hygiene.py --strict   # fail (legacy allowlist exempt)
```

`--verify-live` prints `.deployed.json` and re-hashes every manifest entry on the
VPS. A non-zero exit means someone edited production in place (a server-side
hotfix, a partial write, or a deploy that skipped the manifest) â€” deploy merged
`main` to restore it. CI fails any PR that adds or edits a deploy script which
writes source without `build_source_bundle()`/`enforce_deploy_gate()`, so the
hole cannot be reopened.

`deploy_production.py` runs the same check **before** uploading and prints a
warning when the live checkout drifted, recording `previous_live_status` in
`.deployed.json`. That is the "my change vanished" case surfaced *before* the
deploy replaces the in-place hotfix, instead of after.

### Adding a new deploy script

It must package a commit and enforce the gate:

```python
from deploy import build_source_bundle, upload_verifier
from deploy_guards import enforce_deploy_gate
from release_source import DEFAULT_SOURCE_REF

bundle = build_source_bundle(DEFAULT_SOURCE_REF)   # origin/main
enforce_deploy_gate(commit=bundle.commit, require_merged=True,
                    require_clean=False)           # exact commit, not HEAD
```

Then extract with `--scope <dir>` verification and reuse
`verify_release_manifest.py`. A script that patches files in place will be
flagged by `check_deploy_hygiene.py`.

---

## 8. Post-deploy checklist (sandbox and production)

### Infrastructure

- [ ] `curl -sf https://api.<env>.camxora.com/health`
- [ ] `python scripts/deploy/verify_nginx_api_timeouts.py --env <sandbox|production>`
- [ ] VPS `timedatectl` shows `Asia/Phnom_Penh`; audit log timestamps display with **ICT** suffix
- [ ] WebSocket path has `proxy_read_timeout 86400`
- [ ] `app.<env>.camxora.com/api/v1/auth/signup-mode` returns JSON (same-origin proxy works)

### Onboarding / image generation

- [ ] `POST /api/v1/channel-setup/generate-names` â†’ 200 (authenticated)
- [ ] `POST /api/v1/channel-setup/generate-logo` â†’ 200 in browser (not 504)
- [ ] Audit log outcome matches browser result
- [ ] Admin â†’ API Key Pool has working keys for routed providers

### Billing (if enabled)

- [ ] CutLuy webhook URL points to `https://api.<env>.camxora.com/api/v3/webhooks/cutluy` (music) and/or `https://api.<env>.camxora.com/api/v3/billing/webhooks/cutluy` (desktop billing). `/api/v1/...` remains dual-mounted during transition.
- [ ] Test payment â†’ subscription active

---

## 9. Moving sandbox â†’ production

**Primary runbook:** [`PRODUCTION_CUTOVER.md`](./PRODUCTION_CUTOVER.md) (new VPS, config-only migration, no user data).

Also use [`SANDBOX_DEPLOYMENT_GUIDE.md` Â§18](./SANDBOX_DEPLOYMENT_GUIDE.md#18-moving-sandbox--production-later) and:

1. Provision prod VPS (see `PRODUCTION_INFRASTRUCTURE_PLAN.md` + cutover doc).
2. Copy `scripts/deploy/nginx-camxora-production.conf` â†’ apply with `apply_nginx.py --env production`.
3. Set `PLATFORM_ENVIRONMENT=production` in `platform_api/.env`.
4. Run `validate_production_settings` (strong JWT, no debug, Suno HMAC).
5. Migrate **system config from sandbox** (plans, pricing, admin catalogs, etc.) â€” **not** users/batches. Inventory script: `scripts/deploy/inventory_sandbox_config_for_prod.py`.
6. Configure AI routing in Admin (do **not** use `migrate_ai_routing_sandbox.py` on production).
7. Run Â§7 checklist on production hostnames.
8. Prefer a **new** `PLATFORM_ENCRYPTION_MASTER_KEY` on prod and re-enter provider keys (or document shared-key risk).

---

## 10. Timezone (Phnom Penh / ICT)

**Server:** VPS and PostgreSQL should use `Asia/Phnom_Penh` (`timedatectl set-timezone Asia/Phnom_Penh`).

**API storage:** Always write audit timestamps with timezone-aware UTC (`platform_api/utils/datetime_utils.py`). Do **not** use naive `datetime.utcnow()` with PostgreSQL `TIMESTAMPTZ` â€” Postgres treats naive values as **local** time, which shifts audit logs by 7 hours.

**Admin display:** Timestamps are formatted in `Asia/Phnom_Penh` with an **ICT** suffix (`admin_portal/src/lib/format-datetime.ts`).

**One-time correction** for rows stored before 2026-07-16:

```bash
python scripts/deploy/fix_audit_log_timezone_sandbox.py
```

---

*When you fix a production incident, update this file and the matching nginx config in the same PR.*
