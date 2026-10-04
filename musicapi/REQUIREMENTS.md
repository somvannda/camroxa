# Suno API Platform — Requirements Document (PRD)

> A white-label AI music generation platform built on top of the Suno web interface, offering a REST API to end users (like `docs.sunoapi.org`) with a user-facing panel and an admin panel.

---

## Status legend

- `[DONE]` — implemented and verified.
- `[PARTIAL]` — implemented, some sub-items still pending.
- `[PENDING]` — not yet implemented.

---

## 1. Goal

Build a commercial API that sits on top of multiple Suno accounts and exposes a clean RESTful API to end users. Users pay per request via credits. The platform includes:

- A **user panel** (clone of sunoapi.org) for end users.
- An **admin panel** for the operator to manage Suno accounts, users, pricing, and content.

---

## 2. Architecture `[DONE]`

| Layer | Technology |
|---|---|
| Frontend (user + admin) | Next.js (React) — two separate apps: `web-user` (port 4001) and `web-admin` (port 4002) |
| Backend API | Fastify (Node.js / TypeScript), port 4003 |
| Suno engine | Existing reverse-engineered client (`src/client.ts`) |
| Database | PostgreSQL (local, database `sunoapi`) |
| Queue / async jobs | `[DONE]` Redis (BullMQ) behind `QUEUE_DRIVER` — default `memory` keeps the in-memory LRU/TTL map mirrored to the Postgres `jobs` table; `redis` moves execution onto BullMQ workers while the `jobs` table stays the system of record. Descriptor-backed jobs (the `payload` column, resolved by `src/jobOps.ts`) survive a crashed process — `recoverJobs()` re-queues them and another consumer adopts them. Composite submissions keep the in-process path. Graceful `trackJob()`/`drainJobs()` on shutdown in both modes. |
| Auth | Google OAuth (signup + login) with httpOnly `sunosession` cookie + CSRF Origin check; email/password (bcrypt) + JWT remains for **admin** login only — `POST /auth/register` is intentionally disabled (`405`) |

The Suno engine is already **proven working** for: auth, billing, lyrics, music generation, sounds, extend, cover, and multi-account sessions. The product layer (users, keys, credits, logs, panels) is built on top of it.

---

## 3. User Panel

Left sidebar navigation + bottom section.

### 3.1 Dashboard `[DONE]`
- Last 24 hours request counts: **success / failed / total**.
- **Remaining credits**.
- **Usage graph** by date for the last 30 days.
- **Real-time success rate**.

### 3.2 Playground `[DONE]`
- `[DONE]` Music generation + Sounds generation (Simple/Custom mode + version selector v4.5-all → v5.5, Loop/BPM/Key for sounds).
- `[DONE]` Separate sidebar items: Recovery audio, Separate vocals, Generate voice, Check voice, Replace section. Each has a sidebar nav entry (`layout.tsx`), a dedicated page with a real generation form, and a live backend route (`/me/recovery`, `/me/stems`, `/me/voice-generate`, `/me/voice-validate`, `/me/replace-section`; plus `/me/voice-phrase` and `/me/voice-record` for voice capture). Verified end-to-end on sandbox: every route returns 401 unauthenticated, 400 on missing input, and 402 with no API-key credits (auth + validation + charge gate all wired).

### 3.3 API Key `[DONE]`
- View / generate keys.
- **Safe-spend limits** (per key) — enforced.
- **IP whitelist** (per key) — enforced.
- Note: the raw key is shown only once at creation (only the prefix is stored/retrievable).

### 3.4 API Usages `[DONE]`
- `[DONE]` 24h counts, 30-day series, endpoint breakdown.
- `[DONE]` Total spend in currency ($) — `GET /me/usage` returns all-time `total_credits`/`total_spend` (USD, via the cheapest-active-pack rate); the API Usages page shows a "Total spend" card.

### 3.5 API Updates `[DONE]`
- Blog posts / changelog (managed in admin).

### 3.6 Logs `[DONE]`
- `[DONE]` Table: time, type/endpoint, model, prompt, status, credits, task id.
- `[DONE]` Tabs by type (audio, recovery, lyrics, subtitle, wav, vocal-removal, video, voice) — `/dashboard/logs` filters rows client-side per type; live in-flight jobs from `GET /me/jobs/running` are merged with `GET /me/logs` history.
- `[DONE]` Result on hover (cover image, lyrics, download button) — hovering a row's Result cell reveals a preview card with the clip cover art, lyrics, and a Download MP3 button; clicking opens a playback modal.

### 3.7 Billing `[DONE]`
- `[DONE]` Balance remaining, credit packs, API endpoint costs list (view docs).
- `[DONE]` Payment processing via ChmabaPay (KHQR / ABA PayWay). `POST /payments/chmaba/create` mints a payment for a credit pack (`reference_id`/`idempotency_key` = local transaction id) into the shared `payment_transactions` ledger (`provider='chmaba'`) and returns the KHQR payload plus a same-origin `qr_url` (`GET /payments/chmaba/qr/:id`, an SVG proxy of the provider's public renderer) that the billing page shows inline in a modal — with the provider's hosted `checkout_url` kept as a fallback. `GET /payments/chmaba/status/:id` reconciles against the authoritative check-status endpoint; the public `POST /payments/chmaba/webhook` verifies the `X-ChmabaPay-Signature` HMAC (t/v1, ±5 min) and grants credits exactly once through a guarded `pending → paid` claim. Checkout stays disabled (503) until `CHMABA_API_KEY` + `CHMABA_STORE_ID` are set, and the webhook rejects any delivery it cannot verify while `CHMABA_WEBHOOK_SECRET` is unset.

### 3.8 Document `[DONE]`
- Public API documentation at `/docs` (no auth required).

### 3.9 Bottom sidebar `[DONE]`
- `[DONE]` Logout.
- `[DONE]` Get support — the sidebar shows a "Get Support" link opening the operator-configured Telegram URL (`brand.support_telegram_url`), rendered only when set. The user panel reads branding from the public `GET /settings`.
- `[DONE]` Settings — `/dashboard/settings` edits the display name via `GET`/`PUT /me/profile` (the endpoint the page already expected but which was missing; now backfilled).
- `[DONE]` Language — the sidebar language selector offers the operator-enabled `brand.languages` and persists the choice to `users.language` via `PUT /me/profile`, which rejects any code the operator has not enabled.

---

## 4. Admin Panel

### 4.1 Overview dashboard `[DONE]`
- `[DONE]` Total users, requests, success rate, credits consumed.
- `[DONE]` Revenue ($), Suno accounts health summary — `GET /admin/stats` adds `revenue` + `credits_per_usd` (rate from the cheapest active credit pack, same as `/me/usage` and `/admin/analytics`) and `account_health` (`total`/`healthy`/`disabled`/`low_credits`/`captcha_required`/`captcha_solver`, using the same flags and low-credits threshold as the Accounts page). `captcha_solver` reports whether a 2Captcha key is configured; a captcha-required account is counted `healthy` when a solver is present (it is solved automatically at generation time) and only flagged when there is none.

### 4.2 Suno Accounts (worker pool) — core `[DONE]`
- `[DONE]` Add accounts; tag free/paid; load from DB; auto-pull plan/credits/models (live `billing/info`).
- `[DONE]` Routing rules (model → policy).
- `[DONE]` Edit/remove accounts; health status (low-credits / captcha-required / disabled).

### 4.3 Users `[DONE]`
- List / search, credits balance, status (active/suspended).
- Manually add/remove credits, ban/unban.

### 4.4 Rate limits & security `[DONE]`
- `[DONE]` Safe-spend limit, per-key IP whitelist.
- `[DONE]` Per-user rate limit (req/min, req/day) — backed by `rate_limits`, enforced in `requireKey`, admin CRUD at `/admin/users/:id/rate-limits`.

### 4.5 Pricing / credit charge `[DONE]`
- Cost per endpoint (and per model — schema supports it; charging uses endpoint-level).
- Credit packs (amount → price). Admin can set/edit/delete.

### 4.6 Billing / Suno credit monitor `[DONE]`
- `[DONE]` Per-account live credits shown in Suno Accounts.
- `[DONE]` Top-up alerts (Suno accounts at/below the configured low-credits threshold surface in the admin panel and push to the ops Telegram channel).
- `[DONE]` Aggregate summary — `GET /admin/stats` returns `suno_credits` (`active` = live credits on enabled accounts, `total` = including disabled); the dashboard shows a "Suno Credits" card plus the pool breakdown in the accounts-health panel.

### 4.7 Usage analytics `[DONE]`
- `[DONE]` Per-endpoint, per-model and per-user breakdowns; success/fail counts; daily revenue trends — `GET /admin/analytics?days=N` (admin-only; 7–90 day range, default 30) derived from `usage_logs`, with revenue converted using the same cheapest-active-pack rate as `/me/usage` (task 5.4, `feat/musicapi-usage-analytics`).
- `[DONE]` Admin dashboard at `web-admin/app/admin/analytics` — 7/30/90-day toggle, summary cards (requests, success rate, failed, credits, revenue), daily revenue bar chart, and by-endpoint / by-model / by-user tables.

### 4.8 Content (API updates / blog) `[DONE]`
- CRUD for blog posts shown in the user panel.

### 4.9 Logs (admin-wide) `[DONE]`
- Same table as user logs, across all users.

### 4.10 Settings & alerts `[DONE]`
- Brand name, docs URL, Telegram support link, languages — stored in `app_settings`, editable at `GET`/`PUT /admin/settings`.
- Alerts: low credits and failure-rate spikes — evaluated at `GET /admin/alerts` and pushed to the ops Telegram channel on state change. Captcha is deliberately not an alert: a captcha-required account is healthy while a solver is configured, so it is never actionable.

### 4.11 Audit log `[DONE]`
- Record admin actions (top-up credits, ban user, change pricing) — append-only `audit_logs` table; all admin mutations write an entry (actor id+email, action, target, details JSONB, IP); readable at `GET /admin/audit`.

---

## 5. Account routing logic `[DONE]`

Requests are routed by **model** with a policy:

| Model | Policy |
|---|---|
| `v4.5-all` (free-capable) | prefer **free** account |
| `v5` / `v5.5` | **paid** account only |
| any | fallback to any healthy account |

Rules: pick an account that (1) supports the model, (2) has credits, (3) matches the preferred type, (4) is not captcha-locked/disabled.

- Implemented via `pool.pick(model, policy)` + `routingPolicy(model)` (DB `routing_rules` override, else defaults).

---

## 6. Pricing & credits `[DONE]`

- Operator sets **credit cost per endpoint + model** (admin-configurable, read from `pricing` table).
- Users buy **credit packs**.
- Each request deducts credits from the user's key.
- Operator monitors **Suno-side credits** separately.

Default pricing (1 credit = $0.005):

| Endpoint | Credits | Price |
|---|---|---|
| Music generation (2 songs) | 9 | $0.045 |
| Extend | 9 | $0.045 |
| Cover | 9 | $0.045 |
| Sounds | 9 | $0.045 |
| Stems (separate vocals) | 9 | $0.045 |
| Remaster / Upsample | 9 | $0.045 |
| Mashup (2+ clips) | 9 | $0.045 |
| Add vocals | 9 | $0.045 |
| Add instrumental | 9 | $0.045 |
| Replace section | 9 | $0.045 |
| Create persona (voice clone) | 9 | $0.045 |
| Upload + extend | 9 | $0.045 |
| Upload + cover | 9 | $0.045 |
| Recovery audio | 9 | $0.045 |
| Boost music style | 9 | $0.045 |
| MIDI generate | 9 | $0.045 |
| Voice — phrase | 9 | $0.045 |
| Voice — generate (clone) | 9 | $0.045 |
| Voice — apply / use | 9 | $0.045 |
| Voice — extend | 9 | $0.045 |
| Cover image | 5 | $0.025 |
| MP4 / music-video generate | 5 | $0.025 |
| Lyrics | 2 | $0.010 |
| WAV download | 1 | $0.005 |
| Upload — init (S3 policy) | 1 | $0.005 |
| Upload — register | 1 | $0.005 |
| Voice — validate sample | 1 | $0.005 |
| Voice — record session | 1 | $0.005 |
| Lyrics detail / timestamped | 1 | $0.005 |
| WAV detail | 1 | $0.005 |
| Stems detail | 1 | $0.005 |
| Video / MP4 detail | 1 | $0.005 |
| Cover detail | 1 | $0.005 |
| Subtitle detail | 1 | $0.005 |
| Recovery detail | 1 | $0.005 |
| MP4 detail | 1 | $0.005 |
| MIDI detail | 1 | $0.005 |
| Clip (monolithic) detail | 1 | $0.005 |

Credit packs: `$5 / 1,000` · `$25 / 5,000` · `$100 / 20,000` (flat $0.005/credit).

---

## 7. Data model (PostgreSQL) `[DONE]`

| Table | Purpose |
|---|---|
| `users` | id, email, password_hash, role (user/admin), name, language, status |
| `api_keys` | id, user_id, name, key, credits, safe_spend_limit, ip_whitelist, is_active |
| `credit_transactions` | id, user_id, amount, type (purchase/adjust/spend/refund), description |
| `usage_logs` | id, user_id, api_key_id, endpoint, model, prompt, status, credits_consumed, task_id, result_json |
| `suno_accounts` | id, label, type (free/paid), client_cookie (encrypted), device_id, plan, credits_left, is_active |
| `routing_rules` | id, model, policy (prefer_free/paid_only/any) |
| `pricing` | id, endpoint, model, credit_cost |
| `credit_packs` | id, amount, price, currency, is_active |
| `blog_posts` | id, title, slug, content, published |
| `rate_limits` | id, user_id, requests_per_minute, requests_per_day |

---

## 8. API endpoints (current + planned)

**Current (verified) — full parity:**
- `POST /v1/music` — generate music `[DONE]`
- `POST /v1/sounds` — generate sound effects `[DONE]`
- `POST /v1/lyrics` — generate lyrics `[DONE]`
- `POST /v1/music/extend` — extend clip `[DONE]`
- `POST /v1/music/cover` — style cover of clip `[DONE]`
- `POST /v1/music/stems` — separate vocals/instrumental (stems) `[DONE]`
- `POST /v1/music/remaster` — remaster / upsample quality `[DONE]`
- `POST /v1/music/add-vocals` — add vocals to instrumental clip `[DONE]`
- `POST /v1/music/add-instrumental` — add instrumental backing to vocal clip `[DONE]`
- `POST /v1/music/mashup` — mashup 2+ clips together `[DONE]`
- `POST /v1/music/replace-section` — regenerate a section [start_s, end_s] with new lyrics `[DONE]`
- `POST /v1/music/cover-image` — generate cover art for a clip `[DONE]`
- `POST /v1/persona/create` — create a voice persona / clone from clip `[DONE]`
- `POST /v1/music/wav` — authorize WAV download via `downloadUrl` → signed CDN URL `[DONE]`
- `POST /v1/generate/upload-extend` — continue an uploaded/external audio URL (upload_extend) `[DONE]`
- `POST /v1/generate/upload-cover` — style-cover of an uploaded/external audio URL (cover_infill) `[DONE]`
- `POST /v1/upload/init` — upload step 1: create S3 presigned policy session `[DONE]`
- `POST /v1/upload/register` — upload step 3: register completed S3 upload → processing `[DONE]`
- `GET /v1/upload/status/:id` — poll upload processing status (processing → passed_audio_processing / clip_id) `[DONE]`
- `POST /v1/music/recovery` — recovery audio for a clip `[DONE]`
- `POST /v1/generate/boost` — boost / restyle a clip with new style prompt `[DONE]`
- `POST /v1/music/midi` — generate MIDI arrangement for a clip `[DONE]`
- `POST /v1/mp4/generate` — generate music video (MP4) for a clip `[DONE]`
- `POST /v1/voice/phrase` — Suno Voice op 1: generate reference phrase for cloning `[DONE]`
- `POST /v1/voice/validate` — Suno Voice op 2: validate a voice sample / URL `[DONE]`
- `POST /v1/voice/record` — Suno Voice op 3: create voice-recording upload session `[DONE]`
- `POST /v1/voice/generate` — Suno Voice op 4: create / clone persona from sample `[DONE]`
- `POST /v1/voice/apply` — Suno Voice op 5: generate music using a persona / voice clone `[DONE]`
- `POST /v1/voice/extend` — Suno Voice op 6: extend song using a persona (vox_extend) `[DONE]`
- `GET /v1/task/:id` — job polling (returns {job_id, type, status, clips, result, error}) `[DONE]`
- `GET /v1/credits` — remaining credits `[DONE]`
- `GET /pricing` — public pricing + packs `[DONE]`
- Detail endpoints (per-asset, all `[DONE]`):
  - `GET /v1/clip/:id` — monolithic clip detail (CDN URLs, metadata)
  - `GET /v1/lyrics/:id` — timestamped lyrics for a clip
  - `GET /v1/music/wav/:id` — WAV detail
  - `GET /v1/music/stems/:id` — vocal-separation (stems) detail
  - `GET /v1/music/video/:id` — video / MP4 detail
  - `GET /v1/music/cover/:id` — cover image detail
  - `GET /v1/music/subtitle/:id` — subtitle / captions detail
  - `GET /v1/music/recovery/:id` — recovery audio detail
  - `GET /v1/mp4/:id` — MP4 task detail
  - `GET /v1/music/midi/:id` — MIDI detail
- Webhook callbacks via `callback_url` `[DONE]`

**Planned `[DONE]` (all completed):**
- Upload 3-step flow endpoints (init S3 policy + register): `POST /v1/upload/init`, `POST /v1/upload/register` `[DONE]`
- Timestamped lyrics detail endpoint `[DONE]`
- Recovery audio + details endpoint `[DONE]`
- Boost music style `[DONE]`
- Music video: `POST /v1/mp4/generate` + `GET /v1/mp4/:id` `[DONE]`
- Suno Voice 6 operations: phrase / validate / record / generate / apply / extend `[DONE]`
- MIDI generation + details `[DONE]`
- Per-task-type detail endpoints (lyrics, wav, vocal-separation, video, cover, lyrics, subtitle) `[DONE]`

---

## 9. Non-functional requirements

- **Captcha** `[DONE]`: per-account browser-based 2Captcha integration — `solveCaptchaForAccount(account)` in `src/captcha.ts`; pay-per-solve **only** when `/api/c/check` returns `required=true`. Central entry point `ensureCaptchaToken()` wired into `submitClips()` (covers ALL v2-web/upsample clip ops: generate, sounds, extend, cover, stems, remaster, mashup, addVocals, addInstrumental, replaceSection, uploadExtend, uploadCover) + separately into `createPersona`, `generateCoverImage`, `downloadUrl` (the 3 non-clip ops). Token auto-attached to payload.
- **Durability** `[DONE]`: jobs / keys / credits **survive restarts** — jobs are persisted to the Postgres `jobs` table and recovered on boot (`recoverJobs()`), keys and credits are DB-native. With `QUEUE_DRIVER=redis`, job execution also **survives a process crash**: descriptor-backed jobs (`payload`, `src/jobOps.ts`) are re-queued on boot and adopted by another consumer. Composite submissions remain in-process/single-node until converted (see roadmap R4).
- **Security** `[DONE]`: passwords hashed (bcrypt) `[DONE]`, API keys hashed (sha256) `[DONE]`, Suno cookies encrypted at rest with AES-256-GCM `[DONE]` (`src/cookieCrypto.ts`, `enc:v1:<iv|tag|ciphertext>`, used by `server.ts` and `pool.ts`).
- **Rate limiting** `[DONE]`: per-key safe-spend + IP whitelist `[DONE]`, per-user rate limit `[DONE]` (`enforceUserRateLimit()` in `src/server.ts`, backed by the `rate_limits` table + `rateLimitCache`).

---

## 10. Phasing

1. **Foundation** — DB schema + user/admin auth + roles. `[DONE]`
2. **User panel** — Dashboard → Playground → API Key → Usage → Logs → Billing → Docs. `[DONE]`
3. **Admin panel** — Suno account pool + routing → users → pricing → analytics → content → settings. `[DONE]`
4. **Hardening** — captcha (2Captcha per-account) `[DONE]`, cookie encryption at rest `[DONE]`, per-user rate limits `[DONE]`, Redis queue `[DONE]`.
5. **Full sunoapi.org parity** — all endpoints: upload 3-step, mp4 video, voice ops, MIDI, detail endpoints, captcha-wired everywhere `[DONE]`.

---

## 11. Open decisions

- Currency for credit packs. (default USD)
- Telegram support link / account.
- Language options (default English + which others).
- Whether to migrate existing `accounts.json`/`api-keys.json` into the DB as seed data. (`[DONE]` — `scripts/seed.ts` migrates both.)
