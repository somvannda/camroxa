# Music Generation Reliability, Logs Status, MP3/WAV Download Conversions - Product Requirements Document

## Overview
- **Summary**: Ensure every playground API endpoint works end-to-end for the logged-in user, including reliable music generation via the Suno upstream client; show every request's status (success/ok badges + pending/running/error states) in the dashboard Logs page; and allow user to download any generated audio result as MP3 or WAV via on-demand transcode (or re-download from upstream Suno) when the format is available. Wire up all `/v1/...` API-key endpoints that exist on the backend to have equivalent `/me/...` logged-in equivalents, so the playground pages can use them.
- **Purpose**: User was stuck in `captcha solve timed out after 120s` during music generation testing; they also want "every API endpoint request should be working" (both `/v1/*` and `/me/*` routes), success status showing "ok" with green badge in Logs, and MP3/WAV download conversion on every result that contains audio.
- **Target Users**: Logged-in Camxora Music API users browsing via `web-user/dashboard/*` and API-key callers.

## Goals
- Music Generation and every Playground sub-page endpoint (Recovery Audio, Separate Vocals, Generate Voice, Check Voice, Replace Section) completes successfully using available upstream accounts.
- Logs page at `/dashboard/logs` shows every request with timestamp, endpoint, model, prompt, status chip (emerald for success/ok, red for error, grey for pending/running), credits consumed, task_id, AND includes a row action to open the task result and download MP3/WAV of each clip.
- Any clip/audio result (whether in playground result panel, in task view, or in Logs) exposes one-click MP3 download and one-click WAV download using the backend's `downloadUrl(clipId, format)` route exposed as a `/me/download` endpoint.
- All `/v1/*` API-key routes that exist and have a SunoClient operation (`wav`, `upload_init`, `upload_register`, `upload_extend`, `upload_cover`, `download_url`, `midi_generate`, `mp4_generate`, `lyrics_detail`, `voice_apply`, `voice_extend`, `boost_style`, `remaster`, `remix`, `add_vocals`, `add_instrumental`, `cover_music`, `cover_image`, `mashup`, `timestamped_lyrics`, `denoise`, etc.) receive a matching authenticated `/me/*` route that picks the user's key and charges credits, so they can all be exercised from the logged-in dashboard context or API-key context.
- Job status progresses from pending → running → complete/error and persists via `usage_logs` DB rows, so status "ok" / success badges remain correct across page reloads.

## Non-Goals
- Upstream Suno account provisioning / captcha-solver integration is NOT in scope — if the upstream has no working accounts, we cannot force successful audio; what we guarantee is that every pipeline correctly routes to a healthy upstream account, falls back to a different pool account when one fails captcha, records the error honestly, and a retry button is available so user can try again.
- Local audio transcoding with ffmpeg/lame is NOT required. We will use `client.downloadUrl(clipId, "mp3" | "wav")` which asks upstream Suno for the requested format, and then proxy/redirect to the final URL.
- SunoAPI UI parity pages we already completed are not re-done from scratch — this spec only adds missing pieces (retry, downloads, logs actions, missing /me/* mirror routes, running/pending status in Logs via live-poll).

## Background & Context
- Previous session produced 5 brand-new placeholder→real pages (Recovery, Separate, GenVoice, CheckVoice, ReplaceSection) + 8 `/me/*` routes in backend + shared `useJob`/`PageShell`/`OutputTabs` in `components/playground.tsx`. Music Generation (`/dashboard/playground`) was already built.
- Real E2E test run at 2026-09-08 logged in as `user@example.com` → submitted Midnight Whisper prompt → job_id `301665b8-...` created, 72 polls of `/me/task/:id` succeeded but upstream finished with `error: "captcha solve timed out after 120s"`. This error came from `SunoClient.generateMusic` path.
- Existing Logs page (`/dashboard/logs`) reads from `GET /me/logs` → SQL `usage_logs WHERE user_id=$1 ORDER BY created_at DESC LIMIT 100`. It only shows final `status` column (complete/error/...). It does not yet show running/pending jobs (which live only in memory) and does not have "success ok" semantics.
- Backend already has `client.downloadUrl(clipId, format)` (used by `/v1/.../download_url`) — there is NO `/me/download` endpoint yet.
- Backend has about 15-20 `/v1/*` endpoints (upload_init, upload_register, upload_extend, upload_cover, midi, mp4, denoise, wav, boost, remaster, remix, addVocals, addInstrumental, timestamped_lyrics, lyrics_detail, cover_image, cover_music, mashup, voice_apply, voice_extend, persona upload flow) that DON'T have `/me/*` equivalents (we only added 8 + a few existing ones like generate). User asked "every api endpoint request should be working" so both should be equally wired.

## Functional Requirements

- **FR-1: Upstream routing, fallback, and retry**: If the selected SunoClient account fails for music/sounds generate (captcha timeout, account rate limited, 5xx, etc.), the worker should try the next healthy account from the pool before finalizing job as error (auto-retry N times with different clients). The playground result card and useJob hook must expose a Retry button that resubmits identical payload for a new job.
- **FR-2: All v1 endpoints have /me mirror**: Every `/v1/<endpoint>` route that is NOT /auth or /admin routes has a corresponding `/me/<endpoint>` route that calls `requireAuth`, `pickUserKey`, `charge`, then `newJob(type)` + run{Clip,Result}Job.
- **FR-3: Download MP3 and WAV for any clip**: Backend exposes `GET /me/download?clip_id=X&format=mp3|wav` returning the download URL or 302 redirect. The Playground result cards and Logs expanded-row result section show `<button MP3>` and `<button WAV>` per clip that open a download link.
- **FR-4: Logs page shows all statuses including pending/running**: Logs page fetches historical rows from `/me/logs` AND running in-memory jobs for the user via new endpoint `/me/jobs/running`, merges them newest-first, and shows an emerald "ok" chip for `status === "complete"`, "error" red for `status === "error"`, "running" blue-ish animated chip for `status === "running"`, "pending" grey for `status === "pending"`.
- **FR-5: Logs row expand → result + downloads**: Each Logs row is clickable/expandable to show stored `result_json` parsed, list all clips, render `<audio>` player, and offer MP3 / WAV download buttons per clip using FR-3 endpoint.
- **FR-6: Playground result cards render audio players + download buttons**: Music Generation, Recovery Audio, Separate Vocals, Replace Section — every page using the new `OutputTabs` with kind="clips" must display an `<audio controls>` element for each clip with audio_url and two small buttons for "MP3 download" and "WAV download" (same pattern as FR-3).
- **FR-7: "Success/ok" semantics visible everywhere**: For each completed job in Logs, the `status === "complete"` row shows a `Success` chip with a green check icon / emerald pill, and the text word `ok` or similar visible cue, so users can immediately see the request worked.

## Non-Functional Requirements
- **NFR-1**: No TypeScript diagnostics errors in web-user or backend after the change. `npx tsc --noEmit` (or GetDiagnostics) → clean.
- **NFR-2**: Every new page route must be server-components-wrapped in existing dashboard layout; everything that uses hooks is `"use client"`.
- **NFR-3**: All `/me/*` routes must honor `requireAuth()` and use `pickUserKey` + `charge()` so credits decrement, matching `/v1/*` semantics — no free operations.
- **NFR-4**: Download endpoint must never leak a different user's clip. Check clip ownership via usage_logs → userId ownership lookup OR just proxy through Suno since clip IDs are opaque; at minimum authenticate the request via `requireAuth`.
- **NFR-5**: Poll for job status in Logs page (every 5s) when any in-memory job is still running; stop polling once all are finished.

## Constraints
- **Technical**: Existing Node.js Fastify backend + PostgreSQL (`usage_logs` SQL table exists, write-only). Web-user is Next.js 15+ App Router. Tailwind is already configured with brand emerald `--emerald` CSS var and violet/purple/fuchsia gradient brand.
- **Business**: Credits are charged once per job attempt. Retries = new job + new charge (consistent with sunoapi.org pricing policy).
- **Dependencies**: `src/client.ts` provides all SunoClient operations (`generateMusic`, `generateSounds`, `pollClips`, `downloadUrl`, `stems`, `replaceSection`, `generateRecoveryAudio`, `createPersona`, `voiceGenerate`, `voiceValidate`, `voicePhrase`, `voiceRecord`, `uploadInit`, `uploadRegister`, `extendMusic`, `uploadExtend`, `uploadCover`, `deNoise`, `audio2Midi`, `audio2MP4`, `boost`, `remaster`, `remix`, `addVocals`, `addInstrumental`, `coverMusic`, `generateCoverImage`, `mashup`, `timestampedLyrics`, `lyricsDetail`, `voiceApply`, `voiceExtend`, plus many more). Use ONLY what client.ts already provides — no direct calls to suno.com.
- **UI consistency**: Use `components/playground.tsx` primitives (PageShell, OutputTabs, PrimaryButton, Switch, ChoiceCard, Field, inputCls, textareaCls, useJob) and add new primitives there (RetryButton, DownloadButton, LogRowExpand) as needed to keep visual uniformity with sunoapi.org.

## Assumptions
- Pool accounts.json has at least one Suno account that can successfully solve captcha; if ALL accounts fail captcha, we still show correct error + Retry button per FR-1, and Logs shows error chip correctly.
- Upstream `downloadUrl(clipId, "mp3")` and `downloadUrl(clipId, "wav")` both produce a valid public URL (Sunocdn or similar) — we don't need ffmpeg for format conversion.
- The browser `web-user` next.config.ts rewrites `/backend/*` → backend `/:splat*`, or if not, all new `/me/*` endpoints will be called via `/backend/me/...` prefix automatically by `apiFetch`.

## Acceptance Criteria

### AC-1: Music generation retries across pool accounts until success (or all exhausted)
- **Type**: `rule`
- **Given**: pool contains N accounts where 1 fails captcha timeout and at least 1 succeeds
- **When**: user submits music generation job
- **Then**: backend retries the failed generate with a DIFFERENT client (next one in pool) up to (N-1) times before marking error; if any account succeeds the final status is "complete"
- **Pass Condition**: FinalizeJob produces `status=complete` after at least one captcha-timeout retry attempt, visible in `usage_logs.status='complete'` (or in-memory job.result = clips)
- **Evidence**: RunCommand smoke test with accounts stub (or real accounts) showing retry count > 0 and status complete

### AC-2: Playground exposes retry button for failed jobs + job_id shown
- **Type**: `rule`
- **Given**: a page using useJob hook ended with status=error
- **When**: user clicks Retry
- **Then**: the same inputs are re-submitted as a NEW `/me/<endpoint>` POST, new polling begins
- **Pass Condition**: In browser DevTools, Retry click → new POST request, new job_id in URL of /me/task/:id (different job_id than failed)
- **Evidence**: Browser network + page screenshot before/after retry click

### AC-3: Every existing /v1/* API-key endpoint has a matching /me/* route
- **Type**: `rule`
- **Given**: any route registered with `fastify.(post|get)("/v1/<name>")` (excluding /v1/auth endpoints)
- **When**: grep for `/v1/...` registrations in server.ts and compare to `/me/...` list
- **Then**: for each `/v1/<name>` there is a corresponding `/me/<name>` with identical body validation, using requireAuth + pickUserKey + charge, same job type, same runClipJob/runResultJob submitter
- **Pass Condition**: `grep -E '\("/v1/' server.ts` yields M routes; `grep -E '\("/me/'` yields (auth + M routes); 1-to-1 mapping count equality + manual spot-checks of midi, mp4, denoise, upload_init, mashup, cover_music, etc
- **Evidence**: Terminal grep counts before vs after, matching entries side-by-side

### AC-4: /me/download endpoint works for clip_id + format=mp3|wav
- **Type**: `rule`
- **Given**: a logged-in user and a valid upstream-owned clip_id that has audio
- **When**: `GET /backend/me/download?clip_id=<X>&format=mp3` and `...&format=wav`
- **Then**: each returns HTTP 302 redirect or a JSON `{ url: string }` where url is a valid playable audio file URL for that format
- **Pass Condition**: Status 302 / 200 JSON with url, and audio file loads in `<audio>` element for both mp3 and wav formats of same clip
- **Evidence**: RunCommand curl with auth token against test clip_id

### AC-5: Logs page displays pending/running/complete(error) statuses with correct chips
- **Type**: `rule`
- **Given**: one pending job, one running job, one complete job, one error job for user
- **When**: open `/dashboard/logs`
- **Then**: 4 rows merged (DB + live /me/jobs/running) show 4 distinct status chips — pending grey, running blue pulsing, complete emerald green with "ok" check icon text, error red
- **Pass Condition**: Visual screenshot of all 4 statuses visible in one page; emerald badge explicitly contains "ok" word or adjacent checkmark badge text says "Success — ok"
- **Evidence**: Browser screenshot + browser_snapshot confirming chip text colors

### AC-6: Logs row expands to task result + audio player + MP3/WAV download buttons
- **Type**: `rule`
- **Given**: a Logs row with complete status whose result_json contains at least 1 clip with audio_url
- **When**: click expand/collapse on row
- **Then**: panel below row shows parsed JSON list, `<audio controls>` for the clip, and two buttons: "Download MP3" and "Download WAV" that hit /me/download?clip_id=<X>&format=... with `Content-Disposition: attachment` behavior (download trigger, not navigate)
- **Pass Condition**: Browser screenshot of expanded row showing audio player + both buttons; clicking both buttons triggers network requests to /me/download
- **Evidence**: Network requests log showing both /me/download mp3 and wav GET requests initiated

### AC-7: Playground Music Generation + Recovery + Separate + Replace result panels include MP3/WAV download
- **Type**: `rule`
- **Given**: a result job with clips in playground pages
- **When**: result cards render
- **Then**: every clip card (inside OutputTabs overview) includes `<audio controls>` + MP3 button + WAV button
- **Pass Condition**: Visual inspection of OutputTabs clips in browser — each card has the 3 elements
- **Evidence**: Screenshot of any playground clips result with audio + download buttons visible

### AC-8: All endpoints respond (non-500) in smoke test
- **Type**: `rubric`
- **Dimension**: Endpoint breadth & working order
- **Scale**: 1-5
- **Anchors**: 1 = >5 endpoints return 5xx on valid input; 3 = all respond 202/200 but some /me mirror routes missing; 5 = ALL /v1 and matching /me routes return sensible statuses, no crashes, credits charged correctly
- **Pass Threshold**: >= 4
- **Evidence**: RunCommand smoke script or curl list for every /me/* route with demo auth token — at most 1 endpoint returns 5xx for malformed input, and all /me mirrors of /v1/* exist

### AC-9: Logs still shows "ok / Success" green badge even after page refresh
- **Type**: `rule`
- **Given**: a job marked complete in DB `usage_logs.status='complete'`
- **When**: refresh `/dashboard/logs` page
- **Then**: the row shows emerald "Success" chip with "ok" label
- **Pass Condition**: After hard refresh (Ctrl+F5), the Logs row still renders green "Success ok" chip for same DB row
- **Evidence**: two screenshots — before and after refresh — same row with same green badge

## Open Questions
- [ ] NONE currently — scope boundaries clear. If user wants ffmpeg local transcode as a fallback when upstream `downloadUrl(clipId, mp3)` fails, that's a future enhancement (currently out of scope per Non-Goals).
