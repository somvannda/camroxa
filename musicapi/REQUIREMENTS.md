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
| Frontend (user + admin) | Next.js (React) — two separate apps: `web-user` (port 3001) and `web-admin` (port 3002) |
| Backend API | Fastify (Node.js / TypeScript) |
| Suno engine | Existing reverse-engineered client (`src/client.ts`) |
| Database | PostgreSQL (local, database `sunoapi`) |
| Queue / async jobs | Redis (BullMQ) — `[PENDING]` (currently in-memory) |
| Auth | Email/password (bcrypt) + JWT, role-based |

The Suno engine is already **proven working** for: auth, billing, lyrics, music generation, sounds, extend, cover, and multi-account sessions. The product layer (users, keys, credits, logs, panels) is built on top of it.

---

## 3. User Panel

Left sidebar navigation + bottom section.

### 3.1 Dashboard `[DONE]`
- Last 24 hours request counts: **success / failed / total**.
- **Remaining credits**.
- **Usage graph** by date for the last 30 days.
- **Real-time success rate**.

### 3.2 Playground `[PARTIAL]`
- `[DONE]` Music generation + Sounds generation (Simple/Custom mode + version selector v4.5-all → v5.5, Loop/BPM/Key for sounds).
- `[PENDING]` Separate sidebar items: Recovery audio, Separate vocals, Generate voice, Check voice, Replace section.

### 3.3 API Key `[DONE]`
- View / generate keys.
- **Safe-spend limits** (per key) — enforced.
- **IP whitelist** (per key) — enforced.
- Note: the raw key is shown only once at creation (only the prefix is stored/retrievable).

### 3.4 API Usages `[PARTIAL]`
- `[DONE]` 24h counts, 30-day series, endpoint breakdown.
- `[PENDING]` Total spend in currency ($).

### 3.5 API Updates `[DONE]`
- Blog posts / changelog (managed in admin).

### 3.6 Logs `[PARTIAL]`
- `[DONE]` Table: time, type/endpoint, model, prompt, status, credits, task id.
- `[PENDING]` Tabs by type (audio, recovery, lyrics, subtitle, wav, vocal-removal, video, voice).
- `[PENDING]` Result on hover (cover image, lyrics, download button).

### 3.7 Billing `[PARTIAL]`
- `[DONE]` Balance remaining, credit packs, API endpoint costs list (view docs).
- `[PENDING]` Payment processing (Buy buttons are placeholders).

### 3.8 Document `[DONE]`
- Public API documentation at `/docs` (no auth required).

### 3.9 Bottom sidebar `[PARTIAL]`
- `[DONE]` Logout.
- `[PENDING]` Get support (Telegram link), Settings, Language.

---

## 4. Admin Panel

### 4.1 Overview dashboard `[PARTIAL]`
- `[DONE]` Total users, requests, success rate, credits consumed.
- `[PENDING]` Revenue ($), Suno accounts health summary.

### 4.2 Suno Accounts (worker pool) — core `[PARTIAL]`
- `[DONE]` Add accounts; tag free/paid; load from DB; auto-pull plan/credits/models (live `billing/info`).
- `[DONE]` Routing rules (model → policy).
- `[PENDING]` Edit/remove accounts; health status (low-credits / captcha-required / disabled).

### 4.3 Users `[DONE]`
- List / search, credits balance, status (active/suspended).
- Manually add/remove credits, ban/unban.

### 4.4 Rate limits & security `[DONE]`
- `[DONE]` Safe-spend limit, per-key IP whitelist.
- `[DONE]` Per-user rate limit (req/min, req/day) — backed by `rate_limits`, enforced in `requireKey`, admin CRUD at `/admin/users/:id/rate-limits`.

### 4.5 Pricing / credit charge `[DONE]`
- Cost per endpoint (and per model — schema supports it; charging uses endpoint-level).
- Credit packs (amount → price). Admin can set/edit/delete.

### 4.6 Billing / Suno credit monitor `[PARTIAL]`
- `[DONE]` Per-account live credits shown in Suno Accounts.
- `[DONE]` Top-up alerts (Suno accounts at/below the configured low-credits threshold surface in the admin panel and push to the ops Telegram channel).
- `[PENDING]` Aggregate summary.

### 4.7 Usage analytics `[PENDING]`
- Per-endpoint, per-model, per-user; success/fail; revenue trends.

### 4.8 Content (API updates / blog) `[DONE]`
- CRUD for blog posts shown in the user panel.

### 4.9 Logs (admin-wide) `[DONE]`
- Same table as user logs, across all users.

### 4.10 Settings & alerts `[DONE]`
- Brand name, docs URL, Telegram support link, languages — stored in `app_settings`, editable at `GET`/`PUT /admin/settings`.
- Alerts: low credits, captcha-locked, failure-rate spike — evaluated at `GET /admin/alerts` and pushed to the ops Telegram channel on state change.

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
- **Durability** `[PENDING]`: jobs/keys/credits must survive restarts → DB + Redis queue (currently in-memory).
- **Security** `[PARTIAL]`: passwords hashed (bcrypt) `[DONE]`, API keys hashed `[DONE]`, Suno cookies encrypted at rest `[PENDING]`.
- **Rate limiting** `[PARTIAL]`: per-key safe-spend + IP whitelist `[DONE]`, per-user rate limit `[PENDING]`.

---

## 10. Phasing

1. **Foundation** — DB schema + user/admin auth + roles. `[DONE]`
2. **User panel** — Dashboard → Playground → API Key → Usage → Logs → Billing → Docs. `[PARTIAL]`
3. **Admin panel** — Suno account pool + routing → users → pricing → analytics → content → settings. `[PARTIAL]`
4. **Hardening** — captcha (2Captcha per-account) `[DONE]`, Redis queue `[PENDING]`.
5. **Full sunoapi.org parity** — all endpoints: upload 3-step, mp4 video, voice ops, MIDI, detail endpoints, captcha-wired everywhere `[DONE]`.

---

## 11. Open decisions

- Currency for credit packs. (default USD)
- Telegram support link / account.
- Language options (default English + which others).
- Whether to migrate existing `accounts.json`/`api-keys.json` into the DB as seed data. (`[DONE]` — `scripts/seed.ts` migrates both.)
