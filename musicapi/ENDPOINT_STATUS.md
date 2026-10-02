# Endpoint Status Matrix — SunoAPI Middleman Wrapper

> Report date: **2026-09-09** · Ground-truth: live browser E2E (viewId `92d5fefd-89ec-4130-80a0-06a77bad173e`) + 100-entry rolling network buffer + `probe_e2e.ts` exit 0 + Fastify route inventory [server.ts](file:///e:/Development/SunoAPI/src/server.ts) (100 registered routes) + Next.js pages inventory (25 page routes).

---

## Legend

| Status | Meaning |
|--------|---------|
| ✅ **VERIFIED** | Live traffic evidence this session — network dump + real clicks + byte-verified output. |
| 🟡 **PROBABLY WORKS** | Route handler exists, page renders, light 200 in network, but **no deep POST E2E** was executed this cycle. |
| ⚠️ **NOT VERIFIED / NEEDS E2E TESTING** | Handler/page is registered or present but **zero live traffic evidence** or 100% FAILED log rows observed. Assumed non-working until proven. |

---

## 1. Core Auth + Self-Service Dashboard Endpoints (18 routes)

| # | Endpoint | Method | Handler | Status | Evidence |
|---|----------|--------|---------|--------|----------|
| 1.1 | `/health` | GET | [server.ts L538](file:///e:/Development/SunoAPI/src/server.ts#L538) | ✅ VERIFIED | Frontend proxy bootstrap returns `{ok:true}`. |
| 1.2 | `/auth/register` | POST | [server.ts L545](file:///e:/Development/SunoAPI/src/server.ts#L545) | 🟡 PROBABLY WORKS | Register page renders; auth pipeline is identical to working `/auth/login`. |
| 1.3 | `/auth/login` | POST | [server.ts L561](file:///e:/Development/SunoAPI/src/server.ts#L561) | ✅ VERIFIED | Logged in `user@example.com` → JWT set; `/auth/me` confirms session. |
| 1.4 | `/auth/me` | GET | [server.ts L575](file:///e:/Development/SunoAPI/src/server.ts#L575) | ✅ VERIFIED | Header renders `U Test User user@example.com` (snapshot ref `e696`). |
| 1.5 | `/auth/google/url` · `/auth/google/callback` | GET / POST | [server.ts L583-L599](file:///e:/Development/SunoAPI/src/server.ts#L583-L599) | ⚠️ NOT VERIFIED | Google button renders in login modal but **OAuth flow never completed** this cycle. Needs valid Google credentials + real consent-screen round-trip E2E. |
| 1.6 | `/me/keys` (list) | GET | [server.ts L652](file:///e:/Development/SunoAPI/src/server.ts#L652) | ✅ VERIFIED | Network entries #1/#3/#28/#29 → 200. API Keys page renders in 3 browser tabs. |
| 1.7 | `/me/keys` (create) | POST | [server.ts L661](file:///e:/Development/SunoAPI/src/server.ts#L661) | 🟡 PROBABLY WORKS | UI renders; one-time emerald success-banner code path not hit this session. |
| 1.8 | `/me/keys/:id` (edit / IP whitelist) | PUT | [server.ts L673](file:///e:/Development/SunoAPI/src/server.ts#L673) | 🟡 PROBABLY WORKS | Whitelist editor renders; no live edit performed this cycle. |
| 1.9 | `/me/usage` | GET | [server.ts L1024](file:///e:/Development/SunoAPI/src/server.ts#L1024) | ✅ VERIFIED | Network #0/#2/#33/#35 → 200. Usage page content loads. |
| 1.10 | `/me/usage/by-endpoint` | GET | [server.ts L1120](file:///e:/Development/SunoAPI/src/server.ts#L1120) | ✅ VERIFIED | Network #34/#36 → 200. |
| 1.11 | `/me/logs` | GET | [server.ts L1073](file:///e:/Development/SunoAPI/src/server.ts#L1073) | ✅ VERIFIED | Network #21/#23/#27/#29/#43/#45 → 200; table populates 24 rows correctly. |
| 1.12 | `/me/jobs/running` | GET | [server.ts L1281](file:///e:/Development/SunoAPI/src/server.ts#L1281) | ✅ VERIFIED | Network #22/#24/#44/#46 → 200; auto-poll behavior confirmed. |
| 1.13 | `/me/task/:id` | GET | [server.ts L971](file:///e:/Development/SunoAPI/src/server.ts#L971) | ✅ VERIFIED | Called implicitly by client poller; `probe_e2e.ts` exit 0 exercised 3-step download poll including task data. |
| 1.14 | `/me/billing` | GET | [server.ts L1162](file:///e:/Development/SunoAPI/src/server.ts#L1162) | 🟡 PROBABLY WORKS | Billing page loads (tab #5 active); no deep Stripe / top-up POST executed. |
| 1.15 | `/me/download` (real clips, MP3) | GET | [server.ts L1179-L1278](file:///e:/Development/SunoAPI/src/server.ts#L1179-L1278) | ✅ **DEEPLY VERIFIED** | `probe_e2e.ts` exit 0: 5,054,339 bytes, ID3 bytes `494433`, HTTP 200 `audio/mpeg` in 5.1s. Browser network entries (row + intra-modal + dedup test all 200, zero fail markers for real `0ceba9e7`/`1a58eb4d`/`77fba4e6`/`589fcb86` clip ids. |
| 1.16 | `/me/download` (real clips, WAV) | GET | [server.ts L1179-L1278](file:///e:/Development/SunoAPI/src/server.ts#L1179-L1278) | ✅ **DEEPLY VERIFIED** | `probe_e2e.ts` exit 0: 43,060,250 bytes, RIFF/WAVE/fmt byte-fingerprint match, HTTP 200 `audio/wav` in 6.3s. Browser network intra-modal clip2 WAV [entry 93], row WAV all 200. |
| 1.17 | `/me/download` (expired/dead clips, graceful fail) | GET | [server.ts L1274-L1275](file:///e:/Development/SunoAPI/src/server.ts#L1274-L1275) | ✅ **DEEPLY VERIFIED** (3-path browser test) | Silent Horizons row MP3, row WAV, Result modal both clips → all 3 surfaces return HTTP 502 JSON `{error: "Audio not available. The clip may have expired or the media server is unreachable."}`; error string renders verbatim in `AuthorizedAudio` error div at [playground.tsx L119](file:///e:/Development/SunoAPI/web-user/components/playground.tsx#L119); **zero new `cdn1.suno.ai` URLs** in post-fix 100-entry rolling network buffer (only stale pre-fix entry remains as evidence). |
| 1.18 | `/me/lyrics/:id` | GET | [server.ts L1650](file:///e:/Development/SunoAPI/src/server.ts#L1650) | ⚠️ NOT VERIFIED | Lyrics toolbar button present, never clicked. |

---

## 2. Generation / Media Endpoints — `/me/*` jobs (12 routes)

> **NOTE:** Log table this session shows 21 FAILED rows and 3 SUCCESS rows for `music`, `recovery_audio`, `mp4_generate`, `midi_generate`, `voice_generate`. The 3 SUCCESS rows (Neon/Soft/Silent) were generated in a **previous session on 2026-09-08 22:32 → 19:09** — none of the job-**submission** POSTs below were executed this verification cycle.

| # | Endpoint | Method | Handler | Status | Evidence |
|---|----------|--------|---------|--------|----------|
| 2.1 | `/me/generate` (chirp-v4 music) | POST | [server.ts L702](file:///e:/Development/SunoAPI/src/server.ts#L702) | 🟡 PROBABLY WORKS (historic pass, **needs live E2E**) | Shared `useJob()` hook at [playground.tsx](file:///e:/Development/SunoAPI/web-user/components/playground.tsx) is wired and the task poll+download pipeline (#1.13–#1.16) works end-to-end; BUT no live `POST /me/generate` → SUCCESS was hit this session. **Is next missing piece if the goal is ship.** |
| 2.2 | `/me/music` (alias) | POST | [server.ts L1300](file:///e:/Development/SunoAPI/src/server.ts#L1300) | 🟡 PROBABLY WORKS | Alias for 2.1. |
| 2.3 | `/me/sounds` | POST | [server.ts L1314](file:///e:/Development/SunoAPI/src/server.ts#L1314) | 🟡 PROBABLY WORKS | |
| 2.4 | `/me/recovery` (audio recovery) | POST | [server.ts L768](file:///e:/Development/SunoAPI/src/server.ts#L768) | ⚠️ NOT VERIFIED | **9/9 FAILED rows** `recovery_audio` type in logs. Recovery page loads; no live E2E. Likely prompt issue OR real handler bug. Investigate separately. |
| 2.5 | `/me/stems` (vocal removal / separate) | POST | [server.ts L790](file:///e:/Development/SunoAPI/src/server.ts#L790) | ⚠️ NOT VERIFIED | Separate Vocals page loads. 1 FAILED `vocal-removal` row. |
| 2.6 | `/me/replace-section` | POST | [server.ts L813](file:///e:/Development/SunoAPI/src/server.ts#L813) | ⚠️ NOT VERIFIED | Page loads, never hit. |
| 2.7 | `/me/persona-create` | POST | [server.ts L843](file:///e:/Development/SunoAPI/src/server.ts#L843) | ⚠️ NOT VERIFIED | |
| 2.8 | `/me/voice-generate` | POST | [server.ts L869](file:///e:/Development/SunoAPI/src/server.ts#L869) | ⚠️ NOT VERIFIED | Generate Voice page loads. 1 FAILED `voice_generate` row. |
| 2.9 | `/me/voice-validate` | POST | [server.ts L895](file:///e:/Development/SunoAPI/src/server.ts#L895) | ⚠️ NOT VERIFIED | Check Voice page loads. |
| 2.10 | `/me/voice-phrase` | POST | [server.ts L917](file:///e:/Development/SunoAPI/src/server.ts#L917) | ⚠️ NOT VERIFIED | |
| 2.11 | `/me/voice-record` | POST | [server.ts L936](file:///e:/Development/SunoAPI/src/server.ts#L936) | ⚠️ NOT VERIFIED | |
| 2.12 | `/me/music/replace-section` · `/me/music/recovery` · `/me/upload/status/:id` | POST/GET | [server.ts L1587-L1629](file:///e:/Development/SunoAPI/src/server.ts#L1587-L1629) | ⚠️ NOT VERIFIED | Aliases + upload status. Uploaded-file flows completely untested. |

---

## 3. Public Static & Marketing Endpoints (3 routes)

| # | Endpoint | Method | Handler | Status | Evidence |
|---|----------|--------|---------|--------|----------|
| 3.1 | `/updates` | GET | [server.ts L1734](file:///e:/Development/SunoAPI/src/server.ts#L1734) | ✅ VERIFIED | Network #40/#41 → 200. Updates page loads content. |
| 3.2 | `/pricing` | GET | [server.ts L1740](file:///e:/Development/SunoAPI/src/server.ts#L1740) | 🟡 PROBABLY WORKS | Static JSON; renders on billing page top-up tiles. |
| 3.3 | Docs page `/docs` | GET | [web-user/app/docs/page.tsx](file:///e:/Development/SunoAPI/web-user/app/docs/page.tsx) | 🟡 PROBABLY WORKS | Page route registered; not navigated to this cycle. |

---

## 4. Admin Panel (`/admin/*`) — 18 routes

> **NOT ONE was hit this cycle. Admin UI may or may not work. Assumed ⚠️ across the board.**

| # | Endpoint family | Handler block | Status |
|---|-----------------|---------------|--------|
| 4.1 | `/admin/keys` · `/admin/accounts` (list, create) | [server.ts L1754-L1791](file:///e:/Development/SunoAPI/src/server.ts#L1754-L1791) | ⚠️ NOT VERIFIED |
| 4.2 | `/admin/stats` · `/admin/users` · `/admin/users/:id` (patch, top-up credits) | [server.ts L1810-L1855](file:///e:/Development/SunoAPI/src/server.ts#L1810-L1855) | ⚠️ NOT VERIFIED |
| 4.3 | `/admin/pricing` (list, create, delete) | [server.ts L1886-L1918](file:///e:/Development/SunoAPI/src/server.ts#L1886-L1918) | ⚠️ NOT VERIFIED |
| 4.4 | `/admin/routing` (list, create, delete) | [server.ts L1925-L1951](file:///e:/Development/SunoAPI/src/server.ts#L1925-L1951) | ⚠️ NOT VERIFIED |
| 4.5 | `/admin/logs` · `/admin/content` (list, create, update, delete) | [server.ts L1958-L2009](file:///e:/Development/SunoAPI/src/server.ts#L1958-L2009) | ⚠️ NOT VERIFIED |

---

## 5. Public API `/v1/*` — 30 routes + Legacy wrapper `/api/v1/*` — 26 routes

> These are your **customer-facing public API wrappers**. 56 routes total. **Zero traffic evidence this cycle.** All are ⚠️ until you run real key-authenticated E2E against them.

### 5.1 `/v1/*` (30) — block [server.ts L2017-L2640](file:///e:/Development/SunoAPI/src/server.ts#L2017-L2640)

| Family | Example endpoints | Status |
|--------|-------------------|--------|
| Music | `/v1/music`, `/v1/sounds`, `/v1/music/mashup`, `/v1/music/wav`, `/v1/music/midi`, `/v1/music/recovery`, `/v1/music/replace-section`, `/v1/music/cover-image`, `/v1/mp4/generate`, `/v1/music/mashup`, `/v1/generate/boost`, `/v1/generate/upload-extend`, `/v1/generate/upload-cover` | ⚠️ NOT VERIFIED |
| Voice (6) | `/v1/voice/phrase`, `/v1/voice/validate`, `/v1/voice/record`, `/v1/voice/generate`, `/v1/voice/apply`, `/v1/voice/extend` | ⚠️ NOT VERIFIED |
| Credits / Lyrics / Task | `/v1/credits`, `/v1/lyrics`, `/v1/lyrics/:id`, `/v1/task/:id` | ⚠️ NOT VERIFIED |
| Upload (3) | `/v1/upload/init`, `/v1/upload/register`, `/v1/upload/status/:id` | ⚠️ NOT VERIFIED |
| Persona | `/v1/persona/create` | ⚠️ NOT VERIFIED |

### 5.2 `/api/v1/*` legacy wrapper (PREFIX=`/api/v1`) — block [server.ts L2676-L3213](file:///e:/Development/SunoAPI/src/server.ts#L2676-L3213)

| Family | Example endpoints | Status |
|--------|-------------------|--------|
| Core | `/api/v1/get-credits`, `/api/v1/generate`, `/api/v1/lyrics` | ⚠️ NOT VERIFIED |
| Generate suite (12) | `generate/extend`, `/generate/upload-extend`, `/generate/upload-cover`, `/generate/add-vocals`, `/generate/add-instrumental`, `/generate/generate-persona`, `/generate/cover`, `/generate/cover-image`, `/generate/convert-wav`, `/generate/boost`, `/generate/music-video`, `/generate/mashup`, `/generate/midi`, `/generate/recovery` | ⚠️ NOT VERIFIED |
| Cover suite (2) | `/cover-suno/generate`, `/cover/generate` | ⚠️ NOT VERIFIED |
| Vocal removal | `/vocal-removal/generate` | ⚠️ NOT VERIFIED |
| Upload alias | `/extend-upload`, plus Suno passthrough proxy `GET /api/v1${sunoPath}` at L2841 | ⚠️ NOT VERIFIED |

---

## 6. Frontend Pages Inventory (25 routes)

Grouped by active test evidence this cycle:

| Page route | File | Status |
|------------|------|--------|
| **✅ Loaded in active live tab this cycle** (DOM confirmed) | | |
| Logs (`/dashboard/logs`) | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/dashboard/logs/page.tsx) | ✅ PRIMARY WORKSPACE |
| API Keys (`/dashboard/api-keys`, 3 tabs) | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/dashboard/api-keys/page.tsx) | ✅ ACTIVE TABS (3) |
| Usage (`/dashboard/usage`) | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/dashboard/usage/page.tsx) | ✅ DATA LOADED |
| Updates (`/dashboard/updates`) | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/dashboard/updates/page.tsx) | ✅ DATA LOADED |
| Billing (`/dashboard/billing`) | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/dashboard/billing/page.tsx) | ✅ ACTIVE TAB |
| Landing (`/`) | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/page.tsx) | ✅ DOCUMENT RENDERED |
| Dashboard home (`/dashboard`) | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/dashboard/page.tsx) | 🟡 RENDERS |
| Login (`/login`) + Signup (`/signup`) + Google callback (`/auth/callback`) | [login](file:///e:/Development/SunoAPI/web-user/app/login/page.tsx), [signup](file:///e:/Development/SunoAPI/web-user/app/signup/page.tsx), [callback](file:///e:/Development/SunoAPI/web-user/app/auth/callback/page.tsx) | 🟡 RENDER |
| **🟡 Route exists, page loads in SSR (toolbars show links), never navigated to explicitly this session** | | |
| Playground `/dashboard/playground` | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/dashboard/playground/page.tsx) | 🟡 PROBABLY WORKS |
| Recovery Audio `/dashboard/recovery-audio` | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/dashboard/recovery-audio/page.tsx) | 🟡 PROBABLY WORKS |
| Separate Vocals `/dashboard/separate-vocals` | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/dashboard/separate-vocals/page.tsx) | 🟡 PROBABLY WORKS |
| Replace Section `/dashboard/replace-section` | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/dashboard/replace-section/page.tsx) | 🟡 PROBABLY WORKS |
| Generate Voice `/dashboard/generate-voice` | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/dashboard/generate-voice/page.tsx) | 🟡 PROBABLY WORKS |
| Check Voice `/dashboard/check-voice` | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/dashboard/check-voice/page.tsx) | 🟡 PROBABLY WORKS |
| Settings `/dashboard/settings` | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/dashboard/settings/page.tsx) | 🟡 PROBABLY WORKS |
| Docs `/docs` | [page.tsx](file:///e:/Development/SunoAPI/web-user/app/docs/page.tsx) | 🟡 PROBABLY WORKS |
| **⚠️ Mirror app shell `/app/*` duplicate tree (6 pages) — zero navigation evidence** | | |
| `/app`, `/app/api-keys`, `/app/billing`, `/app/playground`, `/app/usage`, `/app/logs`, `/app/updates` | `web-user/app/app/**` 7 files | ⚠️ NOT VERIFIED |

---

## Summary by Count

| Status | Count | Share |
|--------|-------|-------|
| ✅ VERIFIED (live E2E evidence this session) | **16** | ~16% |
| 🟡 PROBABLY WORKS (route/page present, shallow evidence only) | **8** | ~8% |
| ⚠️ NOT VERIFIED / NEEDS E2E (admin + public API + generation jobs + mirror app shell + FAILED rows) | **76** | ~76% |

---

## Next Priorities (ordered by ship-risk)

| Priority | Item | Why |
|----------|------|-----|
| **P0** | **Live E2E `POST /me/generate` → SUCCESS → download** | The 3 SUCCESS log rows are stale (Sep 8 previous session). You need to prove `POST → task pending → poll → SUCCESS → clip download` works for a brand-new job this session. Uses the same shared `useJob()` + `downloadBuffer` stack that's already been fixed for the timeout/dedup/CDN-leak trio, but the job SUBMIT half has not been exercised at all this cycle. |
| **P1** | **Audit 9 FAILED `recovery_audio` rows** (endpoints `/me/recovery`, `/me/music/recovery`) | 100% of attempts failed. Is it prompt quality, a missing arg, or a handler bug? Users will hit this. |
| **P2** | **Audit FAILED rows for `midi_generate`, `mp4_generate`, `voice_generate`, `vocal-removal`** | Pattern suggests entire media jobs outside plain `music chirp-v4` are broken. |
| **P3** | `/v1/*` + `/api/v1/*` public API smoke test with real API key JWT (not cookie) | 56 customer endpoints are the revenue surface; 0 tested. Even a `curl`-scripted smoke pass would move them from ⚠️. |
| **P4** | Admin panel `/admin/*` smoke login + list views + one mutation each | 18 admin routes = all ⚠️. |
| **P5** | `/app/*` mirror shell: confirm routes resolve, or delete duplication if unused | 7 page routes are a dead-code risk. |

---

### Files referenced
- Route inventory (100 registered Fastify routes): [server.ts](file:///e:/Development/SunoAPI/src/server.ts)
- UI download & player logic (Map-lock dedup, authorizedFetch, AuthorizedAudio): [playground.tsx](file:///e:/Development/SunoAPI/web-user/components/playground.tsx#L39-L142)
- Logs page (rows + Result modal wiring): [logs/page.tsx](file:///e:/Development/SunoAPI/web-user/app/dashboard/logs/page.tsx)
- Backend long timeout (`requestTimeout: 600_000`): [serve.ts](file:///e:/Development/SunoAPI/src/serve.ts)
- Proxy long timeout (`experimental.proxyTimeout: 600_000`): [next.config.ts](file:///e:/Development/SunoAPI/web-user/next.config.ts#L3-L14)
- 3-step download poll (`maxPolls: 600`): [client.ts](file:///e:/Development/SunoAPI/src/client.ts#L512-L575)
