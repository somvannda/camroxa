# API Parity Checklist — our `musicapi` vs. sunoapi.org `/api/v1`

> Companion to [competitor-analysis-sunoapi-org.md](./competitor-analysis-sunoapi-org.md).
> Purpose: make our public API a **drop-in match** for `api.sunoapi.org` so any sunoapi.org
> client can switch base URL + key and keep working.
>
> Method: diff of sunoapi.org's published OpenAPI paths + live-verified responses (§9.13 of the
> analysis) against `musicapi/src/server.ts` (`PREFIX = "/api/v1"` at line 4739).
>
> Legend: ✅ match · 🔁 path mismatch (add alias) · ❌ missing (implement) · ⚠️ shape differs

---

## A. Already matching

| sunoapi.org | ours |
|---|---|
| `POST /api/v1/generate` | ✅ |
| `POST /api/v1/generate/extend` | ✅ |
| `POST /api/v1/generate/upload-cover` | ✅ |
| `POST /api/v1/generate/upload-extend` | ✅ |
| `POST /api/v1/generate/add-instrumental` | ✅ |
| `POST /api/v1/generate/add-vocals` | ✅ |
| `POST /api/v1/generate/generate-persona` | ✅ |
| `POST /api/v1/generate/mashup` | ✅ |
| `GET  /api/v1/generate/record-info` | ✅ |
| `POST /api/v1/lyrics` | ✅ |
| `GET  /api/v1/lyrics/record-info` | ✅ |
| `POST /api/v1/vocal-removal/generate` | ✅ |
| `GET  /api/v1/vocal-removal/record-info` | ✅ |
| `POST /api/v1/voice/validate` | ✅ |
| `POST /api/v1/voice/generate` | ✅ |
| `GET  /api/v1/voice/record-info` | ✅ |

## B. Path mismatches — add aliases (low risk, additive)

| sunoapi.org | our current path | action |
|---|---|---|
| `GET /api/v1/generate/credit` | `GET /api/v1/get-credits` | 🔁 add alias; also see ⚠️ B1 |
| `POST /api/v1/style/generate` | `POST /api/v1/generate/boost` | 🔁 alias |
| `POST /api/v1/wav/generate` | `POST /api/v1/convert-to-wav/generate` | 🔁 alias |
| `GET  /api/v1/wav/record-info` | `GET /api/v1/convert-to-wav/record-info` | 🔁 alias |
| `POST /api/v1/midi/generate` | `POST /api/v1/generate/midi` | 🔁 alias |
| `GET  /api/v1/midi/record-info` | `GET /api/v1/generate/midi/record-info` | 🔁 alias |
| `POST /api/v1/mp4/generate` | `POST /api/v1/create-music-video/generate` | 🔁 alias |
| `GET  /api/v1/mp4/record-info` | `GET /api/v1/create-music-video/record-info` | 🔁 alias |
| `POST /api/v1/suno/cover/generate` | `POST /api/v1/cover-suno/generate` | 🔁 alias |
| `GET  /api/v1/suno/cover/record-info` | `GET /api/v1/cover-suno/record-info` | 🔁 alias |
| `POST /api/v1/suno/recovery` | `POST /api/v1/generate/recovery` | 🔁 alias |
| `GET  /api/v1/suno/recovery/record-info` | `GET /api/v1/generate/recovery/record-info` | 🔁 alias |

**B1 — credit response shape.** Theirs returns `data` as a **bare integer**:
`{"code":200,"msg":"success","data":1000}`. Ours returns `data:{credits,name}`. The
`/api/v1/generate/credit` alias must return `data: <number>` (keep `/get-credits` as-is for our panel).

## C. Missing endpoints — implement

| sunoapi.org | gap | notes |
|---|---|---|
| `POST /api/v1/generate/get-timestamped-lyrics` | ❌ | we have the flow via `GET /api/v1/lyrics/:id` + `timestamped_lyrics_detail`; add POST alias that accepts `{taskId}`/`{audioId}` and returns a taskId |
| `POST /api/v1/generate/replace-section` | ❌ | logic exists at `/me/replace-section`, `/me/music/replace-section`, `/v1/music/replace-section`; expose under `/api/v1/generate/replace-section` |
| `POST /api/v1/generate/sounds` | ❌ | logic exists at `/v1/sounds`, `/me/sounds`; expose under `/api/v1/generate/sounds` |
| `GET  /api/v1/voice/validate-info` | ❌ | alias to verification-phrase result (ours `/api/v1/voice/record-info` shape differs — see ⚠️) |
| `POST /api/v1/voice/regenerate` | ❌ | maps to our recreate-phrase flow (`/voice/phrase`) |
| `POST /api/v1/voice/check-voice` | ❌ | **feature gap** — we have no "voice availability" check; needs a client method |
| `POST /api/file-base64-upload` | ❌ | our 3-step flow is `/api/v1/upload/init` → `/register` → `/status`; add convenience wrappers |
| `POST /api/file-stream-upload` | ❌ | as above |
| `POST /api/file-url-upload` | ❌ | as above |

### File Upload API detail (theirs)

- Separate namespace: `POST /api/file-base64-upload`, `/api/file-stream-upload`, `/api/file-url-upload`.
- Uploaded files are **temporary — auto-deleted after 3 days**.
- Returns an upload id/URL used as `audioUrls[]` in non-custom generation or as `audioId` in
  stems/replace-section.

## D. Response / behavior differences ⚠️

| Item | sunoapi.org (live-verified) | ours | action |
|---|---|---|---|
| Task creation HTTP status | **200** | `202` on `/api/v1/*` create routes | return 200 on the public surface |
| Insufficient credits | **`429`** | `402` | align to 429 on `/api/v1/*` |
| `record-info` result key | `data.response.sunoData[]` | `data.response.data[]` | add `sunoData` (and keep `data` for back-compat) |
| Track field casing | **both** `audio_url` and `audioUrl` (also image/stream/source) | depends on client payload | emit both casings in the public surface |
| `source_audio_url` | `""` (Suno original no longer surfaced) | we pass Suno links through | decide: mirror empty or keep useful |
| Status values | `PENDING/TEXT_SUCCESS/FIRST_SUCCESS/SUCCESS/*_FAILED` | our own status strings | map to their vocabulary |
| `param` | normalized request echoed as a **JSON string** | not returned | add for parity |
| `type` / `model_name` | `chirp-hawk` (V6 → chirp-hawk) | our model-key mapping exists | ensure `model_name` uses `chirp-*` |
| Callback stages | `text` → `first` → `complete`, plus `error` | our `notify()` payload | verify/align payload fields (`callbackType`, `task_id`, `data[]`) |

## E. Models

- Their current default is **`V6`** (→ `chirp-hawk`), also `V6_MINI`, `V6_WILD`; deprecated
  `V5_5/V5/V4_5PLUS/V4_5ALL/V4_5/V4`.
- Our `src/models.ts` normalises retired keys onto `chirp-hawk`/`chirp-goose` but does **not**
  explicitly map `V6`/`V6_MINI`/`V6_WILD`. Live evidence shows V6 = `chirp-hawk`; add explicit
  mappings and confirm `V6_MINI`/`V6_WILD` targets against live Suno.

## F. Suggested minimal implementation (in order)

1. **Route aliases (B)** — one additive block near the existing `PREFIX` section; no logic change.
2. **Credit shape (B1)** + **status codes (D)** — small handler tweaks on `/api/v1/*` only, so the
   panel and `/v1/*` behavior stay untouched.
3. **Missing product routes (C, minus voice)**: timestamped-lyrics, replace-section, sounds.
4. **Result adapter (D)**: emit `sunoData` + dual `snake_case`/`camelCase` fields + `param`/`type`.
5. **File Upload wrappers (C)**: base64/stream/url → existing init/register pipeline.
6. **Voice extras**: `validate-info`, `regenerate`, and the one genuine feature gap `check-voice`.
7. **Models (E)**: explicit V6 family map + live verification.

## G. Verification plan

- Extend `scripts/smoke-test-reachability.ts` (205-route sweep) with the new `/api/v1` aliases.
- Add a contract test that compares our `/api/v1/*` route table against sunoapi.org's OpenAPI
  JSON (checked into `musicapi/docs/` or fetched at test time), failing on any missing path.
- One live smoke: `POST /api/v1/generate` with a real key → poll
  `GET /api/v1/generate/record-info` → assert `response.sunoData[0].audio_url` is a playable URL.

## H. Out of scope (deliberate)

- Their `client/v1` portal API (separate backend). Our panel talks to the same core API — no need
  to clone their split.
- Marketing pages, blog, FAQ, VIP/Adyen billing, auto top-up.
- Their `uniqueid` anti-abuse header (optional hardening).

---

## I. Implementation status — 2026-10-02 (`feat/musicapi-sunoapi-parity`)

Shipped in `src/server.ts` + `src/models.ts`:

- [x] **§B path aliases** — all 13 registered (`style/generate`, `wav/*`, `midi/*`, `mp4/*`,
      `suno/cover/*`, `suno/recovery/*`, `voice/validate-info`, `voice/regenerate`), forwarding
      in-process with `app.inject` so no handler logic is duplicated.
- [x] **§B1 credit shape** — `GET /api/v1/generate/credit` returns `data` as a bare integer.
- [x] **§C missing routes** — `generate/get-timestamped-lyrics`, `generate/replace-section`,
      `generate/sounds`, `voice/check-voice` (best-effort availability), `voice/regenerate`.
- [x] **§D status codes** — `onSend` hook remaps `202→200` and `402→429` on `/api/v1/*` only.
- [x] **§D result adapter** — `record-info` now emits `status` vocabulary, `type`, `param`,
      `errorCode`/`errorMessage`, `createTime`, and `response.sunoData[]` with **dual
      snake_case/camelCase** fields (keeps `response.data[]` for back-compat).
- [x] **§E models** — `V6` → `chirp-hawk` (live-verified). `V6_MINI`/`V6_WILD` pass through
      pending live confirmation.
- [x] Verified: `npm run typecheck` clean; all 18 new routes present via `app.hasRoute`, no
      duplicate-route conflicts at `ready()`.

Done since §I was first written:

- [x] **§C file upload API** — `/api/file-base64-upload`, `/api/file-url-upload`,
      `/api/file-stream-upload` via `@fastify/multipart`, stored on B2 under `musicapi/uploads/`.
- [x] **§D callbacks** — `notify()` now emits `{code,msg,data:{callbackType,task_id,data[]}}`.
- [x] **§E models** — live-verified: V6=`chirp-hawk`, V6-WILD=`chirp-hawk-wild`,
      V6-MINI=`chirp-goose`; `normalizeModel` maps them.
- [x] **§G contract test** — `npm run test:contract` asserts all 37 sunoapi.org paths (37/37).
- [x] **Reference media** — image/audio/video wired into the API + playground and
      **live-verified** (image & audio use `user_uploaded_*_ids` + `task:"agentic_thinking"`;
      video extracts a frame via `ffmpeg-static`).

Still open:

- [ ] Live success path through the public `/api/v1/generate` (imageUrls/audioUrls) once the
      durable `__client` cookie is seeded.
- [ ] Production secret seeding (`MUSICAPI_SUNO_CLIENT_COOKIE`).
- [ ] Commit (not yet — awaiting explicit go-ahead per project ship gates).
