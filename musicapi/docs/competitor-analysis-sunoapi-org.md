# Competitor Analysis — sunoapi.org vs. our `musicapi`

> Scope: reverse-engineering the *public surface* (site, docs, API, storage, watermark, UX/UI) of
> **sunoapi.org** and comparing it A–Z against our active product in `musicapi/`.
> Goal: identify what we must clone to be "identical to sunoapi.org" and what we already do better.
>
> Research method: live browser sweep of `sunoapi.org` + `docs.sunoapi.org` (including `llms.txt`
> and the published OpenAPI specs) + static reading of `musicapi/src/`. Public pages only for the
> first pass; authenticated dashboard pass is logged under §9.
>
> Status: **DRAFT / living doc.** Dates and evidence per section.

---

## 0. TL;DR

1. **sunoapi.org is a white-label reseller, not an engine.** Its own OpenAPI specs declare the
   upstream server `https://apibox.erweima.ai` (KIE.ai / api.box); stem files come from
   `file.aiquickdraw.com`; docs contact is `support@api.box`. They brand a resold API.
2. **We are the engine.** `musicapi/` owns the Suno account pool, routing, captcha, credits,
   ledger/refunds, admin console, audit, alerts, and payments. Their product is a *surface*
   (docs + stable CDN + exact API contract + marketing) on top of someone else's engine.
3. Therefore "be identical to sunoapi.org" = **clone their surface**, not rebuild our engine.
4. **Two real gaps** dominate everything else:
   - **Durable file delivery.** They cache generated output and serve stable CDN URLs for
     14 days (MP3) / 15 days (WAV) with a `recovery` endpoint. We stream live from Suno and
     links expire → 502s. This is the #1 product-quality gap.
   - **Live-Suno correctness is still unproven on our side.** No end-to-end success path
     (generate → callback → download) has been exercised on the current commit.

---

## 1. What sunoapi.org actually is

| Fact | Evidence |
|---|---|
| Branded front for a resold API | OpenAPI `servers: https://apibox.erweima.ai`; contact `support@api.box` |
| Uses KIE.ai ecosystem | Changelog links point at `https://kie.ai/suno-api?model=...` |
| Third-party file CDN | Stem-separation URLs at `file.aiquickdraw.com` |
| Marketing claims | 99.9% uptime, 20-second streaming, watermark-free, high concurrency, 24/7 support |
| Landing stats | 832 running days, 95.32% uptime, 24.8s response time |

**Implication:** they are our *competitor surface* but not our *technical peer* — we already have the
harder half (the engine). The clone target is their API contract, documentation, and file delivery.

---

## 2. Public page inventory

| Page / area | What it is | Notable detail |
|---|---|---|
| `/` Home | Marketing + **live demo generator** + pricing + FAQ | Demo: Music/Sounds tabs, Custom Mode, model selector (V6), image/video/audio reference uploads; "attachments 0/10" combined cap |
| `/blog` | Content marketing | — |
| `/changelog` (Updates) | Release notes | 2026-07-08: Replace Section custom upload, Advanced Stem Separation |
| `docs.sunoapi.org` | Mintlify docs, `llms.txt`, OpenAPI JSON, multi-language code samples | The real product spec |
| `/login` | Sign in | Redirects protected pages here when signed out |
| `/dashboard` | User account area | Login-gated |
| `/billing` | Credit purchase / balance | Login-gated |
| `/api-key` | API key management | Login-gated |
| `/privacy-policy`, `/terms-of-use`, `sitemap*.xml` | Legal/meta | Sitemap effectively only lists `/` |

Brand: dark theme, purple gradient accent, "MUSICAPI.ORG" wordmark. UI is a standard
Next.js/Tailwind SaaS marketing shell with an embedded generator widget.

---

## 3. API surface (from published OpenAPI)

- **Base URL:** `https://api.sunoapi.org` (docs OpenAPI upstream: `https://apibox.erweima.ai`)
- **Auth:** `Authorization: Bearer <api_key>`
- **Envelope:** `{ code, msg, data }`
- **Callbacks:** POST to caller-supplied `callBackUrl`, stages `text` → `first` → `complete`
  (plus `error`), payload `{code,msg,data:{callbackType, task_id, data:[…]}}`

### 3.1 Music / audio (28)

```
POST /api/v1/generate
POST /api/v1/generate/extend
POST /api/v1/generate/upload-cover
POST /api/v1/generate/upload-extend
POST /api/v1/generate/add-instrumental
POST /api/v1/generate/add-vocals
GET  /api/v1/generate/record-info
GET  /api/v1/generate/credit
POST /api/v1/generate/get-timestamped-lyrics
POST /api/v1/style/generate
POST /api/v1/lyrics
GET  /api/v1/lyrics/record-info
POST /api/v1/wav/generate
GET  /api/v1/wav/record-info
POST /api/v1/vocal-removal/generate
GET  /api/v1/vocal-removal/record-info
POST /api/v1/midi/generate
GET  /api/v1/midi/record-info
POST /api/v1/mp4/generate
GET  /api/v1/mp4/record-info
POST /api/v1/generate/mashup
POST /api/v1/generate/replace-section
POST /api/v1/suno/cover/generate
POST /api/v1/generate/generate-persona
GET  /api/v1/suno/cover/record-info
POST /api/v1/generate/sounds
POST /api/v1/suno/recovery
GET  /api/v1/suno/recovery/record-info
```

### 3.2 Suno Voice (6)

```
POST /api/v1/voice/validate
GET  /api/v1/voice/validate-info
POST /api/v1/voice/generate
GET  /api/v1/voice/record-info
POST /api/v1/voice/regenerate
POST /api/v1/voice/check-voice
```

### 3.3 File Upload (3, separate namespace)

```
POST /api/file-base64-upload
POST /api/file-stream-upload
POST /api/file-url-upload
```

### 3.4 Model versions (docs, as of this pass)

- **Current:** `V6` (default), `V6_WILD`, `V6_MINI`
- **Deprecated (back-compat only):** `V5_5`, `V5`, `V4_5PLUS`, `V4_5ALL`, `V4_5`, `V4`
- Custom-mode extras: `title`, `negativeTags`, `vocalGender`, `duration` (10–360s),
  `styleWeight`, `weirdnessConstraint`, `audioWeight`, `variety` (0–4), `personaId`, `personaModel`.

### 3.5 Generate-music parameter notes

- Always required: `customMode`, `instrumental`, `model`.
- Custom mode: at least one of `style` / `lyrics` / `negativeTags`; `prompt` acts as lyrics.
- Non-custom: at least one of `imageUrls` / `videoUrls` / `audioUrls` / `style` / `lyrics`;
  lyrics auto-generated (not a strict match).
- Attachment caps: ≤10 total; images ≤5 (≤10 MB, jpeg/png/webp/bmp), video ≤1 (≤100 MB, ≤241s),
  audio ≤500 MB each (6s–30min).
- Character limits: V6 `style` 1000, `lyrics` 5000, `negativeTags` 1000, `title` 80.

---

## 4. Storage & delivery model

**They cache and serve from their own CDN.**

| Artifact | Retention | Notes |
|---|---|---|
| Generated tracks (MP3) | **14 days** | Docs: "Generated files are retained for 14 days" |
| WAV conversion output | **15 days** | Delivered via `audioWavUrl` |
| Uploaded files | **3 days** | Auto-deleted |

Two URL families per track:

- **Stable / theirs:** `audio_url`, `stream_audio_url`, `image_url` → maintained CDN links.
- **Original / Suno:** `source_audio_url`, `source_stream_audio_url`, `source_image_url` →
  now **deprecated**, "expire after a period of time and are no longer maintained."
- **Recovery:** `POST /api/v1/suno/recovery` + `GET /api/v1/suno/recovery/record-info` exist
  specifically to re-issue fresh playable links after expiry.

**Verified hosts (live generation, §9.13):** their "stable" links are actually third-party
storage/CDN, not their own:

| Field | Host | Note |
|---|---|---|
| `audio_url` (MP3) | `tempfile.aiquickdraw.com/r/<id>.mp3` | "tempfile" — 14-day retention |
| `stream_audio_url` | `audiostream.api.box/stream/<id>.mp3` | api.box stream CDN |
| `image_url` | `musicfile.removeai.ai/<base64>.jpeg` | cover image host |
| `source_image_url` | `cdn2.suno.ai/image_<id>.jpeg` | Suno original (still populated for images) |
| `source_audio_url` | **empty string** | they no longer surface Suno's original audio |

**Our current behavior (contrast):** no storage at all. `GET /me/download` live-drives Suno's
3-step flow (authorize → poll `/download/clip` → signed S3 URL), streams bytes, falls back to
`cdn1.suno.ai`. Links are ephemeral; clips can expire; there is no retention guarantee and no
recovery endpoint. We charge once per `(clip, format)` through `download_purchases`.

> This is the core of "download without limitation": **they cached it; we proxy on demand.**

---

## 5. Watermark-free

**No watermark-removal technology exists in their product.** Every docs occurrence of "watermark"
is either marketing copy or an *optional brand watermark* on generated **music videos**. The actual
mechanism is: generation runs through **paid Suno accounts**, whose native output is clean; only
Suno's free tier watermarks.

We already have the same building block: the pool tags accounts `free|paid` and routing policy
supports `prefer_free` / `paid_only` / `any`. To match and claim it:
**force `paid_only` for customer-facing generation (or gate on a commercial flag) and document it.**

---

## 6. A–Z comparison

Legend: ✅ parity · 🟡 partial · ❌ gap

| Area | sunoapi.org | Our musicapi | Status |
|---|---|---|---|
| Engine | Resells apibox/KIE | Own Suno pool, routing, captcha, health | ✅ stronger |
| Core generation API | `/api/v1/generate` | same path + `{code,msg,data}` envelope | ✅ |
| API path parity | 28 + 6 + 3 endpoints | ~37 aliases, several paths differ | 🟡 |
| Credit endpoint | `GET /api/v1/generate/credit` | `GET /api/v1/get-credits` | ❌ |
| WAV / MIDI / MP4 / cover / recovery paths | `/wav/*`, `/midi/*`, `/mp4/*`, `/suno/cover/*`, `/suno/recovery/*` | `/convert-to-wav/*`, `/generate/midi/*`, `/generate/music-video`, `/cover-suno/*`, `/generate/recovery` | ❌ |
| `sounds`, `style/generate`, `get-timestamped-lyrics`, `replace-section` aliases | present | missing under `/api/v1` | ❌ |
| Voice vocabulary | `validate/validate-info/generate/record-info/regenerate/check-voice` | `phrase/validate/record/generate/apply/extend` | ❌ |
| File upload API | base64 / stream / url, 3-day temp | 3-step `init/register/status` S3 flow | ❌ |
| Models | V6 (default), V6_MINI, V6_WILD | aliases remap V4/V5/V5_5 → v6 family; `V6*` passed through unverified | 🟡 |
| Response / callback shape | 3-stage `text/first/complete` with track URLs | enqueue + poll; callback exists | 🟡 verify exact payload |
| **Stable file delivery** | own CDN, 14/15-day retention, recovery endpoint | none; live streaming from Suno, ephemeral | ❌ **critical** |
| Watermark-free | advertised + paid accounts | possible, not enforced/advertised | 🟡 |
| Credits / billing | credit endpoint; packages; 429 on insufficient | credits, ledger, refunds, safe-spend, packs; returns 402 | 🟡 |
| User panel | dashboard, api-key, billing, playground | full Next.js workspace | ✅ |
| Admin panel | none public | accounts, users, pricing, analytics, audit, alerts, routing | ✅ stronger |
| Auth | Bearer key | Bearer key + Google user + admin email/password + httpOnly cookie | ✅ |
| Payments | (their billing) | KHQR + ChmabaPay, verified webhook | ✅ |
| Ops | claims 99.9% uptime | systemd, nginx+TLS, backups, health alerts, CI | ✅ |
| Docs experience | Mintlify, `llms.txt`, OpenAPI, samples, interactive | markdown + `ENDPOINT_STATUS.md` | ❌ |
| Live correctness proven | live product | **unproven on current commit** | ❌ **critical** |

---

## 7. Gaps ranked by launch impact

1. **Live-Suno success path unproven** (our R1.2). Nothing else matters until a real
   generate → callback/poll → MP3/WAV download succeeds end-to-end.
2. **No durable storage / CDN / recovery.** Causes expiring links and 502s; blocks the
   "download without limitation" claim.
3. **`/api/v1` contract drift** vs. their exact paths, voice vocabulary, upload API, and codes.
4. **Model currency** — V6 family support unverified.
5. **Watermark-free not enforced/advertised.**
6. **Provider secret rotation still pending** (user/ops) and **prod DNS/TLS not issued**.
7. **Docs experience** — no OpenAPI spec or `llms.txt` for drop-in integration.

---

## 8. Recommendations

**Do not chase full parity. Ship the revenue half of their surface, delivered reliably.**

1. **Prove live generation (1–2 days).** Spend a little quota; verify
   `generate → callback/poll → download MP3/WAV` on the current commit.
2. **Durable delivery (3–5 days).** On job completion, copy finished MP3/WAV/image into object
   storage (Backblaze B2 is already in the platform env) and return stable
   `audio_url` / `stream_audio_url` / `image_url`. Add `recovery` + a 14/15-day retention policy.
3. **Exact `/api/v1` contract (2–3 days).** Fix paths/codes/vocabulary, add the 3 upload methods,
   publish an OpenAPI spec + `llms.txt`.
4. **Watermark-free guarantee (hours).** Default customer generation to `paid_only`; document it.
5. **Model currency (0.5–1 day).** Verify V6/V6_MINI/V6_WILD; map deprecated keys; expose new params.
6. **Ship gates (1 day).** Rotate provider secrets; prod DNS + TLS; sandbox deploy → smoke → prod.

**Positioning:** lead with our engine strengths (account pool, admin, audit, refunds, payments,
per-key controls). Clone their docs + stable CDN + exact paths — not their reseller architecture.

**Risk flag (business, not code):** both products stand on reverse-engineered Suno access, and
selling "watermark-free / unlimited downloads" is exactly the claim that invites Suno ToS
enforcement. Mitigate with a multi-provider abstraction and clear branding.

---

## 9. Authenticated research (logged-in paid account)

> Method: read-only browsing + **0-credit** read endpoints only. **No plan, credit, or top-up was
> purchased by the agent.** The one API call made (`POST /api/v1/voice/check-voice`) is a
> no-cost read and returned `{"code":400,"msg":"Voice record not found","data":null}`.
> Account at time of research: 1,342.8 credits, 32 requests / 100% success in 24h.

### 9.1 User panel information architecture

Sidebar (top → bottom): **Dashboard** · **Playground** (Music Generation, Recovery Audio,
Separate Vocals, Generate Voice, Check Voice, Replace Section) · **API Key** · **API Usage** ·
**API Updates** · **Logs** · **Billing** · **Document** · Get Support (Discord / Telegram) ·
Settings · Language · Log Out.

Header shows avatar, name, email; Dashboard has `API Key` and `Top Up` buttons.

### 9.2 Dashboard

- Last 24 Hours: **Success / Failure / Other** counts with percentages; **Total Requests**.
- **Remaining credits**.
- Multi-day bar chart with **14 days / 7 days** toggle (`2026-09-18 … 2026-10-01`, Total 755).
- **Real-time Success Rate** line chart (per-minute, ~15 min window).
- Portal backing calls: `GET /client/v1/user/user-info`, `GET /client/v1/dashboard/last-24-hours`,
  `POST /client/v1/dashboard/time-record` `{startDate,endDate}`,
  `GET /client/v1/userRecord/getSuccessRate`.
- 24h payload shape: `{code:200,msg:"success",data:{totalCount,successCount,failCount,otherCount}}`.

### 9.3 API Key page

Columns: **Name · Key · Created Date · IP Whitelist · Safe-Spend Limits · Actions**; button
"Create New Key". Backed by `GET /client/v1/user/getApiKeyList`.

> Note: IP whitelist + safe-spend limits + one-time-visible keys are features **we already ship**
> (`/me/keys`, `api_keys.ip_whitelist`, `safe_spend_*`).

### 9.4 API Usage page

"Track credit spend across models and API keys", date range (e.g. `Sep 19 – Oct 2`) + **Export**.
Backed by `POST /client/v1/credits/usagePage` `{startTime,endTime}`.

### 9.5 Logs page

- Banner: "Media files (images, videos, audio, etc.) are retained for **14 days**, and log data is
  retained for **2 months**. Data beyond these periods will be permanently deleted."
- Tabs: **audio · recovery audio · lyrics · subtitle · wav · vocal-removal · lyrics video
  generator · voice**.
- Table: **Time · Type · Model · Prompt · Status · Credits Consumed · taskId · Result**.
- taskId search + Refresh. Backed by `GET /client/v1/userRecord/getPageDisplayType`
  and `POST /client/v1/userRecord/getApiboxSunoRecordPage`.

> Our dashboard logs tabs already mirror these (`REQUIREMENTS §3.6`). **Gap:** they retain media
> 14 days / logs 2 months; we do neither.

### 9.6 Billing page (real numbers)

- **Balance:** 1,342.8 credits. "**Credits never expire.**"
- **Rate limit: 20 requests / 10 seconds (20 req/10s).**
- **Packages:** $5 → 1,000 · $50 → 10,000 (Save 5%) · $500 → 105,000 (Save 10%) ·
  $1,250 → 275,000 (Save 10%).
- **Payment:** Card + Apple Pay + Cash App + crypto (via **Adyen** — portal call
  `GET /client/trade/adyen/listVaults`), Business Purchase toggle, Country/Region, Zip.
- **Automatic Payments / auto top-ups:** enable, Auto-Pay Threshold, Auto-Pay Amount, reload max
  once every 10 minutes.
- **Transaction History** table (DateTime · Credits · Amount · Invoice) via
  `POST /client/v1/payOrder/getApiboxSunoPayOrderList` `{pageNum,pageSize}`.
- **"Each credit is valued at $0.005 USD."**

**Per-endpoint credit costs (authoritative):**

| Endpoint | Credits/call | ≈ USD |
|---|---|---|
| Generate Music (V5.5 / V5 / V4.5+ / V4.5 / V4 / V4.5ALL) | 12 | $0.060 |
| Extend Music (same model set) | 12 | $0.060 |
| Upload And Cover Audio | 12 | $0.060 |
| Upload And Extend Audio | 12 | $0.060 |
| Add Instrumental | 12 | $0.060 |
| Add Vocals | 12 | $0.060 |
| Sounds Generation (V5) | 2.5 | $0.0125 |
| Separate Vocals from Music | 10 | $0.050 |
| Split Stem | 50 | $0.250 |
| Advanced Stem Split from Music | 20 | $0.100 |
| Replace Music Section | 5 | $0.025 |
| Create Music Video | 2 | $0.010 |
| Get Timestamped Lyrics | 0.5 | $0.0025 |
| Boost Musik Stil | 0.4 | $0.002 |
| Generate Lyrics | 0.4 | $0.002 |
| Convert to WAV Format | 0.4 | $0.002 |
| Generate Music Cover | 0 | free |
| Generate Persona | 0 | free |
| All `record-info` / details endpoints | 0 | free |
| Get Remaining Credits | 0 | free |

> **Use this table as the source of truth for our `pricing` rows.** Our credits are DB-driven
> (`pricing` table), so matching their numbers is an admin-data change, not a code change.

### 9.7 Playground pages (field-level feature inventory)

**Music Generation** (`/playground`): Music Generation / Sounds Generation tabs, Custom Mode
toggle, model selector (**V6** default), Song Description (0/3000), Style of Music (0/1000),
Reference Images (0/5, ≤10MB, JPEG/JPG/PNG/WEBP), Reference Video (0/1, ≤100MB, MP4/MOV/WEBM),
Reference Audio (0/10, ≤500MB, 6s–30min), "Attachments used 0/10", Instrumental toggle, Lyrics
(0/5000), `personaId`, Generate Music. Copy: "streaming response… as fast as 20 seconds",
"Stable and watermark-free".

**Recovery Audio** (`/recovery-audio`): `sunoTaskId*`, `callBackUrl*`, Recover Audio; JSON output.
**Separate Vocals** (`/separate-vocals`): use generated music or uploaded custom audio;
`taskId*`, `audioId*`; Separation Type = **Vocal Separation | Multi-Stem Separation | Advanced
Split** (custom track name); JSON output.
**Generate Voice** (`/generate-voice`): source + validation groundwork in a popup; `taskId`,
`voiceName`, `style`, `singerSkillLevel` (Beginner/Intermediate/Advanced/Professional),
`description`; outputs source audio, validation phrase, validation audio, voiceId.
**Check Voice** (`/check-voice`): `taskId` → Check Availability (this was the 0-credit call we made).
**Replace Section** (`/replace-section`): `taskId*, audioId*, prompt*, lyrics, tags*, title*,
infillStartS*, infillEndS*` (min 10s), `negativeTags, fullLyrics*, vocalGender, styleWeight,
weirdnessConstraint, audioWeight, variety (off/normal/high/extra/max), personaId`.

> Almost all of this maps 1:1 onto our `/dashboard/playground` + `/me/*` routes. The **Replace
> Section** form is the richest single gap-check: compare our field set and defaults.

### 9.8 API Updates + Settings

- **API Updates**: announcement list via `POST /api/v1/common/pageApiAnnouncementList`.
- **Settings**: email subscription toggle, Join VIP channel (via **KIE**, Telegram),
  Danger Zone → Delete Account.

### 9.9 Payments / provider fingerprints

- Payments: **Adyen** card vaults (`/client/trade/adyen/listVaults`).
- Support/VIP: **KIE** Telegram server (confirming the KIE.ai reseller relationship in §1).
- Infra: **Cloudflare** in front (`cf-ray …-SIN`, Singapore edge).
- Portal auth: `authorization` cookie + `localStorage.apibox_user`; client API also sends a
  `uniqueid` header. Portal API is a **separate `client/v1` backend**, distinct from the public
  `api/v1` product API.

### 9.10 Public API contract — live-verified

`POST https://api.sunoapi.org/api/v1/voice/check-voice`
→ request `{"taskId":"…"}`, response `{"code":400,"msg":"Voice record not found","data":null}`
(HTTP 200). Confirms the `{code,msg,data}` envelope and that business errors travel in `code`,
not the HTTP status.

### 9.11 Authenticated gaps vs. our product

| Finding | Our state | Action |
|---|---|---|
| Media retention 14 days, logs 2 months | none | **Build** storage + retention |
| 20 req/10s account rate limit | per-user/min+day + global | Align defaults or document difference |
| Adyen card vaults + auto top-up | KHQR/ChmabaPay, no auto top-up | Consider auto top-up later |
| Pricing = 12 credits ($0.06) per generation | DB pricing rows | **Set our rows to match** |
| Free endpoints (details/persona/cover = 0) | verify our pricing rows are 0 | Align |
| Split Stem (50) / Advanced (20) tiers | single stems op | Add stem tiers if Suno supports |
| Separate `client/v1` portal API | panel uses same core API | Not required; note only |
| `uniqueid` anti-abuse header | none | Optional hardening |

### 9.12 Pricing parity (theirs vs. our defaults)

1 credit = $0.005 on both sides.

| Endpoint | sunoapi.org | Our default (REQUIREMENTS §6 / migrations) | Delta |
|---|---|---|---|
| Music generation (2 tracks) | 12 | 9 | we are cheaper |
| Extend | 12 | 9 | cheaper |
| Upload + cover / extend | 12 | 9 | cheaper |
| Add vocals / instrumental | 12 | 9 | cheaper |
| Sounds | 2.5 | 9 | **we are 3.6× more expensive** |
| Stems / vocal separation | 10 | 9 | ~parity |
| Split Stem | 50 | n/a | **missing tier** |
| Advanced stem split | 20 | n/a | **missing tier** |
| Replace section | 5 | 9 | we are pricier |
| Create music video (MP4) | 2 | 5 | we are pricier |
| Lyrics | 0.4 | 2 | we are 5× pricier |
| Cover image | 0 | 5 | **they are free, we charge** |
| Generate persona | 0 | 9 | **they are free, we charge** |
| Convert to WAV | 0.4 | 3 (`wav_download`, per `0018`) | we are 7.5× pricier |
| Timestamped lyrics | 0.5 | 1 | we are pricier |
| Boost music style | 0.4 | 9 | we are ~22× pricier |
| **All `record-info` / detail endpoints** | **0** | **1** | **they are free, we charge** |
| Get remaining credits | 0 | — | parity |
| Credit packs | $5/1k · $50/10k · $500/105k · $1250/275k | $5/1k · $25/5k · $100/20k | different tiers |

> Because pricing lives in the `pricing` / `credit_packs` tables, **matching them is an admin-data
> task, not a code change** — but note we'd be *lowering* revenue on several endpoints
> (detail endpoints → free, cover image/persona → free) while *raising* it on stems tiers.

### 9.13 Live generation — verified contract (spent 12 credits, user-approved)

One real V6 generation was submitted from the playground. Credits went **1,342.8 → 1,330.8**
(exactly **12**). Dashboard 24h count went 32 → 33, 100% success.

**1) POST `/api/v1/generate` — request actually sent by their own UI**

```json
{"callBackUrl":"playground","style":"","title":"","customMode":false,"instrumental":false,
 "model":"V6","prompt":"A short calm ambient piano instrumental","lyrics":"",
 "imageUrls":[],"videoUrls":[],"audioUrls":[]}
```

Response (HTTP 200):

```json
{"code":200,"msg":"success","data":{"taskId":"6bf6525143de49076a519a442a9207bc"}}
```

Notes: the UI uses a sentinel `callBackUrl:"playground"` and polls instead of a real webhook.
All fields are always sent (empty `style`/`title`/`lyrics` and empty arrays), so the upstream
tolerates explicit empties.

**2) GET `/api/v1/generate/record-info?taskId=…` — full success payload**

Envelope `{code,msg,data}`; `data` fields:

```jsonc
{
  "taskId": "…",
  "parentMusicId": "",
  "param": "<the normalized request echoed as a JSON *string*: model, prompt, callBackUrl, arrays…>",
  "response": {
    "taskId": "…",
    "sunoData": [ { /* track 1 */ }, { /* track 2 */ } ]
  },
  "status": "SUCCESS",             // PENDING | TEXT_SUCCESS | FIRST_SUCCESS | SUCCESS | …_FAILED
  "type": "chirp-hawk",            // V6 maps to chirp-hawk
  "operationType": "generate",
  "errorCode": null,
  "errorMessage": null,
  "createTime": 1790920965000
}
```

Each `sunoData[]` track ships **both snake_case and camelCase duplicates**:

```jsonc
{
  "id": "e5ee1374-…",
  "prompt": "[Instrumental]", "title": "Quiet Unfolding",
  "tags": "Calm ambient solo piano, …",
  "createTime": 1790921000628, "duration": 45.2,
  "audio_url":         "https://tempfile.aiquickdraw.com/r/<id>.mp3",
  "source_audio_url":  "",
  "stream_audio_url":  "https://audiostream.api.box/stream/<id>.mp3",
  "source_stream_audio_url": "https://audiostream.api.box/stream/<id>.mp3",
  "image_url":         "https://musicfile.removeai.ai/<b64>.jpeg",
  "source_image_url":  "https://cdn2.suno.ai/image_<id>.jpeg",
  "model_name": "chirp-hawk",
  // … same values again as audioUrl / sourceAudioUrl / streamAudioUrl / imageUrl / modelName
}
```

Track 1 was auto-titled/tagged; track 2 came back with empty `title`/`tags` (variation).
A 2-track generation counts as **1** against the 24h request counter.

**3) Authoritative per-operation credit map (from their account `consumeCreditsMap`)**

| Operation key | Credits |
|---|---|
| `suno_generate_v6` / `_v6_mini` / `_v6_wild` (also v3.5–v5.5) | 12 |
| `suno_extend_v6*` (and older) | 12 |
| `suno_upload_cover_v4` / `suno_upload_extend_v4` | 12 |
| `suno_add_vocals_v45_plus` / `suno_add_instrumental_v45_plus` | 12 |
| `suno_mashup` | 12 |
| `vocal-removal-separate-vocal` | 10 |
| `vocal-removal-split-stem` | 50 |
| `vocal-removal-split-stem-advanced` | 20 |
| `suno_replace_section` | 5 |
| `suno_vocal_removal_generate` | 4 |
| `suno_generate_sounds_v5/_v55/_v6/_v6_mini/_v6_wild` | 2.5 |
| `suno_mp4_generate` | 2 |
| `suno_get_lyrics` | 0.5 |
| `suno_create_lyric` | 0.4 |
| `suno_style_ai_generate` | 0.4 |
| `suno_wav_generate` | 0.4 |

**4) Portal account shape** (`localStorage.apibox_user`) includes `id, email, nickname, avatar,
credits, creditsThreshold, automaticDeductionFlag, automaticDeductionPriceId,
automaticRechargeCredits, consumeCreditsMap, apiKey, billingType, vipChannel*…` — i.e. the panel
loads the full account (and the API key) into the browser once authenticated.

---

## 10. Open questions / next research

- Exact successful generation callback payload + HTTP status from `api.sunoapi.org`
  (requires one paid generation — **needs explicit user approval to spend ~12 credits**).
- `getApiKeyList` field shape for safe-spend limits (page showed a loading state only).
- Whether media retention (14d) is enforced by deletion or by link signing.
- Their invoice/tax handling (Adyen) vs. our payment stack.

---

## Appendix A — Source URLs

- https://sunoapi.org/ · /blog · /changelog · /login · /dashboard · /billing · /api-key
- https://docs.sunoapi.org/ · /llms.txt
- OpenAPI: `/suno-api/suno-api.json`, `/suno-api/suno-voice-api.json`, `/file-upload-api/file-upload-api.json`
- Key docs pages: `generate-music`, `generate-music-callbacks`, `get-music-generation-details`,
  `convert-to-wav-format`, `get-wav-conversion-details`, `recovery-audio`,
  `separate-vocals-from-music`, `get-remaining-credits`, `quickstart`
