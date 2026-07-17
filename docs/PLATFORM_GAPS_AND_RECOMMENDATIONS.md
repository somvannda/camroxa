# CamXora Platform — Gaps Analysis & Recommendations

**Date:** 2026-07-15  
**Scope:** Full stack — `platform_api`, `website`, `user_portal`, `admin_portal`, `camxora_python`, `camxora`, `python_app`  
**Environment target:** Sandbox on shared VPS (dev/staging), **CutLuy production** for real payment tests only  
**Related docs:** [`BILLING_COSTS_SECURITY_LAUNCH_GAPS.md`](./BILLING_COSTS_SECURITY_LAUNCH_GAPS.md), [`billing-proration-and-plan-changes.md`](./billing-proration-and-plan-changes.md), [`PRODUCTION_INFRASTRUCTURE_PLAN.md`](./PRODUCTION_INFRASTRUCTURE_PLAN.md)

---

## 1. Executive summary

CamXora has a **strong billing enforcement core** in `platform_api` (plan meters, wallet holds, CutLuy scaffold, audit, rate limits). The **web surfaces** (website, portals) are largely aligned with live plan data. **Desktop clients** (`camxora_python`, legacy `camxora`) depend on the API being reachable with correct CORS, callbacks, and WebSocket URLs.

**What is production-ready today**

| Area | Status |
|------|--------|
| Auth (JWT, refresh rotation, lockout) | Ready with correct env |
| Plan meters (draft/song/image/video/merge) | Implemented |
| Admin Plans as pricing SSOT | Implemented |
| CutLuy plan checkout + webhook scaffold | Ready for **live keys** |
| Website public pricing | Live plans + term discounts API |
| Admin portal (plans, users, finance, licenses) | Functional |
| User portal (billing, onboarding, profiles) | Functional |

**What is NOT ready for public production** (sandbox can proceed with mitigations below)

| Area | Risk | Sandbox? | Production? |
|------|------|----------|-------------|
| Proration on plan upgrade (B2) | Billing correctness | ✅ proration checkout | ✅ implemented |
| Add-on term alignment (B3) | Price mismatch for 6mo/annual subs | ✅ term-aligned quotes | ✅ implemented |
| Website vs checkout price sync (B4) | User trust | ✅ drift API + Admin sync | ⚠️ run sync after edits |
| Credit pack purchase via CutLuy (B7) | Wallet top-ups | ✅ billing checkout | ✅ implemented |
| Background job queue / worker split | Scale & reliability | ✅ single-process OK | ❌ Phase C |
| Object storage for media streaming | VPS disk & egress | ✅ local disk OK | ❌ B2 + CDN |
| Full production hardening (S7) | Security ops | ✅ staging env | ❌ KMS at scale |
| WS auth query string (S2) | Token in URL | ✅ header auth preferred | ✅ desktop updated |

**Recommendation:** Deploy sandbox stack, run migration **056**, configure env, build sandbox desktop installer, run §10 checklist including CutLuy micro-payments and credit-pack checkout.

### Sandbox readiness (2026-07-15)

| Item | Status |
|------|--------|
| Admin add-on manage (+/− pending & active) | Done |
| Safe add-on removal validation | Done |
| Plan upgrade preserves add-ons (B1) | Done |
| Proration on upgrade (B2) | Done |
| Add-on term alignment (B3) | Done |
| Price drift check + sync (B4) | Done (Admin drift banner + sync add-ons) |
| Scheduled downgrade at renewal (B5) | Done (`POST /billing/schedule-downgrade`, migration 056) |
| Credit pack CutLuy (B7) | Done |
| WS auth via Authorization header (S2) | Done (desktop; query legacy still supported) |
| Desktop dashboard video/merge quotas | Done |
| Desktop profile add-on display | Done |
| Desktop API URL locked per build | Done |
| Portal-only onboarding & profile creation | Done |
| User portal video/merge quota labels (E4) | Done |
| Pending vs active add-on UX (E1) | Done (portal copy) |
| Website sandbox banner | Done (env flag) |
| Job queue / B2 streaming / KMS (S7) | Phase C — not sandbox blockers |
| Security S1–S8 (env/config) | Deploy checklist |
| Infra §5 (VPS, backups, CI) | Deploy checklist — SANDBOX guide |

### Master gap status (all IDs)

| ID | Summary | Code status | Sandbox blocker? |
|----|---------|-------------|------------------|
| **S1** | Fail-fast production boot | ✅ exists — set env | No — set `PLATFORM_DEBUG=false` |
| **S2** | WS token in query string | ✅ **Fixed** — header preferred | No |
| **S3** | CORS localhost default | ✅ config — set origins | No — set `PLATFORM_CORS_ORIGINS` |
| **S4** | Suno callback HTTPS | ✅ config | No — set callback URL |
| **S5** | CutLuy webhook HMAC | ✅ exists — set secret | No — configure webhook |
| **S6** | Credit pack mint closed | ✅ intentional | No |
| **S7** | No KMS for API keys | Open (Phase C) | No for sandbox |
| **S8** | Admin dual-control credits | ✅ exists — verify flow | No — test once |
| **B1** | Upgrade revokes add-ons | ✅ **Fixed** | No |
| **B2** | No proration | ✅ **Fixed** | No |
| **B3** | Add-on monthly-only checkout | ✅ **Fixed** | No |
| **B4** | Website vs checkout price drift | ✅ drift API + Admin sync | No if synced |
| **B5** | No scheduled downgrade | ✅ **Fixed** | No |
| **B6** | Mock checkout when debug | ✅ guard exists | No — keep debug off |
| **B7** | Credit packs not wired | ✅ **Fixed** | No |
| **F1–F5** | Finance / ledger / COGS | ✅ implemented — **verify** in sandbox | No — run test payment |
| **E1** | Pending vs active add-on UX | ✅ **Fixed** | No |
| **E2** | Safe add-on removal | ✅ **Fixed** | No |
| **E3** | 10 channel cap | ✅ enforced | No |
| **E4** | Video/merge quota labels | ✅ **Fixed** | No |
| **E5** | Plan meters required | ✅ guard — seed plans correctly | No |

---

## 2. Service inventory

| Service | Stack | Default port | Role |
|---------|-------|-------------|------|
| `platform_api` | FastAPI, PostgreSQL, Redis | **8000** | Sole billing & AI enforcement |
| `website` | Next.js 16 | **3000** | Marketing, `/pricing` |
| `user_portal` | Next.js 16 | **3001** (recommended) | Login, billing, onboarding |
| `admin_portal` | Vite + React | **5173** dev / static prod | Admin CMS |
| `camxora_python` | PySide6 desktop | — | Primary desktop client |
| `camxora` | Electron (legacy) | — | Older desktop client |
| `python_app` | PySide6 (older tree) | — | Legacy; prefer `camxora_python` |

**External dependencies**

| Dependency | Used for |
|------------|----------|
| PostgreSQL 15+ | All platform state |
| Redis 7 | Rate limits, lockout, token blocklist |
| Suno API | Music generation + callbacks |
| DeepSeek / SLAI / Fal | Drafts & images |
| CutLuy (`cutluy.com`) | KHQR plan & add-on checkout |
| Backblaze B2 (optional) | Music streaming catalog |
| SMTP | Email verification |

---

## 3. Critical gaps (fix before real customers)

### 3.1 Security

| ID | Gap | Evidence | Recommendation | Status |
|----|-----|----------|----------------|--------|
| **S1** | Production boot without fail-fast if `debug=true`, weak JWT, missing Suno HMAC | `platform_api/config.py` → `validate_production_settings()` | Sandbox: set `PLATFORM_ENVIRONMENT=staging`, `PLATFORM_DEBUG=false`, unique JWT ≥32 chars | **Deploy config** |
| **S2** | WebSocket auth via query string `?token=` on desktop | `camxora_python/tests/test_ws_url.py` | Prefer `Authorization: Bearer` header; query legacy supported | ✅ **Fixed** |
| **S3** | CORS allowlist defaults to localhost only | `platform_api/config.py` → `cors_origins` | Set `PLATFORM_CORS_ORIGINS` to sandbox domains explicitly | **Deploy config** |
| **S4** | Suno callback must be HTTPS public URL | `PLATFORM_SUNO_CALLBACK_BASE_URL` | Use `https://api.sandbox.camxora.com/api/v1/callbacks/suno` | **Deploy config** |
| **S5** | CutLuy webhook signature required | `platform_api/routers/billing.py` → `/webhooks/cutluy` | Configure `PLATFORM_CUTLUY_WEBHOOK_SECRET` from CutLuy dashboard | **Deploy config** |
| **S6** | Unverified credit pack mint still disabled | `POST /credits/purchase` | **Keep closed** until CutLuy pack product exists | **By design** |
| **S7** | API keys in DB — per-row salt, no KMS | `BILLING_COSTS_SECURITY_LAUNCH_GAPS.md` §M9 | Sandbox OK; add KMS envelope before high-value keys at scale | **Open — Phase C** |
| **S8** | Admin dual-control for large credit adjusts | Migration `047_admin_pending_ops` | Enable in sandbox; test second-admin approve flow | **Verify in sandbox** |

### 3.2 Billing & plans

| ID | Gap | Impact | Recommendation | Status |
|----|-----|--------|----------------|--------|
| **B1** | **Plan upgrade revokes license** — wipes add-ons | Paid users lose `profile_addon_*` on plan change | Fulfillment calls `change_plan` in place | ✅ **Fixed** |
| **B2** | **No proration** on mid-cycle upgrade | Over/under-charge vs policy in `billing-proration-and-plan-changes.md` | `proration_service` + checkout integration | ✅ **Fixed** |
| **B3** | **Add-on checkout monthly only** — not aligned to user's 6mo/annual term | Price mismatch for long-term subscribers | Term-aligned add-on quotes + sync | ✅ **Fixed** |
| **B4** | **Website 6mo/annual display** vs **checkout plan rows** can diverge | Marketing shows calculated discount; checkout uses DB row | `GET /plans/term-price-drift` + Admin sync (incl. add-ons) | ✅ **Fixed** |
| **B5** | **No scheduled downgrade at renewal** | Support burden if mid-cycle downgrades allowed | Block mid-cycle; `POST /billing/schedule-downgrade` | ✅ **Fixed** |
| **B6** | **Mock checkout** only when `PLATFORM_DEBUG=true` | Accidental free plans if debug left on | Never enable debug on sandbox payment paths | **Deploy config** |
| **B7** | CutLuy **credit packs** not wired | Users cannot buy wallet top-ups | `POST /billing/credit-pack/payments` + webhook | ✅ **Fixed** |

### 3.3 Credits & financial

| ID | Gap | Impact | Recommendation | Status |
|----|-----|--------|----------------|--------|
| **F1** | Finance depends on complete `billing_payments` + ledger | Under-reported revenue if webhooks fail | Monitor webhook logs; alert on unpaid `pending` > 1h | **Verify in sandbox** |
| **F2** | `platform_absorb` fail budget (25/day) | Abuse or bad provider configs | Tune `PLATFORM_DAILY_FAIL_ABSORB_BUDGET` per sandbox | **Deploy config** |
| **F3** | Redeem codes can unlock full plans | Promo abuse | Rate-limit redeem; admin alerts on burst | **Implemented — verify** |
| **F4** | GCV / pricing drift | Negative margin | Keep Admin pricing gate (cost ≤ sell) enabled | **Ongoing ops** |
| **F5** | Subscription cash in Finance | Reports after CutLuy live tests | Run $0.01–$1 KHQR test; confirm Finance row | **Verify in sandbox** |

### 3.4 Entitlements & quotas

| ID | Gap | Impact | Recommendation | Status |
|----|-----|--------|----------------|--------|
| **E1** | Add-on **pending vs active** — quotas scale on active only | User confusion if onboarding skipped | Portal copy + admin tool | ⚠️ **Partial — test E2E** |
| **E2** | Admin add-on removal blocked if profiles exceed allowance | Correct — document for support | `validate_profile_addon_reduction` | ✅ **Fixed** |
| **E3** | Max **10 channels** cap | Hard limit | Enforced in API; show in portal | ✅ **Fixed** |
| **E4** | User portal **video/merge remaining** labels | UX gap | Dashboard + credits pages | ✅ **Fixed** |
| **E5** | Plan row null meters rejected for paid recurring | Good guard | Ensure all sandbox plans have full meter set | **Deploy config** (seed plans) |

---

## 4. Medium gaps (features & UX)

> **Legend:** ✅ done · ⚠️ deploy/config/test · ❌ open code work · 🔒 by design for sandbox

### 4.1 `platform_api`

| Gap | Notes | Status |
|-----|-------|--------|
| Batch runs in **BackgroundTasks** (same uvicorn process) | No durable queue; restart loses in-flight batches | ❌ Phase C |
| Profile uploads on local `uploads/` disk | Not B2-backed at scale | ⚠️ OK for sandbox |
| Music streaming needs B2 + CDN config | `PLATFORM_STREAMING_*` vars empty by default | ❌ Phase C |
| Email verification uses SMTP defaults (MailHog) | Configure real SMTP for sandbox invites | ⚠️ Deploy config |
| Marketplace storage local path | `./marketplace_storage` on VPS disk | ⚠️ OK for sandbox |
| Migrations **049–055** must be applied | Channel tiers, add-ons, term discounts | ⚠️ Deploy step |

### 4.2 `admin_portal`

| Gap | Notes | Status |
|-----|-------|--------|
| Subscriptions add-on UI | Add/remove pending & active | ✅ **Fixed** |
| Term discount **sync** manual step | Easy to forget after editing % | ⚠️ **Manual ops** (B4) |
| No built-in deploy/health dashboard | Use `/health` + external uptime | ❌ Phase C |
| Users list paginated (100) — profile count for add-on dialog | May miss users not on page 1 | ❌ Low priority |

### 4.3 `user_portal`

| Gap | Notes | Status |
|-----|-------|--------|
| Hardcoded marketing URL fallback `https://camxora.com` | Set `NEXT_PUBLIC_MARKETING_BASE_URL` for sandbox | ⚠️ Deploy config |
| Mock checkout pages still present | Hidden when `debug=false` on API | ⚠️ OK if API not debug |
| Plan upgrade self-service | Depends on B2 proration for correctness | ⚠️ Test w/ micro-amounts; B2 before prod |
| Profile add-on purchase + onboarding flow | End-to-end on sandbox | ⚠️ **Verify in sandbox** |

### 4.4 `website`

| Gap | Notes | Status |
|-----|-------|--------|
| Pricing page needs API reachable at build/SSR time | Set `NEXT_PUBLIC_PLATFORM_API_BASE_URL` | ⚠️ Deploy config |
| Weak CTAs on some pages | Link to portal with `plan_id` | ⚠️ Partial — polish later |
| No staging banner | `NEXT_PUBLIC_CAMXORA_ENV=sandbox` | ✅ **Fixed** |
| 6mo/annual price display vs DB checkout rows | Computed display fixed; DB sync manual | ⚠️ B4 — Admin sync after discount edits |

### 4.5 `camxora_python` / `camxora`

| Gap | Notes | Status |
|-----|-------|--------|
| API base URL user-editable in settings | Locked in sandbox/production builds | ✅ **Fixed** |
| Onboarding wizard on desktop | Portal-only redirect | ✅ **Fixed** |
| Create profile on desktop | Settings opens portal | ✅ **Fixed** |
| Dashboard missing video/merge remaining | `RemainingMonthCard` | ✅ **Fixed** |
| Profile page missing add-on slots | Membership card | ✅ **Fixed** |
| WS token in query string | Header auth preferred; query legacy supported | ✅ **Fixed** (S2) |
| Feature parity: `python_app` vs `camxora_python` | Standardize on `camxora_python` | ⚠️ Use `camxora_python` only |
| Auto-merge refund-on-skip weaker in Electron vs Python | Low–medium | ❌ Low priority |
| Desktop not deployed on server | Ship sandbox installer to testers | ⚠️ Build pipeline |

#### Desktop release policy (sandbox → production)

1. **No runtime API switching** — users cannot point the app at arbitrary endpoints.
2. **Separate installers** — sandbox build bakes `https://api.sandbox.camxora.com/api/v1`; production build bakes `https://api.camxora.com/api/v1`.
3. **Build-time env** — set `CAMXORA_BUILD_ENV`, `CAMXORA_API_BASE_URL`, `CAMXORA_PORTAL_BASE_URL` in CI or bundle `.env.sandbox` / `.env.production` next to the executable (see `camxora_python/.env.*.example`).
4. **Portal for account setup** — billing, onboarding, and new profiles happen in the user portal only; desktop is for generation workflows on existing profiles.
5. **Safe production cutover** — publish new production installer + update download page; do not OTA-switch API URL on installed sandbox builds.

---

## 5. Infrastructure & ops gaps

| Gap | Detail | Sandbox mitigation | Status |
|-----|--------|-------------------|--------|
| **No Docker Compose in repo** | Manual install | Follow [`SANDBOX_DEPLOYMENT_GUIDE.md`](./SANDBOX_DEPLOYMENT_GUIDE.md) | ⚠️ Documented |
| **Shared VPS with botifyr.xyz** | CPU/RAM contention | Separate ports, PostgreSQL DB, Redis DB index | ⚠️ Deploy choice |
| **8 GB RAM tight** | OOM risk | Next production mode; uvicorn workers 1–2 | ⚠️ Deploy tuning |
| **150 GB disk** | OK for Postgres + logs | Do not store MP3s on VPS; B2 later | ⚠️ OK for sandbox |
| **No automated backups documented** | Data loss risk | Daily `pg_dump` cron in deploy guide §15 | ⚠️ **Set up on VPS** |
| **No CI deploy pipeline** | Manual drift | Git pull + systemd restart procedure | ❌ Phase C |
| **Suno callback IP allowlist** | Dev fallback when HMAC missing | Always set HMAC on sandbox | ⚠️ Deploy config |

See [`PRODUCTION_INFRASTRUCTURE_PLAN.md`](./PRODUCTION_INFRASTRUCTURE_PLAN.md) for the longer-term VPS 20 + worker + B2 architecture.

---

## 6. CutLuy integration strategy (sandbox)

CutLuy has **no sandbox mode** — only live Bakong KHQR ([cutluy.com/docs](https://cutluy.com/docs)).

**Recommended sandbox approach**

| Component | Mode |
|-----------|------|
| CutLuy payments | **Production** (`ck_live_…`, real micro-amounts $0.01–$1) |
| Plan checkout | Live CutLuy via `POST /billing/payments` |
| Add-on checkout | Live CutLuy |
| Webhook | `https://api.sandbox.camxora.com/api/v1/billing/webhooks/cutluy` |
| Credit packs | Live CutLuy via `POST /billing/credit-pack/payments` |
| Mock checkout | **Off** (`PLATFORM_DEBUG=false`) |

**Required env vars**

```bash
PLATFORM_CUTLUY_SECRET_KEY=ck_live_...
PLATFORM_CUTLUY_PAYMENT_LINK_ID=...
PLATFORM_CUTLUY_WEBHOOK_SECRET=whsec_...
PLATFORM_CUTLUY_API_BASE_URL=https://cutluy.com
```

**Admin alternative:** Settings → Billing may override CutLuy keys in DB (`billing_config_service`).

---

## 7. Feature completeness matrix

| Feature | API | Admin | User portal | Website | Desktop |
|---------|-----|-------|-------------|---------|---------|
| Auth / sessions | ✅ | — | ✅ | — | ✅ |
| Plans CRUD | ✅ | ✅ | read | public | — |
| Subscriptions / licenses | ✅ | ✅ | partial | — | — |
| Profile add-ons (+2) | ✅ | ✅ | ✅ | pricing table | read-only display |
| Term discounts (6mo/annual) | ✅ | ✅ | checkout | ✅ | — |
| CutLuy plan pay | ✅ | config | ✅ | — | — |
| CutLuy add-on pay | ✅ | — | ✅ | — | — |
| Credit packs pay | ✅ | packs CRUD | ✅ buy + redeem | — | — |
| Redeem codes | ✅ | ✅ | ✅ | — | — |
| Draft/Suno/Image meters | ✅ | ✅ | partial labels | ✅ | ✅ |
| Video/Merge meters | ✅ | ✅ | ✅ | ✅ | ✅ |
| Batch generation | ✅ | — | — | — | ✅ |
| YouTube connect/upload | ✅ | — | partial | — | ✅ |
| Music streaming | ✅ | ✅ | ? | — | — |
| Marketplace | ✅ | partial | via desktop | — | ✅ |
| Finance / COGS | ✅ | ✅ | — | — | — |
| Onboarding wizard | ✅ | — | ✅ | — | portal redirect only |
| Desktop profile create | — | — | ✅ | — | ❌ portal only |
| Plan upgrade w/ proration | ✅ | — | ✅ | — | — |
| Scheduled downgrade | ✅ | — | ✅ | — | — |
| Job queue / workers | ❌ | — | — | — | — |

---

## 8. Prioritized recommendations

### Phase A — Sandbox go-live (1–3 days)

1. Deploy stack per [`SANDBOX_DEPLOYMENT_GUIDE.md`](./SANDBOX_DEPLOYMENT_GUIDE.md)
2. Run migrations through **056**
3. Create admin user; configure plans (2/6/10 × monthly/6mo/annual + add-on rows)
4. Save term discounts → **Sync 6-month & annual prices**
5. Configure CutLuy live keys + webhook
6. Set Suno callback URL to public HTTPS
7. Set `NEXT_PUBLIC_CAMXORA_ENV=sandbox` on website build
8. Build & distribute **sandbox desktop installer** (locked API URL)
9. Run $0.01 plan payment test end-to-end
10. Complete **§10 testing checklist** below

### Phase B — Billing correctness ✅ (implemented 2026-07-15)

1. ~~**B1** Preserve add-ons on plan upgrade~~ (done)
2. ~~**B2** Proration service for upgrades~~ (done)
3. ~~**B3** Add-on term alignment~~ (done)
4. ~~**B4** Automated check: website price == plan row price~~ (done — drift API + Admin banner)

### Phase C — Hardening (ongoing)

1. ~~Credit pack CutLuy fulfillment~~ (done — B7)
2. Durable job queue + `platform_worker`
3. B2 + CDN for streaming
4. ~~WS auth without query token~~ (done — S2 header preferred)
5. Automated backups & uptime monitoring

### Phase D — Production cutover (later)

1. Move from `sandbox.camxora.com` to `app.camxora.com` / `api.camxora.com`
2. `PLATFORM_ENVIRONMENT=production` + full `validate_production_settings`
3. Build **production desktop installer** (separate artifact — do not repoint sandbox installs)
4. Scale VPS or split API/worker per infra plan

---

## 9. Domain strategy

| Purpose | Recommended hostname | Notes |
|---------|---------------------|-------|
| Sandbox marketing | `sandbox.camxora.com` or `www.camxora.com` | Keep prod marketing separate if botifyr unrelated |
| Sandbox user app | `app.sandbox.camxora.com` | Login, billing, onboarding |
| Sandbox admin | `admin.sandbox.camxora.com` | IP restrict or VPN |
| Sandbox API | `api.sandbox.camxora.com` | CORS + Suno + CutLuy webhooks |
| Production (later) | `app.camxora.com`, `api.camxora.com` | Same stack, new env files |

**Do not** point apex `camxora.com` to sandbox until stable; use subdomain first.

---

## 10. Testing checklist (sandbox)

### Web & billing

- [ ] Register → verify email (if SMTP configured)
- [ ] Admin assign plan OR CutLuy checkout completes webhook
- [ ] User portal shows correct quotas (draft/song/image/video/merge)
- [ ] Purchase +2 add-on → pending → create profiles in **portal onboarding** → complete onboarding → active quotas
- [ ] Admin Finance shows payment + COGS after generation
- [ ] Attempt add-on removal with 4 profiles — blocked correctly
- [ ] Plan upgrade via CutLuy — **add-on slots preserved** (B1)
- [ ] Plan upgrade mid-cycle — **prorated amount** charged (B2)
- [ ] Add-on purchase on 6mo/annual sub — term-aligned price (B3)
- [ ] Admin Plans drift banner clear after **Sync 6-month & annual prices** (B4)
- [ ] Schedule downgrade — takes effect at renewal, not immediately (B5)
- [ ] Credit pack purchase via CutLuy — credits minted after webhook (B7)

### Desktop (`camxora_python` sandbox installer)

- [ ] Installer uses locked `api.sandbox.camxora.com` — no API URL field in Settings
- [ ] Login succeeds against sandbox API
- [ ] Dashboard shows credits, drafts, songs, images, **videos**, **merges** remaining
- [ ] Profile page shows active + pending add-on channels
- [ ] Settings → Profiles: **Create profiles in portal** button (no inline create)
- [ ] No profiles → onboarding gate directs to portal; refresh after portal setup
- [ ] Batch generate; Suno callback received
- [ ] Push notifications connect via WS **Authorization header** (S2)

### Ops

- [ ] Rate limit returns 429 under load test (optional)

---

## 11. Document map

| Document | Purpose |
|----------|---------|
| **This file** | Cross-platform gaps & priorities |
| [`BILLING_COSTS_SECURITY_LAUNCH_GAPS.md`](./BILLING_COSTS_SECURITY_LAUNCH_GAPS.md) | Deep billing/security audit (Phase 0–4) |
| [`billing-proration-and-plan-changes.md`](./billing-proration-and-plan-changes.md) | Plan change policy & open implementation items |
| [`PRODUCTION_INFRASTRUCTURE_PLAN.md`](./PRODUCTION_INFRASTRUCTURE_PLAN.md) | Long-term VPS, B2, workers |
| [`SANDBOX_DEPLOYMENT_GUIDE.md`](./SANDBOX_DEPLOYMENT_GUIDE.md) | Step-by-step Ubuntu deploy |

---

*Last updated: 2026-07-15 — Phase B billing gaps (B2–B5, B7), B4 drift check, S2 WS header auth, migration 056.*
