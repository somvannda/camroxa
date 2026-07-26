# Production cutover — decisions (2026-07-26 update)

**Document ID:** CAMXORA-PROD-CUTOVER-001  
**Status:** production VPS bootstrap done (HTTP); DNS + TLS pending  
**Date:** 2026-07-26 (revised)  
**Audience:** engineering / DevOps  

**Related:** [`PRODUCTION_INFRASTRUCTURE_PLAN.md`](./PRODUCTION_INFRASTRUCTURE_PLAN.md), [`DEPLOYMENT_OPERATIONS.md`](./DEPLOYMENT_OPERATIONS.md), [`FOLLOWUPS_DESKTOP_GPU_EXPORT.md`](./FOLLOWUPS_DESKTOP_GPU_EXPORT.md)

---

## 0. Pre-flight (git + VPS)

| Item | Status |
|------|--------|
| Branch | `cursor/channel-pricing-and-plan-tiers` |
| Marketing homepage + portal chrome | Pushed + sandbox deployed |
| Desktop stamps | `1.0.0` targeting `api.camxora.com` (installer build still pending) |
| B2 media copy sandbox → `productions-camxora-song` | Done (~850 objects) |
| Production VPS bootstrap (`deploy_production.py`) | **Done** on `82.197.71.248` — API/website/portal/admin/music systemd active |
| TLS (Let's Encrypt) | **Blocked** — production DNS A records not pointed at prod VPS yet |
| AI provider keys / CutLuy webhook / streaming B2 admin | Not configured on prod yet |

### DNS required (Cloudflare / registrar)

Point these **A** records to **`82.197.71.248`**, then re-run certbot:

```
A    camxora.com           → 82.197.71.248
A    www.camxora.com       → 82.197.71.248
A    api.camxora.com       → 82.197.71.248
A    app.camxora.com       → 82.197.71.248
A    admin.camxora.com     → 82.197.71.248
A    music.camxora.com     → 82.197.71.248
```

After DNS propagates:

```bash
python scripts/deploy/apply_nginx.py --env production
# or SSH and:
certbot --nginx -d api.camxora.com -d camxora.com -d www.camxora.com -d app.camxora.com -d admin.camxora.com --non-interactive --agree-tos -m CERTBOT_EMAIL --redirect
```

---

## 1. Confirmed product decisions

| Topic | Decision |
|-------|----------|
| Users / licenses / batches / songs / wallets | **Do not migrate** |
| Finance (payments, credit wallets/transactions) | **Do not migrate** |
| Software updates / desktop push / client logs / audit logs / usage | **Do not migrate** |
| Image sample packs / marketplace | **Do not migrate** — recreate manually on prod |
| Plans (+ plan offers if any) | Migrate from **local** Postgres, **not** sandbox |
| Other system config (pricing, AI routing, admin prompts, moods, languages, genres, blocklist, channel prompts, content pools, blog, …) | From **sandbox** (except items above) |
| Streaming catalog (`stream_albums` / `stream_tracks` + cover art keys) | **Migrate** without real owners — see §3 |
| B2 song/media objects | Copy sandbox bucket → prod bucket — see §4 |
| Desktop first official release | **v1.0.0** → `https://api.camxora.com/api/v1` |

---

## 2. What we will NOT copy

- `users`, `licenses`, `batches`, `songs`, `suno_tasks`, `image_jobs`, channel profiles, onboarding  
- Billing: `billing_payments`, `credit_wallets`, `credit_transactions`, daily quota bank  
- `client_log_batches`, `video_export_telemetry`, `audit_logs`, `notification_queue`, usage tables  
- Desktop software-update rows / `desktop.software_update.*` settings (republish 1.0.0 after go-live)  
- `image_sample_packs` / assets, `marketplace_items` (+ their disk files)  
- Redis  

---

## 3. Streaming catalog without owners

### Schema constraint

`stream_albums.user_id` and `stream_tracks.user_id` are **`NOT NULL`** with FK → `users.id`.  
True “ownerless” rows are **impossible** without a schema change.

### Agreed approach (day one)

1. On production, create a single **placeholder user** (no login / invite-only lock), e.g.  
   - email: `catalog-unassigned@system.camxora.local`  
   - display: `Unassigned Catalog`  
2. Import all sandbox `stream_albums` + `stream_tracks` (+ metadata fields, storage keys, covers).  
3. Set every imported row’s `user_id` to that placeholder.  
4. Null out FKs that point at non-migrated tables: `batch_id`, `song_id`, `suno_task_id` (and skip `stream_upload_jobs`).  
5. Keep `storage_key` / `cover_storage_key` **unchanged** so they resolve in the **production** B2 bucket after the object copy.  
6. **Later:** Admin/script reassigns albums/tracks from placeholder → real creators (post go-live migration).

Public music portal can show catalog as long as `publish_status = published` and signed URLs use the prod B2 credentials.

---

## 4. Backblaze B2 object copy

| | Sandbox (source) | Production (destination) |
|--|------------------|---------------------------|
| Bucket | `camroxa-song-storage` | `productions-camxora-song` |
| Visibility | Public | Private |
| Endpoint | `s3.us-east-005.backblazeb2.com` | same |
| Approx size | ~1,764 files / ~8.8 GB | starts empty |

**Script (two-key download/upload):** `scripts/deploy/migrate_b2_song_storage_two_key.py`  
- Source credentials: sandbox `streaming.b2.*` (decrypt with sandbox master key)  
- Dest credentials: production application key (must be entitled to `productions-camxora-song`)  

**Important:** The production key you shared is **restricted to the prod bucket only**, so server-side `CopyObject` from sandbox→prod is not allowed. Migration downloads via sandbox key and uploads via prod key (~4+ GB; object count may differ from B2 UI if versions are counted).

**Security:** Rotate both B2 application keys after cutover (keys appeared in chat / local `.dbg`). Never commit `.dbg/b2_src.env`.

**Prod API config after copy:**

- `PLATFORM_STREAMING_B2_*` env and/or Admin `streaming.b2.*` → prod bucket + prod key  
- Private bucket: keep using signed URLs (app already supports this)

---

## 5. Plans from local database

| Source | Tables |
|--------|--------|
| **Local** `platform_db` | `plans`, `plan_offers` (if used) |
| Prefer **not** sandbox plans | Avoid sandbox-only experiments |

Also decide locally whether to export `channel_pricing_config` / `plan_term_discounts` / `global_credit_value` from local `system_settings`, or keep sandbox pricing JSON — **default: local plans rows + confirm pricing JSON with product before import.**

---

## 6. Config still expected from sandbox (non-user)

Copy when implementing DB migrator (excluding §2):

- Admin catalogs: descriptions/structures/moods (`user_id IS NULL`), languages, genres, channel prompts, suno blocklist  
- `credit_packs`, `credit_pricing`, `ai_model_costs` (unless you prefer local)  
- `system_settings` **except** finance overrides you will re-enter, software-update keys, sandbox URLs  
- Content pools (title/album/opening) + preset packs — reset `used_*` counters  
- Blog posts (optional)  
- AI routing JSON + key entries (encryption key policy still applies)

**Manual redo on prod:** sample packs, marketplace, CutLuy live keys, SMTP, software updates.

---

## 7. Desktop v1.0.0 (official)

| Item | Value |
|------|--------|
| Version | `1.0.0` |
| Build env | `CAMXORA_BUILD_ENV=production` |
| API | `https://api.camxora.com/api/v1` |
| Portal | `https://app.camxora.com` |
| Changelog | High-level product features only (not every sandbox hotfix) |
| Installer | `CamxoraSetup-1.0.0.exe` after API is live |

Footer must **not** show “Sandbox API”.

---

## 8. Cutover order (updated)

1. Provision prod VPS + empty DB + alembic head  
2. Finish B2 copy; verify object counts  
3. Import **local plans**  
4. Import sandbox system/catalog config (scrubbed)  
5. Create placeholder catalog user; import stream albums/tracks  
6. Point prod streaming settings at `productions-camxora-song`  
7. Seed real admin; enter provider keys; DNS + CutLuy webhook  
8. Publish desktop **1.0.0**  
9. Later: reassign streaming ownership from placeholder  

---

## 9. Open engineering tasks

| Task | Status |
|------|--------|
| B2 bucket copy script + run | **Done** (~850 objects → `productions-camxora-song`) |
| Sandbox→prod config migrator (scoped) | Not started |
| Local plans export/import | Not started |
| Streaming import w/ placeholder owner | Not started |
| Desktop 1.0.0 production build | Stamped; installer build pending after API live |
| Production VPS secrets in `.deploy/secrets.env` | **Pending** |
| Rotate B2 application key | **Required after chat exposure** |

---

*User data, licenses, batches, finance, packs/marketplace remain out of scope for day-one migration.*
