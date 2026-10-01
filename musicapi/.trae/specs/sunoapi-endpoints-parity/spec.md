# Complete SunoAPI Endpoints Parity — Product Requirements Document

## Overview
- **Summary**: Implement all remaining SunoAPI endpoints so Camxora Music API reaches 100% parity with docs.sunoapi.org / openapi.midify.top endpoints. Endpoints: upload 3-step (init policy → S3 upload → register), MP4 video generate + detail, timestamped lyrics + lyrics detail, WAV detail, vocal-separation (stems) detail, video / cover detail, subtitle detail, recovery audio + detail, boost music style, Suno Voice 6 operations (phrase / validate / record / generate / apply), MIDI generate + MIDI detail.
- **Purpose**: Reach full commercial feature parity with sunoapi.org so user can sell a functionally identical API product.
- **Target Users**: End-user API consumers + Camxora operator user/admin panels.

## Goals
- Add ~25 remaining v1 endpoints covering upload, video, voice, MIDI, recovery, boost, subtitles, and per-task detail endpoints.
- Add all client methods + Job processors + credit pricing rows + v1 routes.
- Pass TypeScript 0 errors, server starts, all routes return correct 401/400/202 status in curl smoke tests.
- Maintain REQUIREMENTS.md DONE/PARTIAL/PENDING legend and public docs page.
- Reverse-engineer any unknown endpoint schemas by combination of: (a) live browser XHR capture from signed-in paid account UI, (b) openapi.midify.top docs extrapolation, (c) API probing against paid pool account via rawRequest.

## Non-Goals
- No UI changes to web-user / web-admin beyond updating public docs and REQUIREMENTS.md; only update sidebar links if easy.
- No migration to Redis queue (stays in-memory per existing architecture).
- No refactor of captcha.ts / pool.ts; keep as-is.
- No change to auth or billing/credits architecture.

## Background & Context
- Already 17 endpoints implemented and verified (401/400/202) in prior session; 8+ categories of endpoints remain.
- Browser (viewId 5cb5942b) has user `iamduke1987@gmail.com` signed in; fetch/XHR interceptor installed (`window.__ALL_CALLS`); reset for fresh capture.
- Paid account pool: pool.size=2, paid account type=paid (boolean) confirmed via probe.
- 405 route pattern discovered `/api/clip/upload` etc — path variants under `/api/clip/{segment}` for upload policy; need click-through upload dialog to trigger.
- Suno base URL: `https://studio-api-prod.suno.com`; upload bucket `https://suno-uploads.s3.amazonaws.com/` confirmed from midify.top docs.

## Functional Requirements

### Endpoints to implement (8 categories, ~25 routes total):
- **FR-1 Upload 3-step**: `POST /v1/upload/init` (extension, upload_type → S3 policy + url + fields), `POST /v1/upload/register` (upload_id → clip_id registered for upload_extend / cover_infill).
- **FR-2 Recovery audio**: `POST /v1/music/recovery`, `GET /v1/music/recovery/:task_id`.
- **FR-3 Timestamped lyrics + lyrics detail**: `GET /v1/lyrics/:task_id` (detail), timestamped lyrics fields in task result.
- **FR-4 WAV detail + vocal-sep detail + video/cover detail**: `GET /v1/music/wav/:task_id`, `GET /v1/music/stems/:task_id`, `GET /v1/music/video/:task_id`, `GET /v1/music/cover/:task_id`, `GET /v1/music/subtitle/:task_id`.
- **FR-5 Music video (MP4)**: `POST /v1/mp4/generate` (clip_id → async video), `GET /v1/mp4/:task_id` (details + video_url).
- **FR-6 Boost music style**: `POST /v1/generate/boost` (clip_id + style prompt).
- **FR-7 Suno Voice 6 operations**: phrase, validate, record, generate, apply (per sunoapi.org voice flow spec).
- **FR-8 MIDI**: `POST /v1/music/midi` (clip_id → generate MIDI), `GET /v1/music/midi/:task_id` (MIDI download URL + details).

### Client.ts Methods Required:
- **FR-9**: `createAudioUpload(extension, upload_type?, last_upload_id?)` → returns {id, url, fields}
- **FR-10**: `registerAudioUpload(uploadId)` → returns clip_id / task_id
- **FR-11**: `generateRecoveryAudio(clipId)` → returns task id / Job
- **FR-12**: `generateMP4(clipId, params?)` → async task
- **FR-13**: `boostStyle(clipId, stylePrompt)` → submitClips or direct
- **FR-14**: `generateMIDI(clipId)` → task
- **FR-15**: Voice phrase / validate / record / generate / apply methods
- **FR-16**: Detail fetchers (lyricsDetail, wavDetail, stemsDetail, videoDetail, coverDetail, subtitleDetail, mp4Detail, midiDetail, recoveryDetail)

### Backend Routes Required (charge credits via costFor → charge):
- **FR-17**: All 25 new v1 routes validate inputs → 400 on missing fields.
- **FR-18**: Each new type requires Job.type union entry + DEFAULT_COSTS entry + DB pricing row.
- **FR-19**: runClipJob / runResultJob used consistently (clip ops → runClipJob, simple POST → runResultJob).
- **FR-20**: All 3 remaining non-clip sites (if any) get ensureCaptchaToken (already done for createPersona, generateCoverImage, downloadUrl; extend to any new non-clip ops found by probe).

## Non-Functional Requirements
- **NFR-1**: `npx tsc --noEmit` passes 0 errors (rule, verifiable via CLI exit 0).
- **NFR-2**: Server starts with `npm run serve` without throwing, pool.size=2 confirmed (captured console output).
- **NFR-3**: Each new v1 route passes 3-tier curl smoke test: no auth → 401, valid auth but missing required params → 400 with route-specific message, valid auth+valid body → 202 + {job_id, status:"pending"}.
- **NFR-4**: Credit cost read from DB pricing table; DEFAULT_COSTS in server.ts are the fallback only.
- **NFR-5**: Captcha solve paid only when `/api/c/check` required=true (no-op solve otherwise).

## Constraints
- **Technical**: PostgreSQL local only, no Docker. Server Fastify + TypeScript; upload flow uses same studio-api-prod.suno.com base (different from midify.top /suno/* wrapper paths). Midify.top paths are Wrapper-only, not Suno-direct. Reverse-engineer direct Suno endpoint paths from UI calls or probes.
- **Business**: Pricing admin-configurable; no hardcoded credit amounts (DB is source of truth). 2Captcha only paid when required=true.
- **Dependencies**: Existing @2captcha/captcha-solver + playwright-core already installed. aws-sdk v2/v3 NOT installed (S3 signed uploads are client-responsibility via step-2 midify-style; we only issue policy+fields, never host or upload files).

## Assumptions
- Upload policy endpoint is some variant of `/api/clip/{?}/...` since probe-clip-upload found 405 pattern `/api/clip/upload`, `/api/clip/audio_upload`, `/api/clip/audio-upload`, `/api/clip/create-upload` (POST 405 → GET or `/api/clip/{segment}/upload`).
- Recovery audio, boost, mp4, midi, voice ops all go through `/api/generate/v2-web/` with task discriminator similar to mashup/upload_extend.
- Detail endpoints likely GET against `/api/clip/{clip_id}/...` segments or `/api/download/...`.
- If any endpoint cannot be discovered via probe + browser within reasonable attempts, implement routes as placeholder with documented task shapes matching midify.top docs (so API surface exists even if upstream payload not yet fully aligned, requiring one more click-through to capture final shape).

## Acceptance Criteria

### AC-1: All 25+ new v1 routes registered in Fastify + responding 401 to unauthed request
- **Type**: `rule`
- **Given**: Server started, no changes to port 3000.
- **When**: `scripts/smoke-test-routes.ts` hits every new route with POST {} or GET and no Authorization header.
- **Then**: Every route responds 401 JSON `{"error":"Invalid or missing API key."}` (no 404s).
- **Pass Condition**: 0 routes return 404; all 401 with correct JSON shape.
- **Evidence**: CLI command output captured in task.md completion evidence per route.

### AC-2: Valid auth + missing required params returns 400 with route-specific message
- **Type**: `rule`
- **Given**: Auth via `Authorization: Bearer sk-test-123` (seeded test key with 500 credits).
- **When**: Smoke-test-auth runs against each route with empty/minimal body `{}`.
- **Then**: Each route returns 400 with a route-specific validation error (e.g., upload/init requires "extension").
- **Pass Condition**: All routes 400 with descriptive message unique to the route; no 500s.
- **Evidence**: CLI output.

### AC-3: Valid auth+valid body returns 202 with job_id for async routes
- **Type**: `rule`
- **Given**: Test API key has >= 100 credits remaining (topped up).
- **When**: POST every new async route with valid (possibly placeholder) body.
- **Then**: Response HTTP 202, JSON contains `job_id` UUID string + `status: "pending"`.
- **Pass Condition**: All new async routes 202 with job_id. Synchronous result routes may return 200.
- **Evidence**: CLI output.

### AC-4: TypeScript zero errors
- **Type**: `rule`
- **Given**: Project root (e:\Development\SunoAPI).
- **When**: `npx tsc --noEmit`.
- **Then**: Exit code 0, no stdout output.
- **Pass Condition**: 0 diagnostic errors.
- **Evidence**: CLI exit status + stdout.

### AC-5: Pricing rows in DB for every new endpoint
- **Type**: `rule`
- **Given**: PostgreSQL dbname sunoapi, user postgres, password postgres.
- **When**: `SELECT endpoint, credit_cost FROM pricing ORDER BY endpoint;` query after running update-pricing.
- **Then**: Every new endpoint appears with credit_cost matching DEFAULT_COSTS.
- **Pass Condition**: Count of pricing rows >= 17 (current total) + new count.
- **Evidence**: SELECT output pasted.

### AC-6: REQUIREMENTS.md + public docs updated with new endpoints
- **Type**: `rubric`
- **Dimension**: Completeness of documentation coverage for new endpoints.
- **Scale**: 1-5
- **Anchors**: 1 = missing both files; 3 = REQUIREMENTS.md updated but public docs missing param tables for half; 5 = REQUIREMENTS.md DONE legend updated for every endpoint AND public docs page has param table with required desc for every new route.
- **Pass Threshold**: >= 5
- **Evidence**: Diff review of both files' line-level contents.

### AC-7: Browser capture yields at least 2 unknown endpoint URL shapes, reducing unknowns
- **Type**: `rubric`
- **Dimension**: Reverse-engineering discovery throughput.
- **Scale**: 1-5
- **Anchors**: 1 = no new endpoints captured (all blind implemented); 3 = one or two new endpoint URLs captured; 5 = upload policy endpoint AND one other feature endpoint (mp4, persona, boost, midi, recovery) actual URL + response captured.
- **Pass Threshold**: >= 3
- **Evidence**: window.__ALL_CALLS JSON filtered for /api/ matches (non-notification/non-bing/clarity).

### AC-8: API probe discovers schema for at least 4 more endpoints via 422 200 responses
- **Type**: `rubric`
- **Dimension**: Probe-based schema discovery success.
- **Scale**: 1-5
- **Anchors**: 1 = all probes 404 (no new knowledge); 3 = 1 or 2 probes show path pattern; 5 = 4+ endpoint paths/schemas narrowed from 422 required-field lists or 200 OK with response.
- **Pass Threshold**: >= 3
- **Evidence**: Probe round 9+ in scripts/probe-endpoints-round9.ts, captured CLI exit status 0.

### AC-9: Captcha wiring for all new non-clip submit sites
- **Type**: `rule`
- **Given**: src/client.ts line scan.
- **When**: Grep `new client methods` for ensureCaptchaToken or submitClips usage.
- **Then**: Every new method that makes a POST to an /api/* endpoint either calls submitClips (which has ensureCaptchaToken) OR independently calls ensureCaptchaToken and attaches token to body. Download/register/policy GETs are exempt.
- **Pass Condition**: No new write-method bypasses captcha injection pattern.
- **Evidence**: grep output mapping method → capture entry point.

## Open Questions
- [ ] Does the upload flow require GET on `/api/clip/create-upload`? We'll probe that.
- [ ] Does Suno Voice 6-op require upload (step 3 pattern) or a separate `/api/vox/*` path?
- [ ] Does video generation use `/api/video_gen/mp4/generate` (parallel to `/api/video_gen/image/generate` we already used) or `/api/clip/{id}/mp4`?
