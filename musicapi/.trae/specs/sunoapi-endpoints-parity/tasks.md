# Complete SunoAPI Endpoints Parity — Implementation Plan

## Task 1: Browser capture — Agree to Terms → Upload dialog file picker → capture policy endpoint URL + shape
- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - Click Agree to Terms in upload dialog → show file picker / upload form.
  - If possible, simulate selecting a file OR programmatically triggering form submit that will be intercepted BEFORE actual upload (we only care about the policy endpoint URL + response shape for step 1 and step 3 register URL, not actual S3 upload).
  - Capture window.__ALL_CALLS and extract any `/api/clip/*` or `/api/upload/*` calls.
- **Acceptance Criteria Addressed**: AC-7, FR-1
- **Test Requirements**:
  - `rule` TR-1.1: After clicking through dialog, `window.__ALL_CALLS` contains at least one `/api/` POST with a path different from notification endpoints.
  - `rubric` TR-1.2: Upload policy endpoint discovery quality; scale 1-5; 1=0 new URLs captured, 3=at least one new /api/* URL and method found, 5=step-1 policy URL captured with response body containing {id, url, fields}; evidence browser_evaluate calls.

## Task 2: API probe — round 9 — all path candidates for upload / mp4 / voice / midi / recovery / detail endpoints
- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - Create `scripts/probe-endpoints-round9.ts` using existing rawRequest pattern.
  - Probe: GET/POST `/api/clip/{clip_id}/upload`, `/api/clip/{clip_id}/audio_upload`, `/api/clip/{clip_id}/create-upload`, `/api/clip/{clip_id}/policy`, `/api/upload/policy`, `/api/audio/upload/policy`, `/api/video_gen/mp4/generate`, `/api/mp4/generate`, `/api/clip/{clip_id}/mp4`, `/api/video_gen/mp4`, `/api/midi/generate`, `/api/clip/{clip_id}/midi`, `/api/midi`, `/api/clip/{clip_id}/recovery`, `/api/recovery`, `/api/boost`, `/api/clip/{clip_id}/boost`, `/api/generate/boost`, `/api/clip/{clip_id}/subtitles`, `/api/clip/{clip_id}/lyrics`, `/api/clip/{clip_id}/detail`, `/api/vox/*`, `/api/voice/*`, `/api/persona/*`
  - For each, check: 404 = not exists, 405 = route exists (different method / path param), 401 = authenticated route (exists), 422 = schema-validated (exists — we can read missing fields).
- **Acceptance Criteria Addressed**: AC-8, FR-1 through FR-8
- **Test Requirements**:
  - `rule` TR-2.1: Script exits 0 (paid pool client loads + requests fire without exception).
  - `rubric` TR-2.2: Schema discovery yield; scale 1-5; 1=all 404, 3=two or more 405/422/200 narrowing schemas, 5=4+ endpoint URLs confirmed with response shapes; evidence printed CLI output + `exit 0`.

## Task 3: Add client methods — upload 3-step (createAudioUpload + registerAudioUpload) + detail methods (lyricsDetail, wavDetail, stemsDetail, videoDetail, coverDetail, subtitleDetail, recoveryDetail, mp4Detail, midiDetail)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1 (optional shape verification; if fails use midify.top /suno/* pattern translated to Suno base) + Task 2
- **Description**:
  - Add to `src/client.ts` imports + methods.
  - Upload step 1: POST to discovered policy path with body {extension, upload_type, last_upload_id?}. Use ensureCaptchaToken if not read-only.
  - Upload step 3: POST to register path with upload_id.
  - Detail methods: GET `/api/clip/{clip_id}/...` patterns.
- **Acceptance Criteria Addressed**: FR-9, FR-10, FR-16, AC-9
- **Test Requirements**:
  - `rule` TR-3.1: Methods declared, exported (no default), called at least once in test probe script without TS error.
  - `rubric` TR-3.2: Method interface cleanliness; scale 1-5; 1=duplicated code / mixed concerns, 3=all methods present uniform signature, 5=all methods uniform signature + ensureCaptchaToken on every write path; evidence from code review.

## Task 4: Add client methods — recoveryAudio, generateMP4, boostStyle, generateMIDI, voiceOps (phrase, validate, record, generate, apply)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 2 (schema confirmation)
- **Description**:
  - If `v2-web` task enum supports via 422, submit those tasks via submitClips so they inherit captcha + common payload handling.
  - If direct endpoint (like `video_gen/mp4/generate` parallel to `video_gen/image/generate`), call `.request()` with ensureCaptchaToken wrapper + token field in body.
  - Voice ops: match midify.top /persona + /vox paths or use `/api/persona/*` based on probes.
- **Acceptance Criteria Addressed**: FR-11, FR-12, FR-13, FR-14, FR-15, AC-9
- **Test Requirements**:
  - `rule` TR-4.1: Compiles (tsc --noEmit exit 0).
  - `rubric` TR-4.2: Captcha coverage; scale 1-5; 1=3+ write ops missing token injection, 3=all submitClips paths, 5=100% write ops include token; evidence grep output lines.

## Task 5: server.ts — extend Job.type union, DEFAULT_COSTS, costFor entries for all new types
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Tasks 3 + 4
- **Description**:
  - Add Job.type entries: `"upload_init" | "upload_register" | "recovery_audio" | "mp4_generate" | "boost_style" | "midi_generate" | "voice_phrase" | "voice_validate" | "voice_record" | "voice_generate" | "voice_apply" | "lyrics_detail" | "wav_detail" | "stems_detail" | "video_detail" | "cover_detail" | "subtitle_detail" | "recovery_detail" | "mp4_detail" | "midi_detail"`.
  - Add DEFAULT_COSTS: 9 for generation-class ops, 1 for detail-class endpoints, 5 for mp4/video class.
  - Update `costFor()`: return DB values or fallback to DEFAULT_COSTS.
- **Acceptance Criteria Addressed**: FR-18, NFR-4, AC-5
- **Test Requirements**:
  - `rule` TR-5.1: `costFor(<every new type>)` invoked in script returns a number (never NaN / undefined).
  - `rubric` TR-5.2: Pricing consistency; scale 1-5; 1=some types have cost undefined, 3=all have numbers, 5=DB pricing upserted via scripts/update-pricing.ts AND all fallback correct; evidence SELECT * FROM pricing CLI output.

## Task 6: server.ts — add all 25 new v1 routes (upload 2, recovery 2, lyrics detail 1, wav/stems/video/cover/subtitle detail 5, mp4 2, boost 1, voice 5, midi 2)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 5
- **Description**:
  - Pattern: each route validate inputs → `cost = await costFor(type)` → `await charge(key, cost)` → 402 on failure → `newJob(type, callbackUrl?)` → `pool.pick()` → `runResultJob` (for detail endpoints, upload init/register) or `runClipJob` (for generation-class ops that produce clips).
  - Each route return 202 {job_id, status: "pending"} immediately for async jobs; detail endpoints may optionally return 200 if synchronous, but follow existing pattern of returning 202 + job_id (consistency with user expectations).
- **Acceptance Criteria Addressed**: FR-17, FR-19, AC-1, AC-2, AC-3
- **Test Requirements**:
  - `rule` TR-6.1: No new route 404s in smoke test (all registered).
  - `rule` TR-6.2: All new routes return route-specific 400 validation message when auth-present but body empty `{}`.
  - `rubric` TR-6.3: Route handler consistency; scale 1-5; 1=mixed error messages, 3=each handler matches existing patterns, 5=each handler validates, charges, creates Job, dispatches, no leaked raw errors; evidence CLI smoke-test output.

## Task 7: Update seed.ts + update-pricing.ts — insert rows for all new endpoint types, run update-pricing.ts, query SELECT output
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: Task 5 (types finalized)
- **Description**:
  - Extend pricing array in seed.ts with all new endpoints matching DEFAULT_COSTS from Task 5.
  - Extend update-pricing.ts upsertPrice() to include all new endpoints.
  - Run `npx tsx scripts/update-pricing.ts`.
  - Query `SELECT endpoint, credit_cost FROM pricing ORDER BY endpoint` and paste result into completion evidence.
- **Acceptance Criteria Addressed**: AC-5, NFR-4
- **Test Requirements**:
  - `rule` TR-7.1: Both scripts exit 0.
  - `rule` TR-7.2: Pricing row count >= 25 (17 existing + 8+ new).

## Task 8: TypeScript 0 errors diagnostics — tsc --noEmit + GetDiagnostics
- **Status**: `pending`
- **Priority**: high
- **Depends On**: All Tasks 1-7 complete
- **Description**:
  - Run `npx tsc --noEmit` from project root.
  - Run VSCode `GetDiagnostics`.
  - Fix any errors surfaced.
- **Acceptance Criteria Addressed**: NFR-1, AC-4
- **Test Requirements**:
  - `rule` TR-8.1: `npx tsc --noEmit` exit code 0 AND no stdout.
  - `rule` TR-8.2: `GetDiagnostics` returns empty array `[]`.

## Task 9: Restart server, run all 3-tier smoke tests (no auth 401, valid auth missing fields 400, valid body 202)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 8 (clean diagnostics)
- **Description**:
  - Kill any process on port 3000; re-start serve.ts with new code.
  - Run existing smoke-test-routes, smoke-test-auth, smoke-test-valid-body scripts plus augment with new routes (write `scripts/smoke-test-all-v1-routes.ts` that enumerates every single route we have including legacy ones).
  - Capture output.
  - Do one live pool.pick() generation test to confirm paid account routing intact.
- **Acceptance Criteria Addressed**: NFR-2, NFR-3, AC-1, AC-2, AC-3
- **Test Requirements**:
  - `rule` TR-9.1: Server starts with console line "accounts=2".
  - `rule` TR-9.2: 401 pass count == total routes (0 404s).
  - `rule` TR-9.3: 400 pass count == total routes (route-specific validation messages).
  - `rule` TR-9.4: Valid-body 202 count >= number of async routes.
  - `rubric` TR-9.5: E2E generation health; scale 1-5; 1=paid account routing fails, 3=dispatch works but generation fails (ok, captcha / upstream limit), 5=dispatch to paid account status running returned from GET /v1/task/:id.

## Task 10: Update REQUIREMENTS.md (sections 6 pricing table, 8 current/planned endpoints, 9 NFR captcha, 10 phasing)
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: Task 9
- **Description**:
  - Flip all newly-implemented endpoints from [PENDING] → [DONE] in section 8.
  - Expand section 6 pricing table with new endpoints.
  - Update section 10 phasing milestones.
  - Leave only unreachable endpoints (if any from Task 1/2 failures) as [PENDING] or [PARTIAL] with inline explanation.
- **Acceptance Criteria Addressed**: AC-6
- **Test Requirements**:
  - `rule` TR-10.1: Count of [DONE] endpoints in section 8 >= 25.
  - `rule` TR-10.2: Section 6 pricing table rows >= 25.

## Task 11: Update web-user public docs app/docs/page.tsx ENDPOINTS array with all new routes + param tables
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: Task 10
- **Description**:
  - Add public-facing doc entries for all 25+ new endpoints with method badges, param tables (name required description columns), and example curl snippets for the key endpoints (upload 2-step, mp4 generate, MIDI, voice ops).
  - Append to the ENDPOINTS array before the GET /v1/task/:id entry.
- **Acceptance Criteria Addressed**: AC-6
- **Test Requirements**:
  - `rule` TR-11.1: `ENDPOINTS.length` >= 40 (17 existing + 23 new).
  - `rubric` TR-11.2: Doc quality; scale 1-5; 1=routes listed w/o params, 3=params for 60%+, 5=every new endpoint has param table, at least 3 have curl example, model table intact; evidence code file grep output or snippet.

## Task 12: Independent Review (Review phase of spec mode)
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: All tasks 1-11 completed
- **Description**:
  - Create `.trae/specs/sunoapi-endpoints-parity/review.md` with checkpoints.
  - Run one final tsc + server start + smoke test snapshot as independent reviewer.
  - Result: `pass` / `fail` / `blocked`.
- **Acceptance Criteria Addressed**: All AC
- **Test Requirements**:
  - `rule` TR-12.1: All review checkpoints have evidence (not "Pending").
  - `rubric` TR-12.2: Workflow fidelity; scale 0-2; 0=phases collapsed, 1=one boundary mistake, 2=all five phases followed; per spec mode rubric definition.
