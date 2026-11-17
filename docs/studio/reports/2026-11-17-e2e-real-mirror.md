# W4 — full browser suite against the live mirror (D2 evidence)

**Date:** 2026-11-17
**Agent:** W4 (`qa/e2e-real-mirror`)
**Base:** `origin/main` @ `bcd612c7` ("docs(studio): plan the residual verification pass…")
**Worktree:** `C:\Users\Kong Somvannda\AppData\Local\Temp\camxora-res-e2e`
**Plan reference:** `docs/studio/RESIDUAL_VERIFICATION_PLAN.md` §1 D2, §4 W4

**D2: PASS**

185 passed / 2 skipped / 0 failed, 6 m 36 s wall, **zero 5xx** and zero ERROR-level
records in the platform API log for the whole run, readiness green on every check that can
be green without a public tunnel.

---

## 1. What was actually running

Everything below ran in **one shell lifetime** (the host reaps long-lived children, so the
stack was started and the suite was run by a single `powershell -File` invocation):

| Component | Port | How it was started | Evidence it was live |
|---|---|---|---|
| moto (S3 stand-in) | 9000 | `python -m moto.server -p 9000` | `bucket created` for `camxora-studio`; signed URLs to `127.0.0.1:9000` appear in the API log |
| platform API | 8100 | `python -m uvicorn platform_api.main:app --host 127.0.0.1 --port 8100 --log-level warning`, env: sandbox DB + Studio token + 5 × `PLATFORM_STREAMING_B2_*` (moto) + `PLATFORM_SUNO_API_BASE_URL=http://127.0.0.1:4003` + `PLATFORM_CREDITS_ONLY_V3_CHARGE=true` | `/health` 200 at 08:20:03; 6,794 log lines during the run |
| musicapi (the real mirror) | 4003 | `npm run serve` (`tsx src/serve.ts`) with the worktree's `musicapi/.env` (`STUDIO_INTERNAL_TOKEN`, `sunoapi` DB) | 760 requests, **747 of them `/internal/studio/*`**, 0 responses ≥ 500 |
| platform worker | — | `python scripts/dev/run-platform-worker.py` with `PLATFORM_ENV_FILE` → the worktree `platform_api/.env` | "Worker … draining job_queue (types=[… web_music_generate])", still alive at suite start |
| web dev server | 3103 | `npm run dev` in `camxora.com` (`PLATFORM_API_URL=http://127.0.0.1:8100`) | `/studio` 200; warmed `/studio`, `/studio/editor`, `/library`, `/create`, `/legal` before the suite |

Databases: `camxora_pfm_sandbox` (platform) and `sunoapi` (musicapi), both on the local
PostgreSQL :5432; Redis :6379 up. Node 24.13.0, Python 3.11.9.
The sandbox user `somvannda@gmail.com` exists with a 4,480,000-credit wallet and an active
`suno` provider key whose `base_url` is `http://127.0.0.1:4003` (decrypts with the current
`PLATFORM_ENCRYPTION_MASTER_KEY`), which is what makes this a *real* mirror rather than a
half-configured stack.

### 1.1 Readiness, as returned

`GET /api/v3/web-music/studio/readiness` — logged in through the web rewrite
(`POST /api/v3/auth/login` 200, cookies on the session), 2026-11-17T01:20:12Z:

```json
{"ready":false,
 "checks":{"tables":true,"pricing":true,"storage":true,"internal_token":true,
           "suno_api_base_url":true,"suno_callback_base_url":false,
           "musicapi":true,"musicapi_accounts":true},
 "missing_tables":[],"missing_pricing":[],"storage_error":null,
 "musicapi_accounts":1,"musicapi_pool_size":1,"musicapi_error":null,
 "checked_at":"2026-11-17T01:20:12.507432+00:00"}
```

| Check | Result | Notes |
|---|---|---|
| `tables` | ✓ | 7/7 Studio tables present in `camxora_pfm_sandbox` |
| `pricing` | ✓ | `studio_edit` 120 000, `studio_stems_2` 120 000, `studio_stems_12` 600 000 (from `credit_pricing`) |
| `storage` | ✓ | env-sourced, **probed with a real authenticated S3 call** against moto — not just "keys are set" |
| `internal_token` | ✓ | from `musicapi/.env` |
| `suno_api_base_url` | ✓ | `http://127.0.0.1:4003` |
| `suno_callback_base_url` | ✗ | **expected** — no public tunnel in a local run; Suno refuses local callbacks, so it correctly reports false instead of lying |
| `musicapi` | ✓ | `/internal/studio/health` answered with the internal token |
| `musicapi_accounts` | ✓ | `active_accounts = 1` (the live-auth count, not the pool size) |

`ready:false` is therefore **only** the missing public callback base — exactly the
"all ✓ except the callback" shape the plan defines for D2. Every other dependency that a
provider-backed path needs was live and authenticated.

---

## 2. The suite

```
cd camxora.com
npx playwright test --workers=2
```

| | Count |
|---|---|
| Tests collected | **187** |
| **Passed** | **185** |
| **Failed** | **0** |
| **Skipped** | **2** |
| Flaky / retried | 0 (retries are 0 locally; none were needed) |
| Playwright duration | **6.6 m** (reporter) — 395.8 s wall (measured around the `npx` call) |
| Exit code | 0 |

Run window: 08:20:14 → 08:26:50 local (01:20:14 → 01:26:50 UTC). 64 spec files.

### 2.1 The two skips (both deliberate env opt-ins, not failures)

| Spec | Reason string | Why it skipped |
|---|---|---|
| `studio-bounce.spec.ts:132` "bounce stores the render in the bucket…" | `set STUDIO_UPLOAD_PROXY_URL to a storage-backed API` | The test proxies the browser upload to a storage-backed API only when `STUDIO_UPLOAD_PROXY_URL` is exported; the suite run did not export it |
| `studio-record.spec.ts:11` "arming a track and recording a take…" | `recording uploads need streaming storage (B-006)` | Gated on `STUDIO_EXPECT_UPLOADS=1`; not exported |

Note these are *opt-ins*, not capability gaps: with this stack both paths are now
serviceable (storage probes green, moto bucket exists). See §5.2 — running them is a
one-flag follow-up, and would change the plan's 185/2 baseline.

---

## 3. API log — 5xx evidence

The API's stderr is `%TEMP%\platform-8100.err.log`. It is truncated at stack start, so the
"before" measurement is taken once the stack is healthy and immediately before the suite:

| | Before run (08:20:14) | After run (08:26:53) | Delta |
|---|---|---|---|
| Lines | 48 | 6,794 | +6,746 |
| Bytes | **3,767** | **743,842** | +740,075 |

Grep of the delta:

| Pattern | Lines |
|---|---|
| ` API 5xx response` (route returned ≥500) | **0** |
| `API 5xx (unhandled exception)` | **0** |
| `Traceback` | **0** |
| Records at level `ERROR` | **0** |
| `[access]` lines with a 5xx status | **0** |
| `WARNI` records | 839 |

**No 5xx extract exists because there was no 5xx.** The 839 warnings are request-audit
noise, not failures:

- 637 × `SECURITY_AUDIT … 401` on `GET /api/v3/users/me` (424) and
  `POST /api/v3/auth/refresh` (213) — the unauthenticated page shell probing `/users/me`
  before each spec signs in. Expected on every navigation; the specs then log in (200).
- 1 × `CLOUDFLARE_TURNSTILE_SECRET_KEY not set` — expected, `NEXT_PUBLIC_TURNSTILE_DISABLED=1`
  is the local sandbox contract.
- 14 × duplicated pairs of seeded-media storage warnings (7 access attempts) for
  `task=dec67289-…`: `NoSuchKey` from moto, then `Web music MP3 download CDN retry 1..5/5`
  → `404` from `http://127.0.0.1:9000/camxora-studio/musicapi/clips/f3f87ffd-….mp3`.
  This is a **pre-existing sandbox row** whose media predates the empty moto bucket; the
  API degrades with a warning + `422`/`404` and never a 5xx. It is also incidental proof
  that storage really is moto: the URL is signed and points at `127.0.0.1:9000`.

4xx breakdown for the run (680 responses — all client-side, none counted against D2):

| Status | Route | Count | Reading |
|---|---|---|---|
| 401 | `/api/v3/users/me` | 424 | pre-login shell probe |
| 401 | `/api/v3/auth/refresh` | 213 | no refresh cookie yet |
| 422 | `/api/v3/web-music/generations/<id>/stream/ok` | 25 | the seeded tasks above, media absent from the fresh bucket |
| 404 | `/api/v3/web-music/generations/<id>/download` (+1 project GET after delete) | 3 | same seeded task / soft-delete flow |
| 400 | `PATCH /api/v3/web-music/studio/projects/<id>` | 7 | rejected writes (see §5.4) |
| 400 | `POST …/projects/<id>/presence` | 2 | negative-path assertions in the specs |
| 422 | `…/projects/{existing-project,project-from-song}/refresh` and `/presence` | 4 | deliberate synthetic-id negative paths |
| 409 | `…/studio/projects/<id>` (conflict specs) | 2 | the conflict/generation-guard assertions |

### 3.1 musicapi side

`musicapi` was genuinely on the request path, not decorative:

| Endpoint family | Requests |
|---|---|
| `POST /internal/studio/projects/<id>/refresh` | 368 |
| `POST /internal/studio/projects/<id>/enqueue` | 317 |
| `GET /internal/studio/projects/status` | 59 |
| `POST /internal/studio/projects/<id>/archive` | 2 |
| `GET /internal/studio/health` (readiness) | 1 |
| **Total** | **747 of 760 requests** |

0 responses with status ≥ 500, 0 records at level 50/60 in the musicapi log. That is the
project-mirror half of the Studio contract exercised end to end through the platform API
with the internal token; no paid clip operation (`generate`, `stems`, `persona`, …) was
invoked — the specs stub the operation routes, and spending credits is D4/W6, not D2.

---

## 4. Failure classification

**No failures, so no retry pass was needed and nothing required classification as
product / timing / environment.** For completeness: 187 collected, 185 passed, 2 skipped,
0 failed, 0 flaky, on the first attempt. The shared sandbox did mutate under the run (it
created the projects the specs ask for) and still produced no transient failure.

---

## 5. Residual observations (for the W0 consolidation)

These are **not** D2 failures; they are things the next workstreams should know.

1. **`suno_callback_base_url` is the only red check**, by design of a local run. Any
   *generation* path (as opposed to clip editing / mirror sync) still needs a public
   callback (`cloudflared tunnel --url http://127.0.0.1:8100`) before it can succeed. D2 as
   specified does not require it; W6 does.
2. **Two suite paths are still unexercised by the standard command** (§2.1). Now that
   storage probes green, a follow-up
   `STUDIO_UPLOAD_PROXY_URL=http://127.0.0.1:8100 STUDIO_EXPECT_UPLOADS=1 npx playwright test --workers=2`
   would cover the bounce-into-bucket and microphone-take uploads and should be recorded
   as an extension of D2 (it will report 187 passed / 0 skipped).
3. **Empty moto bucket vs seeded sandbox media.** Tasks seeded by earlier sessions point at
   objects a fresh bucket does not contain; the media endpoints answer `422`/`404` and log
   warnings while the suite still passes. Anything that judges *playback of old tasks* on
   this stack must seed the bucket first, or the result will look like a UI defect.
4. **7 × `PATCH /studio/projects/<id>` → 400** with 5–30 ms responses and **no ERROR
   record**. Cause not proven from the log (the API logs status, not body); the shape
   (immediately after a successful `GET …/pricing` and `…/presence`) is consistent with the
   write-queue / offline / conflict specs cancelling an in-flight save or sending a
   validated-empty body. Classified **environment/expected 4xx**, not product — but worth a
   one-line `warnings` filter in the API log if these ever need to be attributed.
5. **The run mutated the shared sandbox**: the platform DB `camxora_pfm_sandbox` now holds
   the projects created by these specs (each spec builds its own project by design). It did
   **not** spend credits — `PLATFORM_CREDITS_ONLY_V3_CHARGE=true` and no fill was requested.
6. **`/studio/learn` is not a route** (404 during warm-up); the Learn surface is a header
   menu, not a page. No action.

---

## 6. Reproduce

```powershell
git worktree add "$env:TEMP\camxora-res-e2e" -b qa/e2e-real-mirror origin/main
# copy the three gitignored env files (platform_api/.env, musicapi/.env, camxora.com/.env.local)
# then, in one shell lifetime:
#   moto :9000 + bucket camxora-studio
#   PLATFORM_DATABASE_URL=…camxora_pfm_sandbox
#   PLATFORM_STUDIO_INTERNAL_TOKEN=<musicapi/.env STUDIO_INTERNAL_TOKEN>
#   PLATFORM_SUNO_API_BASE_URL=http://127.0.0.1:4003
#   PLATFORM_STREAMING_B2_{KEY_ID,APPLICATION_KEY,BUCKET,REGION,ENDPOINT}=minioadmin/camxora-studio/us-east-1/http://127.0.0.1:9000
#   uvicorn platform_api.main:app :8100;  musicapi `npm run serve`;  run-platform-worker.py;  camxora.com `npm run dev`
#   log in as somvannda@gmail.com and GET /api/v3/web-music/studio/readiness
cd camxora.com; npx playwright test --workers=2
```

Note: `uvicorn --env-file` truncates at the space in `C:\Users\Kong Somvannda\…`, so the
env file must be exported into the process instead of passed as a flag.

---

## 7. Verdict

**D2: PASS** — 185 passed / 2 skipped / 0 failed in 6 m 36 s with the real mirror
(musicapi + worker + moto + platform API + Studio token) live: readiness green on 7 of 8
checks with the callback check correctly false for a local run, **0** `API 5xx response`
lines, **0** tracebacks, **0** ERROR-level records during the run.
