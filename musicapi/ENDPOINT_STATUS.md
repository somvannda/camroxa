# Endpoint Status Matrix — musicapi

> **Report date: 2026-09-30** · **Tree:** `g:\Developments\Projects\Camxora\MusicGenerator-musicapi-integration\musicapi`
> **Branch:** `integration/musicapi-phase2` · **DB:** PostgreSQL `sunoapi` (migrations `0001`–`0019`)
>
> **Ground truth this revision:** Fastify's own route inventory (`app.printRoutes()`) + an automated
> reachability/auth/validation sweep over **every** registered route against the locally running
> Core API on port **4003**.
>
> Reproduce with: `npm run serve` (one terminal) then
> `npx tsx scripts/smoke-test-reachability.ts` — see
> [smoke-test-reachability.ts](file:///g:/Developments/Projects/Camxora/MusicGenerator-musicapi-integration/musicapi/scripts/smoke-test-reachability.ts).
>
> Supersedes the 2026-09-09 report, which was written against a different tree
> (`e:/Development/SunoAPI`) and undercounted the surface as "100 registered routes".

---

## What was actually measured

Two axes matter, and **they are not the same thing**. The 2026-09-09 report only measured axis B.

| Axis | Question | How it was measured on 2026-09-30 |
|---|---|---|
| **A — Reachability** | Is the route registered, does it enforce auth, and does it validate input? | Sweep hit all 205 routes with **no credentials** (T1) and, for every `POST` on the public surfaces, **again with a valid API key + empty body** (T2). |
| **B — Live Suno correctness** | Does a real job actually generate → poll → download from live Suno? | **NOT re-measured this revision.** Requires spending real Suno quota/credits. Historical 2026-09-09 evidence is retained below and marked as such. |

**T1 / T2 results (2026-09-30):**

```
ROUTES=205
T1 status histogram: {"200":6,"400":2,"401":194,"404":1,"405":1,"503":1}
T2 (valid key + {} on POST /v1/* and /api/v1/*): 62 checks, all 400 — 0 mismatches
NOT-ROUTED (T1 404): 1  →  POST /payments/khqr/confirm-mock/:id
```

Interpretation: **194 of 205 routes are auth-gated** and answer `401` without credentials. Every
one of the **62 public-API `POST` routes** returns a clean `400` on an empty body with a valid key —
no `500`s, no route shadowing, no unauthenticated fall-through on the revenue surface.

---

## Legend

| Status | Meaning |
|--------|---------|
| ✅ **VERIFIED** | Live evidence this cross-check: registered, correctly gated, correct status on the probe. |
| 🟡 **ROUTED (shallow)** | Reachable and gated, but only a `401`/`400` was observed — no deep success path exercised. |
| ⚠️ **UNPROVEN (axis B)** | Axis A passes, but no live-Suno success path has been re-run on this tree. Assumed working until proven. |
| 🔒 **INTENTIONAL** | Non-`200` is deliberate; documented in source. |
| ⛔ **NOT-ROUTED** | Appears in the route table but a live request does not reach a handler. |

---

## 1. Ops / Health (2 routes)

| # | Endpoint | Method | Status | Evidence |
|---|----------|--------|--------|----------|
| 1.1 | `/health` | GET | ✅ VERIFIED | `200` unauthenticated. Reports account-pool healthy count (`accounts=2`). |
| 1.2 | `/metrics` | GET | 🟡 ROUTED (shallow) | **`401` — auth-gated.** If an external scraper (Prometheus) is intended to read this, it needs a token or a loopback exemption. Confirm intent. |

---

## 2. User Dashboard `/me/*` (54 routes)

`401` without a session cookie/JWT for all 54. This is the surface the `web-user` app drives.

### 2.1 Account & API keys (3)

| # | Endpoint | Method | Status |
|---|----------|--------|--------|
| 2.1.1 | `/me/keys` | GET, POST | 🟡 ROUTED (shallow) |
| 2.1.2 | `/me/keys/:id` | PUT | 🟡 ROUTED (shallow) |
| 2.1.3 | `/me/profile` | GET, PUT | 🟡 ROUTED (shallow) |

### 2.2 Generation (music) (14)

| # | Endpoint | Method | Status |
|---|----------|--------|--------|
| 2.2.1 | `/me/generate` | POST | ⚠️ UNPROVEN — **the P0 revenue path** |
| 2.2.2 | `/me/generate/upload-extend` | POST | ⚠️ UNPROVEN |
| 2.2.3 | `/me/generate/upload-cover` | POST | ⚠️ UNPROVEN |
| 2.2.4 | `/me/generate/boost` | POST | ⚠️ UNPROVEN |
| 2.2.5 | `/me/music` | POST | ⚠️ UNPROVEN |
| 2.2.6 | `/me/music/extend` | POST | ⚠️ UNPROVEN |
| 2.2.7 | `/me/music/cover` + `/me/music/cover-image` + `GET /me/music/cover/:id` | POST, POST, GET | ⚠️ UNPROVEN |
| 2.2.8 | `/me/music/remaster` | POST | ⚠️ UNPROVEN |
| 2.2.9 | `/me/music/replace-section` · `/me/replace-section` | POST | ⚠️ UNPROVEN |
| 2.2.10 | `/me/music/recovery` · `/me/recovery` + `GET /me/music/recovery/:id` | POST, POST, GET | ⚠️ UNPROVEN — 9/9 FAILED rows on 2026-09-09 (P1 audit, never closed) |
| 2.2.11 | `/me/music/add-vocals` · `/me/music/add-instrumental` | POST | ⚠️ UNPROVEN |
| 2.2.12 | `/me/music/mashup` | POST | ⚠️ UNPROVEN |
| 2.2.13 | `/me/music/midi` + `GET /me/music/midi/:id` | POST, GET | ⚠️ UNPROVEN |
| 2.2.14 | `/me/music/wav` + `GET /me/music/wav/:id` | POST, GET | ⚠️ UNPROVEN |

### 2.3 Generation (other media) (7)

| # | Endpoint | Method | Status |
|---|----------|--------|--------|
| 2.3.1 | `/me/mp4/generate` + `GET /me/mp4/:id` | POST, GET | ⚠️ UNPROVEN — FAILED rows on 2026-09-09 |
| 2.3.2 | `/me/sounds` | POST | ⚠️ UNPROVEN |
| 2.3.3 | `/me/persona-create` | POST | ⚠️ UNPROVEN |
| 2.3.4 | `/me/stems` + `GET /me/music/stems/:id` | POST, GET | ⚠️ UNPROVEN — FAILED `vocal-removal` row on 2026-09-09 |
| 2.3.5 | `/me/voice-generate` | POST | ⚠️ UNPROVEN — FAILED `voice_generate` row on 2026-09-09 |
| 2.3.6 | `/me/voice-validate` · `/me/voice-phrase` · `/me/voice-record` | POST | ⚠️ UNPROVEN |
| 2.3.7 | `/me/voice/apply` · `/me/voice/extend` | POST | ⚠️ UNPROVEN — **not present in the 2026-09-09 report at all** |

### 2.4 Read-side: task, clip, downloads (10)

| # | Endpoint | Method | Status | Evidence |
|---|----------|--------|--------|----------|
| 2.4.1 | `/me/task/:id` | GET | ✅ VERIFIED (2026-09-09) | Client poller path; `probe_e2e.ts` exit 0 exercised the 3-step download poll. Axis A re-confirmed `401`. |
| 2.4.2 | `/me/clip/:id` | GET | 🟡 ROUTED (shallow) | |
| 2.4.3 | `/me/download` (MP3) | GET | ✅ **DEEPLY VERIFIED** (2026-09-09) | `probe_e2e.ts` exit 0: 5,054,339 bytes, ID3 `494433`, `200 audio/mpeg` in 5.1s. |
| 2.4.4 | `/me/download` (WAV) | GET | ✅ **DEEPLY VERIFIED** (2026-09-09) | `probe_e2e.ts` exit 0: 43,060,250 bytes, RIFF/WAVE/fmt fingerprint, `200 audio/wav` in 6.3s. |
| 2.4.5 | `/me/download` (expired clip) | GET | ✅ **DEEPLY VERIFIED** (2026-09-09) | Graceful `502` JSON on all 3 UI surfaces; zero CDN leakage. |
| 2.4.6 | `/me/music/subtitle/:id` | GET | 🟡 ROUTED (shallow) | |
| 2.4.7 | `/me/music/video/:id` | GET | 🟡 ROUTED (shallow) | |
| 2.4.8 | `/me/lyrics/:id` | GET | 🟡 ROUTED (shallow) | |
| 2.4.9 | `/me/jobs/running` | GET | ✅ VERIFIED (2026-09-09) | Auto-poll behavior confirmed. |
| 2.4.10 | `/me/upload/status/:id` | GET | 🟡 ROUTED (shallow) | |

### 2.5 Billing, usage, logs (7)

| # | Endpoint | Method | Status |
|---|----------|--------|--------|
| 2.5.1 | `/me/usage` | GET | ✅ VERIFIED (2026-09-09) |
| 2.5.2 | `/me/usage/by-endpoint` | GET | ✅ VERIFIED (2026-09-09) |
| 2.5.3 | `/me/logs` | GET | ✅ VERIFIED (2026-09-09) |
| 2.5.4 | `/me/billing` | GET | 🟡 ROUTED (shallow) |
| 2.5.5 | `/me/transactions` | GET | 🟡 ROUTED (shallow) — **new since 2026-09-09** |
| 2.5.6 | `/me/upload/init` · `/me/upload/register` | POST | 🟡 ROUTED (shallow) |

---

## 3. Auth `/auth/*` (6 routes)

| # | Endpoint | Method | Status | Evidence |
|---|----------|--------|--------|----------|
| 3.1 | `/auth/register` | POST | 🔒 **INTENTIONAL 405** | `{ error: "Self-registration is disabled. Please sign in with Google." }` — Google-only signup by design. |
| 3.2 | `/auth/login` | POST | 🟡 ROUTED (shallow) | `400` on empty body. **Admin-only** — returns `403` for non-admin users. |
| 3.3 | `/auth/logout` | POST | ✅ VERIFIED | `200` without auth (idempotent by design). |
| 3.4 | `/auth/me` | GET | ✅ VERIFIED (2026-09-09) | Session confirmed via cookie. Axis A re-confirmed `401`. |
| 3.5 | `/auth/google/url` | GET | ✅ VERIFIED | `200`; returns signed `state` + consent URL. |
| 3.6 | `/auth/google/callback` | POST | 🟡 ROUTED (shallow) | `400` on empty body. Full OAuth round-trip still needs real consent-screen E2E. |

---

## 4. Admin `/admin/*` (32 routes)

All `401` unauthenticated. **No admin route has ever been hit with a real admin session** — this is
the largest untouched block. Note the surface grew from the 18 routes reported on 2026-09-09.

| # | Family | Routes | Status |
|---|--------|--------|--------|
| 4.1 | `/admin/keys` | 1 | ⚠️ UNPROVEN |
| 4.2 | `/admin/accounts` (+ `/:id` PATCH/DELETE) | 4 | ⚠️ UNPROVEN |
| 4.3 | `/admin/analytics`, `/admin/audit`, `/admin/alerts`, `/admin/logs` | 4 | ⚠️ UNPROVEN — **new since 2026-09-09 (Phase 5)** |
| 4.4 | `/admin/stats` | 1 | ⚠️ UNPROVEN |
| 4.5 | `/admin/settings` (GET, PUT) | 2 | ⚠️ UNPROVEN — **new** |
| 4.6 | `/admin/users` (+ `/:id` PATCH, `/:id/credits`, `/:id/rate-limits` GET/PUT) | 5 | ⚠️ UNPROVEN — rate-limits **new** |
| 4.7 | `/admin/pricing` (+ `/:id` PUT/DELETE) | 4 | ⚠️ UNPROVEN |
| 4.8 | `/admin/credit-packs` (+ `/:id` PUT/DELETE) | 4 | ⚠️ UNPROVEN — **new (Phase 5)** |
| 4.9 | `/admin/content` (+ `/:id` PUT/DELETE) | 4 | ⚠️ UNPROVEN |
| 4.10 | `/admin/routing` (+ `/:id` DELETE) | 3 | ⚠️ UNPROVEN |

---

## 5. Public API — the revenue surface

### 5.1 `/v1/*` (42 routes) — the documented, sellable API

All `401` unauthenticated. **All 28 `POST` routes return `400` on `{}` with a valid key** — input
validation is intact across the whole surface.

| Family | Count | Status |
|--------|-------|--------|
| Music (`/v1/music`, `/extend`, `/cover`, `/cover-image`, `/stems`, `/remaster`, `/replace-section`, `/recovery`, `/add-vocals`, `/add-instrumental`, `/mashup`, `/midi`, `/wav`, `/sounds`) | 24 | ⚠️ UNPROVEN (axis B) |
| Media (`/v1/mp4/generate`, `/v1/mp4/:id`, `/v1/clip/:id`, `/v1/music/video/:id`, `/v1/music/subtitle/:id`) | 5 | ⚠️ UNPROVEN |
| Voice (6) | 6 | ⚠️ UNPROVEN |
| Lyrics / credits / task (`/v1/lyrics`, `/v1/lyrics/:id`, `/v1/credits`, `/v1/get-credits`, `/v1/task/:id`) | 5 | ⚠️ UNPROVEN |
| Upload (3) | 3 | ⚠️ UNPROVEN |
| Persona (`/v1/persona/create`, `/v1/generate/boost`, `/v1/generate/upload-extend`, `/v1/generate/upload-cover`) | 4 | ⚠️ UNPROVEN |

### 5.2 `/api/v1/*` (60 routes) — sunoapi.org-compatible wrapper

All `401` unauthenticated. **All 34 `POST` routes return `400` on `{}` with a valid key.**

| Family | Count | Status |
|--------|-------|--------|
| `/api/v1/generate/*` suite (`extend`, `recovery`, `upload-cover`, `upload-extend`, `add-vocals`, `add-instrumental`, `boost`, `mashup`, `midi`, `cover`, `cover-image`, `convert-wav`, `generate-persona`, `music-video`) + paired `record-info` GETs | 30 | ⚠️ UNPROVEN |
| `/api/v1/lyrics` (+ `/record-info`, `/generate`, `/:id`) | 4 | ⚠️ UNPROVEN |
| `/api/v1/voice/*` (`record`, `phrase`, `validate`, `generate`, `apply`, `extend`) + `record-info` | 7 | ⚠️ UNPROVEN |
| `/api/v1/cover-suno/*`, `/api/v1/cover/*` | 4 | ⚠️ UNPROVEN |
| `/api/v1/convert-to-wav/*`, `/api/v1/create-music-video/*` | 4 | ⚠️ UNPROVEN |
| `/api/v1/vocal-removal/*`, `/api/v1/music-remaster/*` | 4 | ⚠️ UNPROVEN |
| `/api/v1/add-vocals/*`, `/api/v1/add-instrumental/*` | 4 | ⚠️ UNPROVEN |
| `/api/v1/extend-upload` (+ `record-info`) | 2 | ⚠️ UNPROVEN |
| `/api/v1/upload/*` (`init`, `register`, `status/:id`) | 3 | ⚠️ UNPROVEN |
| `/api/v1/get-credits` | 1 | ⚠️ UNPROVEN |

---

## 6. Payments `/payments/*` (6 routes)

| # | Endpoint | Method | Status | Evidence |
|---|----------|--------|--------|----------|
| 6.1 | `/payments/khqr/create` | POST | 🟡 ROUTED (shallow) | `401` unauthenticated. |
| 6.2 | `/payments/khqr/status/:id` | GET | 🟡 ROUTED (shallow) | `401` unauthenticated. |
| 6.3 | `/payments/khqr/confirm-mock/:id` | POST | 🔒 **INTENTIONAL 404** | Dev-only guard: returns `404` when `NODE_ENV !== "development"` so it can never mint free credits in production. **Not a bug** — see [server.ts L5483-L5486](file:///g:/Developments/Projects/Camxora/MusicGenerator-musicapi-integration/musicapi/src/server.ts#L5483-L5486). |
| 6.4 | `/payments/chmaba/create` | POST | 🟡 ROUTED (shallow) | `401` unauthenticated. |
| 6.5 | `/payments/chmaba/status/:id` | GET | 🟡 ROUTED (shallow) | `401` unauthenticated. |
| 6.6 | `/payments/chmaba/webhook` | POST | 🔒 **INTENTIONAL 503** | "Not configured" when ChmabaPay keys are absent — fails loudly rather than silently dropping a payment. |

---

## 7. Public static (3 routes)

| # | Endpoint | Method | Status | Evidence |
|---|----------|--------|--------|----------|
| 7.1 | `/settings` | GET | ✅ VERIFIED | `200` unauthenticated. |
| 7.2 | `/updates` | GET | ✅ VERIFIED | `200` unauthenticated. |
| 7.3 | `/pricing` | GET | ✅ VERIFIED | `200` unauthenticated. |

---

## 8. Frontend page inventory

`web-user` — **18 pages**: `/`, `/login`, `/signup`, `/docs`, `/auth/callback`, `/dashboard`,
`/dashboard/{api-keys,billing,check-voice,generate-voice,logs,playground,recovery-audio,replace-section,separate-vocals,settings,updates,usage}`.

`web-admin` — **11 pages**: `/`, `/login`, `/auth/callback`, `/admin`,
`/admin/{accounts,analytics,content,credit-packs,pricing,settings,users}`.

No page-level E2E was re-run this revision. The `/app/*` mirror tree reported on 2026-09-09 **no
longer exists** in this worktree — that dead-code risk is resolved.

---

## Summary by count

**Axis A — exact T1 probe results (all 205 routes):**

| T1 result | Count | Interpretation |
|---|---|---|
| `200` | 6 | Public / idempotent by design (`/health`, `/settings`, `/updates`, `/pricing`, `/auth/logout`, `/auth/google/url`) |
| `401` | 194 | Correctly auth-gated |
| `400` | 2 | Public routes validating a missing credential (`/auth/login`, `/auth/google/callback`) |
| `405` | 1 | 🔒 `/auth/register` — Google-only signup |
| `404` | 1 | 🔒 `/payments/khqr/confirm-mock/:id` — dev-only guard |
| `503` | 1 | 🔒 `/payments/chmaba/webhook` — unconfigured provider |
| **Total** | **205** | **Zero genuine NOT-ROUTED routes** |

**Axis A — public-API input validation:** 62 `POST` checks (`/v1/*` + `/api/v1/*`, valid key, empty
body) → **62 × `400`, 0 mismatches**. No `500`s, no shadowing, no unauthenticated fall-through.

**Axis B — live Suno success:** still **unproven for every job-submission route on this tree**. The
only deeply-verified success paths (`/me/download` MP3+WAV, `/me/task/:id` poll) date from
**2026-09-09** on a different tree. Closing this is P0/P3 below.

---

## Next Priorities (ordered by ship-risk)

| Priority | Item | Why |
|----------|------|-----|
| **P0** | **Live E2E `POST /me/generate` → poll `/me/task/:id` → `GET /me/download`** | The revenue path. Axis A is proven; axis B has never been run on this tree. **Consumes real Suno quota + credits.** |
| **P1** | Re-audit FAILED `recovery_audio` jobs (`/me/recovery`, `/me/music/recovery`) | 9/9 failed on 2026-09-09 and the audit was never closed. Prompt quality vs. handler bug — still unknown. |
| **P2** | Re-audit `midi_generate`, `mp4_generate`, `voice_generate`, `vocal-removal` | Pattern suggests everything outside plain `music chirp-v4` may be broken. |
| **P3** | `/v1/*` + `/api/v1/*` smoke with a **real API key** (not a cookie) | 102 customer-facing routes = the sellable surface. Axis A is green; axis B is untouched. |
| **P4** | Admin panel `/admin/*`: log in, load each list, perform one mutation | 32 routes, zero real-session evidence, and the surface grew in Phase 5. |
| **P5** | Admin **rate-limits** + **credit-packs** + **settings** verification | Newest Phase 5 features; only `401` observed. |

---

## Files referenced

- Route surface (205 registered Fastify routes): [server.ts](file:///g:/Developments/Projects/Camxora/MusicGenerator-musicapi-integration/musicapi/src/server.ts)
- Boot / shutdown / drain: [serve.ts](file:///g:/Developments/Projects/Camxora/MusicGenerator-musicapi-integration/musicapi/src/serve.ts)
- Account pool + cookie decryption: [pool.ts](file:///g:/Developments/Projects/Camxora/MusicGenerator-musicapi-integration/musicapi/src/pool.ts)
- Env contract (fail-fast): [config.ts](file:///g:/Developments/Projects/Camxora/MusicGenerator-musicapi-integration/musicapi/src/config.ts)
- Migrations `0001`–`0019`: [migrations/](file:///g:/Developments/Projects/Camxora/MusicGenerator-musicapi-integration/musicapi/migrations)
- Roadmap this report feeds into: [docs/state-of-the-art-and-roadmap.md](file:///g:/Developments/Projects/Camxora/MusicGenerator-musicapi-integration/musicapi/docs/state-of-the-art-and-roadmap.md)
