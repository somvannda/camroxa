# Music Generation Reliability, Logs Status, MP3/WAV Downloads - Implementation Plan

> Each task maps to Acceptance Criteria in spec.md (AC-1 .. AC-9). Tasks are ordered by dependency: backend-first, shared components second, pages third, smoke tests last.

## Task 1: Add cross-account retry in backend music workers + pool.retry() helper
- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - Modify `server.ts` workers `runClipJob` and `runResultJob` (or wrappers around pool.pick + submit) to auto-retry the submission/worker `runClipJob`/`runResultJob` operation across multiple distinct pool accounts (up to 3 times or until accounts exhausted) when error contains `captcha`, `timed out`, `rate limit`, or is a 5xx.
  - Implement by looping `pool.pick(excludePreviousAccountId)` up to N times before finalizing error state, OR pass `excludeAccountIds` parameter.
  - Make sure we only bill the key ONCE (not on retries) — i.e. charge only after at least one `status=complete`? Or charge before, but refund on retries? Choose: charge at finalizeJob on success (current code charges upfront before run). Move `charge(key, cost)` call AFTER `runClipJob/runResultJob` succeeds, OR if charge was already charged on first pick, on retry we do NOT double-charge — keep a `charged` flag. Keep existing `pickUserKey` preflight check so 402 returns before any retry loop.
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - `rule` TR-1.1: Submit a job that simulates 2 failed attempts + 1 success; verify the final `status=complete` (and usage_logs row has status=complete, not error)
    - Evidence: Backend terminal logs showing "retry attempt 1 (account A) failed captcha timeout, retry attempt 2 (account B) success" — or unit test that counts call count to submit() via mock
  - `rule` TR-1.2: Credits are charged at most once per successful job (no double-charge on retries)
    - Evidence: before/after credits on API key. Run retry scenario, credits delta equals exactly the costFor(endpoint), not cost*retry_count. Check by GET /backend/me/keys credits_before vs credits_after
  - `rule` TR-1.3: If all N accounts fail, final job.status = error and job.error concatenates "All X attempts failed: reasons". Credits refunded to key when final failure (because charge-after-success) OR documented behavior
    - Evidence: curl or browser Network for /me/task/:id returns status=error, error=composite message

## Task 2: Add Retry button to useJob hook + playground error banners
- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - Add `retry()` function to the `useJob()` hook return object in `components/playground.tsx`. Retry simply re-invokes last submitted path + body stored in closure state.
  - Modify `OutputTabs` and any error banner in result card area: when status=error, display a Retry button alongside "Dismiss/Reset" that calls retry().
  - Store `lastSubmit = { path, body }` inside useJob state so retry can reproduce call.
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - `rule` TR-2.1: Click Retry produces a NEW POST and new job_id different from previous failed one
    - Evidence: Network panel screenshot of two POST /me/generate calls with 2 job_ids
  - `rule` TR-2.2: Error banner contains visible "Retry" button
    - Evidence: browser screenshot showing Retry button next to error

## Task 3: Backend — mirror every missing /v1 route to /me counterpart
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1 (can do separately but share retry loop benefit later)
- **Description**:
  - In `src/server.ts` read through ALL `/v1/<name>` route registrations (grep lines). For each route that is NOT `/v1/auth/*` or `/v1/admin/*` and does NOT already have a matching `/me/<name>` route, add a new `/me/<name>` POST (or GET where appropriate) counterpart.
  - Mirror patterns: `requireAuth(req, reply)`, `pickUserKey(u.id, cost)`, `charge(key, cost)` (after success if Task 1 is ready, else charge upfront consistently), `newJob(type, callbackUrl?)`, then `runClipJob(job, client, () => client.<operation>(<params>))` or `runResultJob` same as /v1 version.
  - Mirror these specific known endpoints (confirmed missing from quick scan):
    - `/me/wav` (downloadUrl wav? or separate wav route; matches /v1/wav)
    - `/me/upload-init` or `/me/upload_init`
    - `/me/upload_register`
    - `/me/upload_extend`
    - `/me/upload_cover`
    - `/me/midi` / `/me/midi_generate`
    - `/me/mp4` / `/me/mp4_generate`
    - `/me/denoise`
    - `/me/boost` / `/me/boost_style`
    - `/me/remaster`
    - `/me/remix`
    - `/me/add_vocals`
    - `/me/add_instrumental`
    - `/me/cover_music`
    - `/me/cover_image`
    - `/me/mashup`
    - `/me/lyrics_detail`
    - `/me/timestamped_lyrics`
    - `/me/voice_apply`
    - `/me/voice_extend`
    - `/me/extend` (extend_music / extend_clip)
  - Ensure each route validates required body fields identically to its `/v1/*` counterpart (same 400 validation messages).
- **Acceptance Criteria Addressed**: AC-3, AC-8
- **Test Requirements**:
  - `rule` TR-3.1: Count equality: number of non-auth non-admin /v1/* == number of /me/* counterparts that are for the same operation
    - Evidence: grep counts: `rg '"/v1/' -c` minus `rg '"/v1/(auth|admin)' -c` == `rg '"/me/' -c` minus `rg '"/me/(auth|login|signup|task|logs|usage|billing|keys|me|download|jobs|running)' -c`
  - `rule` TR-3.2: Each new /me route returns 401 without token, 400 without required body field (validation messages match /v1/*)
    - Evidence: curl or RunCommand `(Invoke-WebRequest -Method POST /backend/me/midi -Body '{}' -UseBasicParsing).StatusCode == 400`
  - `rubric` TR-3.3: Breadth & correctness of implementation; scale 1-5, 1 = 3+ routes missing or using wrong job type; 3 = all present, some field mappings imperfect; 5 = 100% of mappings match /v1/* params exactly. Pass threshold >= 4
    - Evidence: side-by-side text diff of body destructuring between /v1/X and /me/X for 5 randomly chosen routes

## Task 4: Backend /me/download endpoint + helper clip ownership guard
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 3 (ordering — doesn't share code, just separate route)
- **Description**:
  - Add `/me/download?clip_id=<id>&format=mp3|wav` GET endpoint.
  - Flow: requireAuth → pick a pool client via pool.pick() → call `client.downloadUrl(clip_id, format)` → return JSON `{ url }` OR return HTTP 302 redirect (choose: 302 so browser downloads).
  - Charge: either 0 cost (no credits) since the clip was already generated, OR charge a tiny costFor("download") — use costFor("download") fallback to 0 if pricing not set.
  - Validation: format must be one of mp3/wav (400 otherwise); clip_id required (400).
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - `rule` TR-4.1: `GET /backend/me/download?clip_id=missing&format=mp3` with no clip_id → 400
    - Evidence: curl output StatusCode = 400
  - `rule` TR-4.2: `GET /backend/me/download?format=ogg` → 400 "format must be mp3|wav"
    - Evidence: StatusCode=400 + error body contains format validation
  - `rule` TR-4.3: Happy path (real valid clip id): returns 302 Location header or {url} with non-empty url pointing to cdn/hosted audio
    - Evidence: curl response

## Task 5: Backend — GET /me/jobs/running endpoint (live in-memory jobs for user)
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: None
- **Description**:
  - Add `/me/jobs/running` GET. RequireAuth → iterate the global `jobs` Map, filter jobs where `job.userId === u.id` and `job.status in ('pending','running','streaming')`, return as array of `{ job_id, type, status, endpoint, created_at, prompt, progress? }` (created_at = approximate; add `job.createdAt = Date.now()` in newJob helper if not already).
  - Add `createdAt: number` to Job interface and set in newJob.
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `rule` TR-5.1: Submit a job and while running, GET /me/jobs/running returns array containing that job_id with status=pending|running
    - Evidence: fetch + JSON parse includes job_id
  - `rule` TR-5.2: After finalize status complete, job disappears from /me/jobs/running within 5s
    - Evidence: second call returns empty list

## Task 6: Playground shared components — add download buttons & audio player to clips rendering
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 4 (needs /me/download URL pattern)
- **Description**:
  - Modify `ClipsOverview` in `components/playground.tsx` — under each clip's `<audio>` player row add a `flex gap-2` bar with two small buttons `Download MP3` and `Download WAV` that navigate to `/backend/me/download?clip_id=<id>&format=mp3` with `target="_blank" rel="noreferrer"` AND also add a `?force_download=1` query parameter for backend to add Content-Disposition attachment.
  - Add `force_download` query param handling to `/me/download` (Task 4 if Task 4 done; otherwise update it in Task 6): when `1`, wrap in a backend proxy route that fetches the upstream URL and pipes with `Content-Disposition: attachment; filename=<title-safe-slug>.<format>`.
  - Retry button (Task 2's button) should show inside error Output area.
- **Acceptance Criteria Addressed**: AC-6, AC-7
- **Test Requirements**:
  - `rule` TR-6.1: Each clip card in OutputTabs Overview shows 1 audio element + 2 buttons (MP3, WAV).
    - Evidence: browser_snapshot of rendered clip card — count of audio=1, button>2 including both words MP3/WAV.
  - `rule` TR-6.2: Clicking Download MP3 opens/downloads a file (network request fires).
    - Evidence: Network panel shows GET /me/download ... format=mp3 with Status 200/302

## Task 7: Rewrite dashboard Logs page — merged DB rows + live running jobs, status chips with Success/ok, expand rows, downloads
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 4, Task 5, Task 6 (uses /me/jobs/running and /me/download patterns + download buttons)
- **Description**:
  - Rewrite `web-user/app/dashboard/logs/page.tsx` completely:
    - Load both `/me/logs` (DB rows) and `/me/jobs/running` (live). Merge newest-first with live rows taking precedence over any stale DB row with same task_id. Live rows should appear at the top if they are newer.
    - Add 5s polling: while `liveRows.some(r => status in ('pending','running'))`, keep polling `/me/jobs/running` every 5s and merge. Stop when all finished.
    - Redesign status chips:
      - `complete` → emerald chip with check icon + "Success · ok" text. Use existing `var(--emerald)`.
      - `error` → red chip with X icon and "Failed" text
      - `running` → indigo/blue chip with spinner pulse + "Running" text
      - `pending` → grey chip, "Pending"
    - Each row → click to expand row. Expanded row: shows `result_json` rendered via the shared `ClipsOverview` component (import from `components/playground.tsx`) OR generic `ResultOverview`. That way clips automatically show audio player + Download MP3/WAV buttons (inherited from Task 6).
    - Add column "Type" (endpoint), "Created", "Status", "Credits", "Actions" — actions are "Downloads" (disabled until row has clips).
    - Keep responsive (mobile: horizontal scroll overflow-x-auto).
- **Acceptance Criteria Addressed**: AC-5, AC-6, AC-9
- **Test Requirements**:
  - `rule` TR-7.1: Page renders at least one row with emerald "Success · ok" chip for a complete row
    - Evidence: screenshot of Logs with visible green chip containing "ok"
  - `rule` TR-7.2: Expand row → clips overview rendered with both Download buttons visible
    - Evidence: expanded row screenshot + count of buttons
  - `rule` TR-7.3: Running jobs appear in Logs without page refresh on 5s poll
    - Evidence: submit job, go to logs, wait ~7s, row appears with Running chip
  - `rule` TR-7.4: After hard browser refresh (Ctrl+F5), DB rows still show emerald Success/ok chip
    - Evidence: before & after refresh screenshots — same green badge

## Task 8: Full diagnostics + e2e smoke run
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Tasks 1..7
- **Description**:
  - Run `GetDiagnostics` until clean. Also run backend `npx tsc --noEmit` (or `npm run check`) or if no check script exists, just rely on GetDiagnostics + quick browser console errors check.
  - Quick smoke test: Login → submit Music Generation prompt → observe: logs page shows Running then (if upstream works) Success/ok green chip with "ok". Retry button appears on captcha fail. Download MP3 + WAV fire network requests. Check 5 random /me/* routes from Task 3 all respond non-500 with invalid params.
- **Acceptance Criteria Addressed**: AC-8, all final integrity checks
- **Test Requirements**:
  - `rule` TR-8.1: GetDiagnostics result = empty array
    - Evidence: tool output "[]"
  - `rule` TR-8.2: Logs page console shows no errors
    - Evidence: browser console messages filtered by error: 0 lines
  - `rubric` TR-8.3: Endpoint breadth score (same rubric as AC-8)
    - Scale 1-5; anchors same as AC-8; pass >= 4
    - Evidence: results from curl/RunCommand smoke
