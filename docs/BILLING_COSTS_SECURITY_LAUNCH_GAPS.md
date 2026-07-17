# Billing, Costs, Credits & Security — Launch Gaps Analysis

**Date:** 2026-07-15 (updated: Phase 4 — video/merge meters + credits; auto-merge Electron settings fix; Phases 0–3 remain)  
**Scope:** Cross-platform audit of plan / billing / credits / costs / charges / refunds  
**Surfaces:** `platform_api`, `admin_portal`, `user_portal`, `website`, `camxora_python`, `camxora`  
**Audience:** System owners — what can lose money, what can be abused, what must close before launch

---

## 0. Agreed product model (source of truth for this doc)

These decisions supersede earlier “drafts never burn any plan meter” and “300 songs / 60 images only” wording. **Implementation and Admin Plans must match this section.**

### 0.1 Plan meters (like credit operations)

Plan allowance is managed **the same way as wallet credit ops**: each billable generation **deducts / refunds a plan unit** (or falls through to wallet overage), with a ledger row every time.

| Scope | What |
|-------|------|
| **Monthly** meters | **Account-wide** — both channels share one pool |
| **Daily** meters | **Per channel** — hard safety caps |
| **Fair share** | “Per channel” numbers below are **targets** (half of account), not separate DB counters |

### 0.1.1 Standard Monthly plan (live Admin values)

| Meter | Admin field | Account / month | Per channel (result) | Daily |
|-------|-------------|----------------:|---------------------:|------:|
| **Suno packages** | `monthly_song_limit` | **300** | 1 request → both channels | **10**/channel |
| **Tracks (display only)** | `packages × 2` | **600** | **300 tracks each** (Primary or Secondary) | **10 tracks**/channel |
| **Drafts** | `monthly_draft_limit` | **1260** | **~630** fair share | **21**/channel |
| **Images** | `monthly_image_limit` | **120** | **~60** fair share | **2**/channel |
| **Videos** | `monthly_video_limit` | **300** | shared account pool | **10**/account |
| **Merges** | `monthly_merge_limit` | **30** | shared account pool | **1**/account |
| Profiles | `profile_allowance` | **2** | — | — |
| Price | `price_cents` | **$79** (`7900`) | — | — |
| Cycle | `billing_cycle_days` | **30** | — | — |

**Video/merge daily choice:** sister meters (song/draft/image) use `daily_*_per_channel`. Video product math is **10/day → 300/mo** and **1 merge/day → 30/mo**, so **`daily_video_limit` / `daily_merge_limit` are account-wide** (not per-channel). Documented in migration `048_plan_video_merge_limits`.

**How the numbers are derived (one day × 30, dual channel):**

| Op | Per channel / day | Account / day | × 30 days (account) |
|----|------------------:|--------------:|--------------------:|
| Lyric | 10 | 20 | 600 |
| Title | 10 | 20 | 600 |
| Album | 1 | 2 | 60 |
| **Drafts total** | **21** | **42** | **1260** |
| Suno packages | *(shared)* | **10** requests → **10** tracks/channel | **300** pkgs → **600** tracks |
| Images (BG+TH) | 2 | 4 | **120** |
| **Videos** | *(n/a — account daily)* | **10** | **300** |
| **Merges** | *(n/a — account daily)* | **1** | **30** |

**Critical Admin rule:** do **not** set `monthly_song_limit = 600`. That field is **Suno packages**. Tracks are shown as **×2** in Admin (`≈ Tracks`). Setting 600 packages would allow ~1200 track files.

Migrations: `045_plan_draft_limits`, `046_monthly_plan_standard_quotas`, `048_plan_video_merge_limits` (Monthly row seeded to the table above including video/merge).

### 0.1.2 What burns +1 (plan = credits semantics)

| Plan meter | What burns +1 | Credits / wallet |
|------------|---------------|------------------|
| **Draft** | Each lyric **or** title **or** album LLM call | List price for that op once |
| **Song (package)** | Each Suno `music` submit | **1 music charge per request** — not ×2 for Primary + Secondary |
| **Image** | Each BG **or** TH | List price once each |
| **Video** | Each local track export (`video`) | **3** display credits list; COGS **$0** |
| **Merge** | Each auto-merge concat (`video_merge`) | **10** display credits list; COGS **$0** |

### 0.1.3 Video + merge cost model (major #3)

Local FFmpeg export/merge — **not free**. Same plan_allowance → wallet overage pattern as song/draft/image.

| Op | Plan meter | Daily (account) | Monthly | List credits | ≈ USD @ GCV $0.01 | COGS |
|----|------------|----------------:|--------:|-------------:|------------------:|-----:|
| Video generation | `video` | 10 | 300 | **3** | **$0.03** | **$0.00** |
| Auto merge | `video_merge` | 1 | 30 | **10** | **$0.10** | **$0.00** |

**Typical day (within allowance):** 10 videos + 1 merge → **0 wallet**; meters burn 10 + 1.  
**Same day on wallet overage:** ≈ **40 credits / $0.40** list.  
**API gate:** `POST /generation/video/consume` (+ `/refund` on failure). Desktop Generate Video / Merge / auto-pipeline must call this **before** local work.

**Polish:** **Disabled for launch** (UI hidden + API `403`). Later: lyric list price + **draft** meter.

**Admin Plans form fields:** Suno packages, images, **drafts**, **videos**, **merges**, daily caps, profiles — **not** separate lyric/title/album SKUs. Helper text must say: *1 draft = one lyric, title, or album call; 1 Suno package = Primary + Secondary channel (2 tracks); video = per-track export; merge = concat.*

### 0.2 UX / pipeline (cost control)

| Step | How it starts | Auto inside step? |
|------|----------------|-------------------|
| Batch create → lyric / title / album | Generate (batch) | Yes — drafts run for the batch |
| Suno | **Right-click → Suno** (manual fire) | Yes once started |
| Images | **Right-click → Image** | Yes once started (album-level BG/TH) |
| Video | **Right-click → Video** | Yes once started |

Auto-GSuno / Auto-Image on batch create: **off by default** (or removed from create) so expensive steps are intentional. If user never right-clicks Suno after drafts, they still **consumed draft allowance** — their choice; platform COGS is bounded by the draft meter.

### 0.3 Wallet / plan parity

| Path | Behavior |
|------|----------|
| Under plan draft/song/image remaining | `billing=plan_allowance`, wallet **$0**, meter **+1**, ledger list/COGS |
| Meter exhausted | Soft monthly overage → **wallet** at list price (hold **before** provider); or hard-block if no balance |
| Failure after deduct | **Refund that meter unit** (+ wallet if charged); keep COGS visible (`platform_absorb` / prior debit) |

### 0.4 What we explicitly rejected (for now)

- ❌ Unlimited free drafts while “songs remaining” (old C5 — closed by **draft meter**).  
- ❌ Separate Admin SKUs for lyric/title/album (complexity; use one **draft** pool).  
- ❌ Shipping polish in the first launch cut.  
- ❌ Putting **600** in `monthly_song_limit` (that would mean 600 Suno requests). Use **300 packages**; tracks = ×2 display.  
- ❌ Charging wallet **×2** for Primary + Secondary channel — credits match plan: **1 music** per Suno request.  
- ❌ Treating CutLuy sandbox as a blocker — use live micro-pays + mock only when `debug=true` (see §13).

---

## 1. Executive summary

**Target + partially shipped:** dual-channel Monthly standard (§0.1.1) including video/merge; draft + song + image + **video + merge** meters like credits; polish off; stepped right-click for Suno/image/video.

**Already closed in code/DB (verify after migrate):** draft meter; polish disabled; unverified credit purchase disabled; Monthly quotas 300 / 1260 / 120 / **300 video / 30 merge** (+ dailies); prepaid image billing; fail/retry absorb; desktop stepped pipeline; **video/merge pricing seed (3 / 10 cr, COGS 0)** + consume API; Electron auto-merge now reads **live settings** (was hardcoded `DEFAULT_SETTINGS.autoMergeAfterVideo=false`).

**Still open before launch (critical highlighted):**

| # | Gap | Severity |
|---|-----|----------|
| 1 | CutLuy **live keys + KHQR micro-pay**; pack purchase stays closed | **Critical** (ops) |
| 2 | Default JWT / `debug=true` / mock if left on in prod | **High** (ops discipline) |
| 3 | User portal may still under-surface **video/merge remaining** vs draft/song/image | **Medium** |
| 4 | Electron merge refund-on-skip still weaker than camxora_python | **Low–Medium** |
| 5 | Full KMS envelope encryption optional | Low |
| 6 | WS query-string tokens on desktop | Medium (H8 residual) |

### Must close before launch (ordered)

| # | Gap | Risk | Severity |
|---|-----|------|----------|
| 1 | `POST /credits/purchase` mints credits from any client `payment_ref` | Infinite free wallet → free AI | **Critical** *(API disabled; keep closed until CutLuy)* |
| 2 | ~~Batch `auto_gen_image` “prepaid” skips wallet & plan ledger~~ | — | **Done** (Phase 1) |
| 3 | ~~Suno callbacks weakly auth’d; FAILED after SUCCESS can refund~~ | — | **Done** (Phase 0) |
| 4 | ~~Generation rate limits exist but are **not wired** on AI routes~~ | — | **Done** (Phase 0) |
| 5 | ~~No draft plan meter~~ | — | **Done** |
| 5b | ~~Polish exposed~~ | — | **Done** |
| 5c | ~~Video/merge free / ungated~~ | Free local pipeline bypasses metered flow | **Done** (Phase 4: meters + consume API + desktop gate) |
| 5d | ~~Auto-merge never fires after batch video (Electron)~~ | UX broken | **Done** (Phase 4: pass live `settings` / `autoMerge`) |
| 6 | ~~Soft monthly overage + charge-after-provider (images)~~ | — | **Done** (Phase 2) |
| 7 | ~~Fail → refund → unlimited retry~~ | — | **Done** (Phase 1) |
| 8 | ~~Finance omits subscription cash; understates COGS~~ | — | **Done** (Phase 2) |
| 9 | Default JWT / debug mock checkout if left on in prod | Forge identity / free plan | **High** |
| 10 | ~~Direct `/generation/draft` undercharges vs batch~~ | — | **Done** (Phase 2) |
| 11 | ~~Desktop still Auto-GSuno / Polish / no stepped right-click pipeline~~ | — | **Done** (Phase 1) |

---

## 2. How money is supposed to work (target model)

### 2.1 Actors & money flows

```text
Customer ──pays──► Subscription and/or Credit packs / redeem
                         │
                         ▼
              platform_api enforces
         ┌────────────────┴────────────────┐
         │ Plan meters: draft / song / image│ Wallet credits (overage / Lifetime)
         │ +1 unit, ledger plan_allowance   │ debit list credits × GCV
         └────────────────┬────────────────┘
                          ▼
               AI providers (YOUR keys)
                          ▼
               You pay provider invoices = true COGS
```

### 2.2 Plan burn table (target + current enforcement)

| Operation | Plan meter +1 | Customer $ under allowance | Owner COGS logged? | Launch UI |
|-----------|---------------|----------------------------|--------------------|-----------|
| Lyric | **Draft** | $0 | Yes | Via batch Generate |
| Title | **Draft** | $0 | Yes | Via batch Generate |
| Album | **Draft** | $0 | Yes | Via batch Generate |
| Polish | *(disabled)* | — | — | **Hidden; API 403** |
| Suno `music` (Primary + Secondary) | **Song package** (not ×2) | $0 | Yes | Right-click → Suno |
| BG / TH | **Image** | $0 if covered | Yes | Right-click → Image |
| Video export | **Video** | $0 if covered; else 3 cr | Yes (list; COGS 0) | Right-click → Video / auto-video |
| Auto merge | **Merge** | $0 if covered; else 10 cr | Yes (list; COGS 0) | Auto after batch (≥2 MP4s) |

**GCV (live):** 1 display credit = **$0.01**.  
**Suno pack COGS:** 12 Suno credits × ($50 / 10k) = **$0.06** per **request** (covers both Primary + Secondary channel tracks).  
**Video/merge COGS:** **$0.00** (local). List prices: video **3** · merge **10** (seed `credit_pricing` ai_service=`local`).  
**Full Monthly burn ballpark (if they use the whole package):** 300 × $0.06 Suno + draft LLM + 120 × ~$0.01 images + video/merge list visibility ≲ plan price depending on providers — track in Finance.

### 2.3 Refund intent

| Failure | Customer | Owner |
|---------|----------|-------|
| Draft fail (after draft unit deducted) | **Draft unit restored**; wallet refund if charged | Keep ledger / `platform_absorb` |
| Suno fail after song deduct | **Song unit restored**; wallet refund if charged | Keep music cost row + failed marker |
| Image fail after reserve | **Image unit restored** | Absorb COGS if provider called |

---

## 3. Cross-surface map

| Surface | Role in money path | Trust level |
|---------|-------------------|-------------|
| **platform_api** | Sole enforcer of quota, wallet, ledger, provider calls | **Must be airtight** |
| **admin_portal** | Plans (**draft** + song + image), pricing, GCV, finance, keys | Privileged |
| **user_portal** | Billing, credits redeem, usage (show **draft/song/image** remaining) | Untrusted UI |
| **website** | Public plans / CTA | Marketing only |
| **camxora_python** | Generate drafts; right-click Suno/image/video; **no polish** | Untrusted client |

**Rule:** Never trust desktop or browser for billing. If the API allows it, curl can do it.

---

## 4. Findings by severity

### CRITICAL — close before launch

#### C1. Credit pack purchase without payment verification

- **Where:** `platform_api/routers/credits.py` → `POST /credits/purchase`; `credit_service.purchase_pack`
- **Close:** Disable until CutLuy-backed fulfillment; never trust client `payment_ref`.

#### C2. Batch “prepaid” images skip wallet and undercount plan COGS

- **Where:** `image_job_service.py` — `prepaid = batch.auto_gen_image`
- **Close:** Escrow/deduct for real; ledger every image; no free overage without wallet hold.

#### C3. Weak / forgeable Suno callbacks + refund after success — DONE (Phase 0)

- HMAC secret configured → signature **required** (no IP/debug fallthrough).
- Callback ignores SUCCESS→FAILED task downgrades; `handle_suno_task_update` skips refund after `suno_success` (and duplicate failed).
- Ops: set `PLATFORM_SUNO_CALLBACK_HMAC_SECRET` (required when `PLATFORM_ENVIRONMENT=production`).

#### C4. Rate limits not wired on AI routes — DONE (Phase 0)

- Wired via `enforce_rate_limit` / `enforce_rate_limit_for_endpoint` on generation draft/suno/image, batch create + retries, channel-setup onboarding AI.
- Path map covers `/batches`, retry-draft/retry-suno, channel-setup generate-* (logo/covers → `image`).

#### C5. Draft plan meter — DONE

- Lyric/title/album → `draft` quota_op; +1 / refund; Admin fields + Monthly **1260** / daily **21**.
- Remaining polish: preflight Generate on draft remaining in desktop; user portal labels for draft/song/image.

#### C5b. Polish disabled — DONE

- API `403 POLISH_DISABLED`; desktop polish UI hidden / handler blocked.
- **Reopen later:** lyric list price + **draft** unit.

---

### HIGH

#### H1. Soft monthly overage without balance hold (esp. images) — DONE (Phase 2)

Atomic wallet hold before provider via `reserve_and_hold_before_provider` (images); plan path still reserves meter only.

#### H2. Fail → refund → unlimited retry
Daily fail budget / cool-down / stake after N absorbs.

#### H3. Prepaid image retries skip re-charge
Align with C2 + right-click image fire.

#### H4. Finance missing subscription cash & incomplete COGS — DONE (Phase 2)

Admin usage summary includes `billing_payments` cash, `platform_absorb`, and draft/song/image plan list units; Finance profit = sub cash + wallet − COGS.

#### H5. Direct `/generation/draft` undercharges vs batch — DONE (Phase 2)

Shared `deduct_split_draft_billing` — lyric/title/album each burn draft meter + list price.

#### H6. Admin unlimited / free assign / adjust — DONE (Phase 3)

Active paid recurring plans reject null monthly song/draft/image meters. Large credit adjusts (≥ `PLATFORM_ADMIN_ADJUST_DUAL_CONTROL_CREDITS`, default 1000) queue for a second admin (`admin_pending_ops` / migration 047).

#### H7. Prod misconfig: default JWT, `debug=true`, mock checkout — DONE (Phase 0 gates)

- `validate_production_settings()` fails fast when `PLATFORM_ENVIRONMENT=production|prod` with `debug=true`, insecure/default JWT, or missing callback HMAC.
- Mock checkout remains debug-only (`_ensure_mock_checkout_allowed`).

#### H8. Tokens in JSON bodies — PARTIAL (Phase 3)

Access TTL default **15 min**; refresh already rotates; **reuse of a revoked refresh token revokes all sessions**. Remaining: prefer WS auth without query-string tokens (desktop).

#### H9. Pricing / COGS drift — DONE (Phase 2)

`set_price` / create / update / approve reject cost > sell; music cost basis ≥ 6 display credits ($0.06).

#### H10. Desktop pipeline ≠ agreed model
- Default **off** Auto-GSuno / Auto-Image on batch create (or remove).  
- After drafts: history/context **right-click → Suno / Image / Video**.  
- Remove polish entry points.  
- Preflight Generate on **draft** (+ profile readiness), not only song package.

---

### MEDIUM

| ID | Gap | Close |
|----|-----|-------|
| M1 | ~~User portal shows plan remaining as “credits”~~ | **Done** — draft/song/image remaining + plan_allowance / wallet / platform_absorb ledger chips |
| M2 | Batch preflight race | Hold total draft (and later song/image) cost |
| M3 | Double-refund Suno FAILED race | Conditional UPDATE + unique refund key |
| M4 | Onboarding AI absorbed after paid | Caps + rate limit + COGS budget |
| M5 | 100% redeem unlocks full plan | Strict redemptions + alerts |
| M6 | Website weak plan CTA | Link → portal `plan_id` |
| M7 | CORS + credentials prod discipline | Explicit allowlist |
| M8 | Plan edit audit weak | Diff on draft/song/image limits |
| M9 | ~~Static key-pool salt~~ | **Done (per-row salt)** — v2 ciphertext embeds random salt; legacy static salt still decrypts. Full KMS envelope optional later. |
| M10 | ~~Draft/Polish gating~~ | **Polish: disable.** Draft: gate on draft meter |

---

### LOW / hygiene

- Show list/COGS on amount-0 plan rows.  
- Normalize `music` vs `music_generation`.  
- Alert on forge-ish callbacks.  
- Streaming public routes must not leak unpaid private assets.

---

## 5. Abuse scenarios (vs target model)

### Scenario A — Free credit mint
Still Critical until C1 closed.

### Scenario B — Subscriber draft drain
**Mitigated:** draft meter (**1260**/mo, **21**/day/ch). Auto-GSuno off only burns drafts up to that cap.  
**Polish spam:** closed (disabled).

### Scenario C — Fail-farm
Still High until H2; refunds stay correct for fairness.

### Scenario D — Callback refund theft
Still Critical until C3.

### Scenario E — Stolen JWT
Still Critical until C4 + H8.

**Scenario F — Soft overage empty wallet**
Mitigated (Phase 2): image soft overage holds wallet before provider.

### Scenario G — Hidden polish API (new)
UI hidden but `POST /polish-lyrics` left open → scripts still burn draft/lyric.  
**Close with C5b:** reject API, not only hide button.

---

## 6. Owner COGS waste

| Waste source | Mitigation under §0 |
|--------------|---------------------|
| Unlimited drafts under song cover | **Draft meter** (C5) |
| Polish loops | **Disable polish** (C5b) |
| Accidental full auto Suno/image | Right-click fire; auto flags off (H10) |
| Suno/image fail after deduct | Refunds + fail budget (H2) |
| Broken prepaid images | C2 |
| Underpriced music | H9 |

**Full-burn ballpark (Standard Monthly, full use):**  
Revenue **$79** − (1260 draft LLM calls + **300 × $0.06** Suno + **120 × ~$0.01** images). Drafts are capped; do not set song packages to 600 by mistake.

---

## 7. Security improvements (permission to spend AI)

1. Entitlement (**draft/song/image unit or wallet hold**) **before** every provider call.  
2. Kill free mint (C1); mock only in debug (H7).  
3. Authenticate callbacks (C3).  
4. Rate-limit all AI surfaces (C4).  
5. **Ship draft meter + disable polish** (C5 / C5b) — closes the gap-in-gap vs older song-package-only story.  
6. JWT hygiene (H7/H8).  
7. Server-only keys.  
8. Admin dual-control.  
9. Idempotent payments and refunds.  
10. Alerts on absorb spikes / zero-dollar fulfills / polish 403 storms (if someone probes).

---

## 8. Surface checklist (aligned to §0)

### platform_api
- [x] Disable unverified `/credits/purchase`
- [x] Fix prepaid image escrow + ledger
- [x] Lock Suno callbacks + refund FSM *(fail-closed HMAC; SUCCESS→FAILED no refund)*
- [x] Wire rate limits on AI routes *(generation / batch / channel-setup)*
- [x] **Add draft plan meter**; lyric/title/album increment + refund draft *(migration 045 + enforcement — restart API / migrate)*
- [x] **Disable `/polish-lyrics`** (403 Forbidden)
- [x] Align `/generation/draft` with batch + draft meter
- [x] Charge/hold before provider on overage
- [x] Cap fail/retry budgets
- [x] Finance: subscription + absorb + draft/song/image COGS
- [x] Boot guards for JWT/debug/mock *(production env fail-fast)*
- [x] Admin dual-control for large credit adjusts *(migration 047)*
- [x] Per-row key encryption salt *(legacy decrypt retained)*
- [x] Refresh-token reuse → revoke all sessions; access TTL 15m
- [x] Abuse alerts → Admin WS (`admin:abuse_alert`)
- [x] **Video + merge plan meters** (`monthly_video_limit` / `monthly_merge_limit` + account daily) *(migration 048)*
- [x] **`POST /generation/video/consume` (+ refund)** — plan_allowance or wallet at 3 / 10 credits
- [x] Seed `local`/`video` + `local`/`video_merge` list prices; public usage-rates include both
- [~] CutLuy webhook plan fulfill *(needs live webhook secret + keys — pack purchase still closed)*

### admin_portal
- [x] Plan form: **draft** limit (+ daily) alongside songs/images
- [x] Plan form: **video** + **merge** monthly + account daily *(helpers like Suno/drafts/images)*
- [x] Helper text: “1 draft = one lyric, title, or album call”
- [x] Finance includes subscription revenue
- [x] No polish pricing SKU required for launch
- [x] Rate-limit settings actually enforce *(wired on AI routes; Admin rate-limits configs apply via Redis cache)*

### user_portal
- [x] Show **draft / song / image** remaining (not “credits” for songs)
- [~] Show **video / merge** remaining *(quota-status API fields shipped; portal UI may still need labels)*
- [x] Usage: plan_allowance vs wallet vs platform_absorb
- [x] No unpaid pack purchase UX *(redeem-only; API purchase stays 403)*

### website
- [x] Live public plans; CTA with `plan_id` *(packages ×2 tracks, drafts, images, **video, merge** from `PublicPlan`)*
- [x] Marketing copy + public usage-rates: draft / Suno / image / **video / merge**

### camxora_python / camxora
- [x] **Hide/remove Polish** entirely *(UI hidden + handler disabled)*
- [x] Generate consumes **draft** (preflight draft remaining)
- [x] Auto-GSuno / Auto-Image **off by default** (or removed)
- [x] Right-click: **Suno**, **Image**, **Video** continue steps
- [x] Video/merge consume before export/merge *(automation + Video page)*
- [x] Electron auto-merge uses **live Music settings** (not `DEFAULT_SETTINGS`)
- [x] Retry respects meters + fail budgets
- [~] Secure tokens; no token logs *(AppLogger redacts tokens; WS `?token=` still present — follow-up)*

---

## 9. Launch gate (ordered, no gap-in-gap)

### Phase 0 — Stop bleeding
1. [x] Disable `/credits/purchase` *(API reject until CutLuy)*.  
2. [x] Suno callback auth + SUCCESS→FAILED refund guard *(HMAC fail-closed; no refund after `suno_success`)*.  
3. [x] Prod: `debug=false`, real JWT secret, mock off *(fail-fast via `PLATFORM_ENVIRONMENT=production` + `validate_production_settings`)*.  
4. [x] Wire rate limits *(generation, batch create/retry, channel-setup AI)*.  
5. [x] **Disable polish** (API + desktop) — removes a whole burn surface.

**Ops to set for production:** `PLATFORM_ENVIRONMENT=production`, `PLATFORM_DEBUG=false`, `PLATFORM_JWT_SECRET` (≥32 unique chars), `PLATFORM_SUNO_CALLBACK_HMAC_SECRET`.

### Phase 1 — Meter drafts like credits + pipeline
6. [x] DB/Admin: `monthly_draft_limit` (+ daily).  
7. [x] Enforcement: lyric/title/album → draft +1 / refund.  
8. [x] Preflight + Usage labels.  
9. [x] Desktop: no polish; Generate → drafts; right-click Suno/image/video; auto flags off.  
10. [x] Fix image prepaid / hold before provider.  
11. [x] Fail/retry budgets.

### Phase 2 — Money truth
12. [x] Finance: sub cash + absorb + all meters’ list COGS.  
13. [x] Pricing sync gate / GCV *(cost > sell blocked; music cost ≥ 6 cr)*.  
14. [x] Align direct draft route with batch.  
15. [x] Soft overage wallet hold before provider (images).

### Phase 3 — Hardening
16. [x] Admin dual-control (large credit adjust queue + second-admin approve), per-row key salt, refresh reuse revoke-all, abuse alerts (absorb / polish probe / redeem burst / zero-dollar). Paid recurring plans forbid null monthly meters.  
17. [ ] Optional later: re-enable polish on draft meter + lyric price. *(explicitly deferred — keep API 403)*  
18. [~] CutLuy signed webhook scaffold for **plan** `billing_payments` fulfillment (`POST /api/v1/billing/webhooks/cutluy`); **`/credits/purchase` remains closed** until a verified pack product exists + live `ck_live_…` + webhook secret micro-pay proof.  
19. [x] User portal: plan_allowance vs wallet vs platform_absorb usage labels + filters.

### Phase 4 — Video / merge billing + auto-merge reliability
20. [x] Plan columns + Monthly seed: `monthly_video_limit=300`, `monthly_merge_limit=30`, `daily_video_limit=10`, `daily_merge_limit=1` *(account-wide daily)*.  
21. [x] Credit pricing seed: `local`/`video`=3 cr, `local`/`video_merge`=10 cr, COGS $0.  
22. [x] Consume/refund API + desktop gates (camxora_python automation + Video page; Electron coordinator).  
23. [x] Admin Plans UI + website PublicPlan features for video/merge.  
24. [x] Electron auto-merge: pass live `settings` / `autoMerge` into `startPipelineExport` (root cause was `parseDefaultSettings()` → always false).

---

## 10. Already in good shape (do not regress)

- Admin Plans sole source of truth (no seed 420).  
- **Standard Monthly quotas live** (§0.1.1): 300 pkgs / 1260 drafts / 120 images / **300 videos / 30 merges**; daily song/draft/image per-channel 10/21/2; **video/merge account daily 10/1**.  
- Draft meter + polish disabled + unverified pack purchase disabled.  
- Admin UI: Suno packages + ≈Tracks (×2); credits = 1 music / package.  
- Video/merge not free; consume before local export.  
- Suno charge-before-call + stash/refund pattern.  
- Provider keys server-side.  
- Website live plans.  
- Failure refunds + `platform_absorb` direction.  
- Finance provider/model-aware COGS for channel cover.

**Do not regress:** putting **600** into `monthly_song_limit` (that means 600 Suno requests). Tracks are display-only ×2.

---

## 11. Glossary

| Term | Meaning |
|------|---------|
| **GCV** | USD per display credit (`$0.01`) |
| **plan_allowance** | Covered by subscription; wallet $0; meter still +1 |
| **platform_absorb** | Owner pays failed/unbillable provider cost; customer restored |
| **Draft meter** | Account pool; +1 per lyric **or** title **or** album; Monthly **1260** |
| **Song / Suno package** | Account pool; +1 per Suno request; Monthly **300** (= **600** tracks display) |
| **Tracks** | Display only = packages × 2 (Primary + Secondary channel); **not** a separate counter |
| **Image meter** | Account pool; +1 per BG/TH; Monthly **120** |
| **Video meter** | Account pool; +1 per track export; Monthly **300**; daily **10 account-wide** |
| **Merge meter** | Account pool; +1 per auto-merge; Monthly **30**; daily **1 account-wide** |
| **Credits music** | **1 charge per Suno package** (same as plan burn) |
| **Credits video/merge** | **3 / 10** display credits list (overage); COGS **$0** |
| **Polish** | Launch: **disabled**. Later: lyric price + draft unit |
| **Stepped pipeline** | Drafts on Generate; Suno/image/video via right-click |
| **Soft overage** | Past monthly meter → wallet (with hold); daily hard |
| **Prepaid images** | ~~Broken escrow~~ — **fixed in Phase 1** (same bill path as non-prepaid) |
| **Standard Monthly** | $79 · 300 pkgs · 1260 drafts · 120 images · **300 videos · 30 merges** · daily/ch 10/21/2 · video/merge daily 10/1 · 2 profiles |

---

## 12. Consistency matrix (no gap-in-gap)

| Earlier / wrong idea | Status vs §0 |
|----------------------|--------------|
| Song package = lyric+title+album+Suno as *workflow* | Still true |
| Only Suno burns *song package* units | Still true (**300**/mo) |
| Admin song limit = **600** (tracks) | **Wrong** — store **300 packages**; display tracks ×2 |
| Drafts free under song remaining | **Rejected** — draft meter **1260** |
| Drafts default 900 / images 60 | **Superseded** — **1260** drafts / **120** images |
| Polish = lyric charge | **Off** at launch |
| Individual lyric/title/album plan fields | **Rejected** — one draft pool |
| Right-click continue Suno/image/video | **Adopted** (H10; desktop landed Phase 1) |
| Credits charge ×2 for Primary + Secondary | **Rejected** — **1 music** per Suno request |
| CutLuy sandbox required | Softened — invite/redeem; live micro-pay (§13) |
| Website “songs” without draft meter | **Superseded** — live plans + usage-rates use packages / drafts / images (§8) |

---

## 13. Payments / CutLuy (context)

- CutLuy ([cutluy.com/docs](https://cutluy.com/docs)): **live Bakong KHQR only**, no sandbox; Free **100 txs/month**; need store **payment link** + `ck_live_…`; webhooks + signature verify.  
- App mock checkout: **`debug=true` only** — not public launch.  
- Pre-CutLuy: Admin license assign + redeem codes; **never** open unverified `/credits/purchase`.  
- Soft-launch: real $0.01–$1 KHQR tests against live CutLuy Free tier.  
- **Shipped scaffold (Phase 3):** `POST /api/v1/billing/webhooks/cutluy` verifies `X-CutLuy-Signature` and fulfills matching **plan** `billing_payments`. Requires `PLATFORM_CUTLUY_WEBHOOK_SECRET` (or Admin Settings → CutLuy webhook secret). Pack mint via `/credits/purchase` stays **403** until a verified pack product is wired.

---

## 14. Document control

| Item | Value |
|------|-------|
| Source audits | Cross-read 2026-07-15 |
| Product decisions | Dual-channel Monthly standard; draft meter; polish off; 1 credit music / Suno package; stepped pipeline |
| Live plan standard (§0.1.1) | **$79 · 300 Suno pkgs (600 tracks) · 1260 drafts · 120 images · 300 videos · 30 merges · daily/ch 10/21/2 · video/merge daily 10/1 · 2 profiles** |
| Migrations | `045_plan_draft_limits`, `046_monthly_plan_standard_quotas`, `047_admin_pending_ops`, `048_plan_video_merge_limits` |
| Video costs (§0.1.3 / major #3) | video **3 cr / $0.03**; merge **10 cr / $0.10**; COGS $0; ~40 cr/$0.40 for 10+1 on overage |
| Next action | **Ops: run migration 048 + restart API**; Admin verify Monthly video/merge fields; CutLuy live keys + KHQR micro-pay; portal video/merge remaining labels; optional polish re-enable; optional KMS / WS token hardening |

*Analysis artifact — §0 is the product contract; keep code/Admin/docs aligned to it.*
