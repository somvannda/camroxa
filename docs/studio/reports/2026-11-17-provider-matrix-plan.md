# W6-prep — paid provider matrix: call chains, cost keys, budget and gate

**Date:** 2026-11-17
**Workstream:** W6-prep (plan: `docs/studio/RESIDUAL_VERIFICATION_PLAN.md` §2 W6, §4)
**Agent:** W6-prep, branch `qa/provider-prep`, worktree
`C:\Users\Kong Somvannda\AppData\Local\Temp\camxora-res-provider`
**Base:** `origin/main` @ `4abff799` (`test(pixels): add the diff harness and revise D3 around allowed divergences`)

**Method:** read-only source analysis. **No server was started, no port was bound, no provider
call was made, no credit was spent, no deploy, no push.** `G:\Developments\Projects\Camxora`
was not touched. The matrix script was written and exercised **offline only**
(`node --check`, `--help`, `--self-test`, and the two guard-failure paths); `--execute` was
never run.

**Deliverables:** this report + `scripts/dev/provider-matrix.mjs`.

---

## 1. What this document decides

D4 needs one recorded id + terminal status per provider operation. Before any credit can be
spent, four things have to be pinned down and agreed:

1. **The exact call chain** — which endpoint, which body, which poller, which ids (§3, §4).
2. **The cost key per operation** — read from the pricing table at run time, never hard-coded
   (§5).
3. **A budget** — a cap the runner cannot exceed, with the arithmetic behind it (§6).
4. **The preconditions** — tunnel, worker, charge flag, key presence, and how to prove them
   in one command (§7).

Nothing here authorises spending. `--execute` stays unused until the cap in §6 is approved.

---

## 2. Surfaces involved

| Layer | Base | What it owns |
|---|---|---|
| Platform API | `PLATFORM_API_BASE_URL` (dev `http://127.0.0.1:8100`) + `/api/v3` | Camxora user, credits, Studio operations, exports |
| Core API (`musicapi`) | `PLATFORM_SUNO_API_BASE_URL` (dev `http://127.0.0.1:4003`) | Suno account pool, jobs, `/internal/studio/*` |
| Provider (Suno) | reached **only** from `musicapi` | clips, personas, stems, WAV conversion |

Every route in `platform_api/routers/web_music.py` sits under `/web-music` and is mounted on
both `/api/v1` and `/api/v3` (`platform_api/main.py:880`, `_mount(…, v1, v3)`). **This plan
uses `/api/v3`** (`platform_api/http_paths.py: API_V3_PREFIX`), the canonical surface.

Auth: `POST /api/v3/auth/login` (`platform_api/routers/auth.py:536`) returns a bearer token
**and** sets `camxora_access_token` (`auth.py:61`). `get_current_user`
(`middleware/auth.py:248`) accepts either, so the runner uses the bearer token and ignores
cookies.

Two different pricing tables exist — the names are easy to confuse:

| Table | Database | Used for | Read via |
|---|---|---|---|
| `credit_pricing` | `platform_db` | **Camxora credits** (the user-facing budget) | `GET /web-music/studio/pricing`, `GET /web-music/quota` |
| `pricing` | `sunoapi` | `musicapi` **API-key credits** (a second, much smaller ledger) | direct SQL only |

`AGENTS.md` calls the first one “the `pricing` table”; the physical name is `credit_pricing`
(micro-units, `CREDIT_SCALE = 10_000`, `platform_api/services/credit_units.py:16`). The plan
below keeps them apart on purpose: §6 charges the Camxora budget, and calls out the
`musicapi` ledger separately.

---

## 3. Call chain per operation

Common prefix: `P = {PLATFORM_API_BASE_URL}/api/v3/web-music`, `H = {x-internal-token: PLATFORM_STUDIO_INTERNAL_TOKEN}`.

Every studio edit follows the same four hops:

```
browser/script
  └─ POST P/studio/…            (202, returns a studio_operations row)
       ├─ platform_api: _request_studio_clip_operation
       │    ├─ resolve provider clip id  (suno_tasks.audio_id_ok|alt, must be status=success)
       │    ├─ INSERT studio_operations (status='queued')
       │    ├─ charge bridge → credit_pricing op (studio_edit | studio_stems_2 | studio_stems_12)
       │    └─ POST {suno_api_base}/internal/studio/…  + H   {clip_id, …}
       │         └─ musicapi: newJob(...) → Suno client call → job.credits = 0
       └─ poll GET P/studio/operations/{id}
            └─ platform_api: GET {suno_api_base}/internal/studio/jobs/{job_id} + H
                 → UPDATE studio_operations (status, result_json)
                 → refund the charge when status ∈ {error, failed}
```

Source: `platform_api/services/web_music_service.py:5705` (`_request_studio_clip_operation`),
`:5639` (`_studio_charge_op`), `:6814-6856` (poll + refund), `musicapi/src/server.ts:9150+`
(`/internal/studio/*`, `job.credits = 0`).

### 3.1 Matrix rows

| # | Operation | Endpoint | Body (required **bold**) | Provider route | Poll / status | Ids to record |
|---|---|---|---|---|---|---|
| 1 | **generate** | `POST P/generate` (202) | **`mode`** `simple\|advanced`, **`style`**, **`title`**, **`lyrics`**, **`instrumental`**, **`model`** ∈ `V6\|V6_MINI\|V6_WILD`, **`prompt`**; optional `negative_tags`, `vocal_gender`, `style_weight`, `weirdness_constraint`, `audio_weight`, `persona_id`, `workspace_id`, `sample_task_id`/`sample_variant` | `musicapi` `POST /v1/music/generate` (Bearer platform key) → Suno; callback `{PLATFORM_SUNO_CALLBACK_BASE_URL}/api/v1/callbacks/suno` | `GET P/generations/{task_id}` → `status` ∈ `PENDING/RUNNING/SUCCESS/FAILED/CANCELLED`; `clips[ok\|alt].ready` | `task_id`; SQL `suno_tasks.external_task_id`, `audio_id_ok`, `audio_id_alt` |
| 2 | **stems (2)** | `POST P/studio/generations/{task_id}/stems` (202) | **`mode`** `vocal` (→ 2-track), `variant` default `ok`, optional `project_id` | `POST /internal/studio/stems` `{clip_id, mode}` | `GET P/studio/operations/{id}` → `complete\|error` | `operation.id`, `musicapi_job_id`, `provider_clip_id` (source), `result.clips[].id`, `credits_charged`, `charge_op` |
| 3 | **stems (12)** | same as #2 | **`mode`** `advanced` (or `stems`) | same | same | same |
| 4 | **voice persona** | `POST P/studio/voice/personas` (201) | **`name`**, `styles`, **`voice_id`** | none — plain `studio_personas` INSERT (`web_music_service.py:4767`) | synchronous (201); list `GET P/studio/personas` | `id`, `provider_persona_id` (= `voice_id`), `status` |
| 4b | persona *from a clip* (0 credits, same billing bucket) | `POST P/studio/generations/{task_id}/personas` (202) | **`name`**, `styles`, `description`, `vocal_start_s`, `vocal_end_s`, `variant` | `POST /internal/studio/persona` `{clip_id, name, styles, description, vocal_start_s, vocal_end_s}` | `GET P/studio/personas` (each read refreshes queued rows, `:5076`) | `studio_personas.id`, `provider_persona_id`, `musicapi_job_id` |
| 5 | **cover** | `POST P/studio/generations/{task_id}/cover` (202) | **`prompt`**, `variant`, `project_id` | `POST /internal/studio/cover` `{clip_id, prompt}` | `GET P/studio/operations/{id}` | as #2 |
| 6 | **extend** | `POST P/studio/generations/{task_id}/extend` (202) | `variant`, `continue_at` (secs), `project_id` | `POST /internal/studio/extend` `{clip_id, continue_at}` | same | as #2 |
| 7 | **remaster** | `POST P/studio/generations/{task_id}/remaster` (202) | `variant`, `model`, `project_id` | `POST /internal/studio/remaster` `{clip_id, model}` | same | as #2 |
| 8 | **vocals** | `POST P/studio/generations/{task_id}/add-vocals` (202) | **`prompt`** (non-empty), `variant`, `project_id` | `POST /internal/studio/add-vocals` `{clip_id, prompt}` | same | as #2 |
| 9 | **instrumental** | `POST P/studio/generations/{task_id}/add-instrumental` (202) | **`prompt`** (non-empty), `variant`, `project_id` | `POST /internal/studio/add-instrumental` `{clip_id, prompt}` | same | as #2 |
| 10 | **mashup** | `POST P/studio/mashup` (202) | **`task_ids`** 2–4 UUIDs, **`variants`** 2–4 (`ok\|alt`, same length), `prompt`, `project_id` | `POST /internal/studio/mashup` `{clip_ids[], prompt}` | same | `operation.id` + the 2–4 source `task_id`s and their provider clip ids |
| 11 | **replace** | `POST P/studio/generations/{task_id}/replace-section` (202) | **`start_s`**, **`end_s`** (`end_s > start_s`), **`lyrics`**, `variant`, `prompt`, `model`, `persona_id`, `project_id` | `POST /internal/studio/replace-section` `{clip_id, start_s, end_s, lyrics, prompt, model, persona_id}` | same | as #2 |
| 12 | **bounce / upload** | `POST P/studio/uploads` (201, multipart `file` = `audio/*`, `duration_seconds`) → then `POST P/studio/uploads/{upload_id}/extend` (202) | upload: **`file`**; extend: `prompt`, `continue_at`, `title`, `tags`, `project_id` | upload: storage only (no provider). extend: `POST /internal/studio/upload-extend` `{audio_url, prompt, continue_at, title, tags}` | upload synchronous; extend via `GET P/studio/operations/{id}` | `studio_uploads.id`, `storage_key`; `operation.id`, `musicapi_job_id` |
| 13 | **export WAV** | `GET P/generations/{task_id}/download-wav?variant=ok` (200) | — | `musicapi` `GET /internal/studio/clips/{clip_id}/wav` is the stem-clip path; song WAV goes through the Suno WAV task (`submit_wav_task` + poll, `web_music_service.py:8715-8823`) | synchronous but **blocks up to ~60 s**; may answer 400 “WAV file is not ready yet” → retry | filename, `Content-Type: audio/wav`, byte length, `RIFF` magic |
| 14 | **export MP3** | `GET P/generations/{task_id}/download?variant=ok` (200) | — | deliver from B2 or Suno, watermark owner export (`:8534`) | synchronous | filename, `Content-Type: audio/mpeg`, byte length |

Notes that change the run:

- **#2 vs #3 is `mode`, not a separate route.** `_studio_charge_op` returns
  `studio_stems_12` when `mode ∈ {stems, advanced}` and `studio_stems_2` for `vocal`
  (`:5639`). Sending `mode: "stems"` to mean “2 stems” charges 5× — the runner sends
  `vocal` for the 2-track row and `advanced` for the 12-track row.
- **#10 needs two *successful, distinct* tasks** (`_studio_source_clip` + an explicit
  `status = success` check per extra task, `:5435`). One generation gives one task id, so the
  mashup row owns a **second generate as a fixture** (10 credits). It also requires all
  source clips to belong to the **same Suno account** (`server.ts:9644`), which is true when
  the pool routes both calls to one account.
- **#12 upload is free; the extend is not** (`charge_op = "studio_edit"`, `:6055`). The
  runner uploads the WAV it already downloaded in #13 — that is exactly the client’s
  “bounce → place back” path.
- **#13/#14 are free** (`_require_download_access` is a no-op, `:906`; only the
  `web_music_download` rate limit applies — 30/min, `middleware/rate_limit.py:52`).
- **Provider clip ids for #1 are not in the API response.** `WebMusicClipResponse` carries
  `variant/audio_url/download_url/ready/…` but no clip id (`routers/web_music.py:85`). The
  ids live in `suno_tasks.audio_id_ok|alt` and `external_task_id`; the report prints the
  exact read-only SQL to capture them (§8).
- **Personas (#4) charge nothing.** Both paths either insert a row directly or start a
  provider job without the charge bridge (`:4767`, `:5119`). The *voice* path is the only
  operation that cannot be made fully scriptable: it needs a human recording of the phrase
  returned by `GET P/studio/voice/phrase`, posted to `P/studio/voice/verify` together with
  `phrase_id` and `source_voice_recording_id` (from `POST P/studio/voice/samples`).

---

## 4. Per-operation order, isolation and ids

- **Order: cheapest first**, dependencies respected — free → 12-credit edits → the
  60-credit 12-track split last, so an early failure cannot eat the expensive step.
  The runner’s order is exactly: `generate` (10) → `export_wav` → `export_mp3` → `persona` →
  `bounce_upload` (12) → `stems_2` (12) → `cover` → `extend` → `remaster` → `vocals` →
  `instrumental` → `replace` → `mashup` (22, includes its fixture) → `stems_12` (60).
- **One disposable project per operation** (`POST P/studio/projects` `{title}` → `201`), passed
  as `project_id` (or `workspace_id` for generate) so nothing is attached to another
  user’s or another run’s asset. `project_id` is an optional FK on every studio route.
- **Ids recorded per row:** platform id (task / operation / upload / persona),
  `musicapi_job_id`, `provider_clip_id` (source clip), `provider_persona_id`, result clip
  ids, status, `credits_charged`, `charge_op`, timestamps, and the error message on failure.
- **Never point a run at a seeded asset.** Sources are only ids this run created; the SQL in
  §8 is read-only and filtered by `user_id`.

---

## 5. Cost keys (read at run time, never hard-coded)

The runner reads both prices from authenticated endpoints before it plans anything:

| Source | Endpoint | Keys |
|---|---|---|
| Studio prices | `GET P/studio/pricing` → `{edit, stems_2, stems_12}` (`web_music_service.py:5602`) | `studio_edit`, `studio_stems_2`, `studio_stems_12` |
| Song price | `GET P/quota` → `credits_per_song` (`:875`) | `music` (sub_model = the model) |
| Readiness | `GET P/studio/readiness` | proves the three pricing rows exist (`:5517`) |

Mapping, from `_studio_charge_op` and the charge bridge:

| Operation | `credit_pricing` key (`ai_service='suno'`) | Notes |
|---|---|---|
| generate | `music` (sub_model `V6_MINI` / `V6` / `V6_WILD`) | migration `176_v6_ten_credits.py` |
| stems 2 | `studio_stems_2` | migration `150_studio_operation_charges.py` |
| stems 12 | `studio_stems_12` | 150 seeds, `151_studio_stems_12_price_60.py` sets 60 |
| cover, extend, remaster, vocals, instrumental, mashup, replace, upload-extend, midi | `studio_edit` | one key, one price, `:5639` |
| voice persona, clip persona | *(none)* | no charge path |
| upload (bounce) | *(none)* | storage only |
| export WAV / MP3 | *(none)* | rate limit only |

Units: `credit_pricing.credits_per_operation` is in micro-units (`CREDIT_SCALE = 10_000`).
Reading the rows directly is only a fallback for the report; the runner always uses the
endpoints so an admin edit to `/admin/pricing` is picked up on the next run.

Current seeded values (2026-11-17, `origin/main`):

| Key | micro-units | display credits | Source |
|---|---|---|---|
| `studio_edit` | 120,000 | **12** | `150_studio_operation_charges.py:34` (Suno 10 + 2) |
| `studio_stems_2` | 120,000 | **12** | `150:45` |
| `studio_stems_12` | 600,000 | **60** | `151:22` (was 520,000 → 52) |
| `music` (V6/V6_MINI/V6_WILD) | 100,000 | **10** | `176_v6_ten_credits.py:19,26` |

Second ledger, for completeness: one song generation also spends **10 `musicapi` credits**
on the platform API key (`musicapi.pricing`, `endpoint='music'`, `credit_cost=10` —
`musicapi/src/server.ts:1303`, `0026_pricing_production_sync.sql:10`). Studio edits spend
none (`job.credits = 0`). At the documented $5/1,000 rate that is ≈ $0.10 for the two
generations in this matrix — outside the Camxora budget, inside the `musicapi` key balance.

---

## 6. Estimated cost of one run (+ two retries)

One run = 12 matrix operations **plus** the mashup fixture generation **plus** the two free
exports: **12 paid provider calls** (11 charged operations + the fixture generation) and
**4 free calls** (persona, the upload half of bounce/upload, export WAV, export MP3).

| # | Operation | Calls | Credits each | Subtotal |
|---|---|---|---|---|
| 1 | generate | 1 | 10 | 10 |
| 2 | stems (2) | 1 | 12 | 12 |
| 3 | stems (12) | 1 | 60 | 60 |
| 4 | voice persona | 1 | 0 | 0 |
| 5 | cover | 1 | 12 | 12 |
| 6 | extend | 1 | 12 | 12 |
| 7 | remaster | 1 | 12 | 12 |
| 8 | vocals | 1 | 12 | 12 |
| 9 | instrumental | 1 | 12 | 12 |
| 10 | mashup (+ fixture generate) | 2 | 12 + 10 | 22 |
| 11 | replace | 1 | 12 | 12 |
| 12 | bounce/upload (upload + upload-extend) | 2 | 0 + 12 | 12 |
| 13 | export WAV | 1 | 0 | 0 |
| 14 | export MP3 | 1 | 0 | 0 |
| | **base total** | | | **188** |

Retries are the only variable. Two retries, cheapest-to-worst case:

| Retry assumption | Arithmetic | Total |
|---|---|---|
| one edit (12) + one generate (10) — the realistic failure pair | 188 + 22 | **210** |
| both retries on the priciest operation (stems 12 = 60) | 188 + 120 | **308** |

**Statement of the range: 188 credits (clean run) → 210 credits (one edit + one generate
retried) → 308 credits (two stems-12 retries).** Every price above is read from the
pricing endpoint at run time; these numbers come from migrations `150`, `151` and `176`
(`credit_pricing`, micro-units ÷ 10,000) and match what `/studio/pricing` and `/quota`
return on a correctly seeded database.

**Recommended approved cap: 320 Camxora credits.** It covers the worst case (308) with 12
credits of slack, and the runner refuses to start an operation that would exceed whatever
number is passed to `--budget`. Refunds: a studio operation that reaches `error`/`failed` is
refunded (`web_music_service.py:6857`), so the true spend should land nearer 188 — the cap
exists because a refund can itself fail.

Separately: **the `musicapi` API key needs ≥ 20 credits** for the two generations.

---

## 7. Preconditions and one-command verification

| Precondition | Why it fails the run | Verified by |
|---|---|---|
| **Public callback** `PLATFORM_SUNO_CALLBACK_BASE_URL` (`cloudflared tunnel --url http://127.0.0.1:8100`) | `suno_client.py:924` falls back to `https://localhost/api/v1/callbacks/suno`, which the provider rejects: generations never leave `PENDING` | readiness `checks.suno_callback_base_url`; the script refuses local/private hosts itself (`localhost`, `*.localhost`, RFC1918, loopback, link-local, reserved) |
| **`PLATFORM_SUNO_API_BASE_URL=http://127.0.0.1:4003`** | generations go to `musicapi.camxora.com` instead of the local mirror (real spend on the wrong stack) | readiness `checks.suno_api_base_url` + `checks.musicapi` |
| **`PLATFORM_STUDIO_INTERNAL_TOKEN` present on *both* processes** | every Studio edit answers *“Studio operations are not configured.”* / `401 Invalid internal service token` | readiness `checks.internal_token`; optional direct `GET {MUSICAPI_BASE_URL}/internal/studio/health` |
| **Suno account pool has a live account** | no account → `409 The source clip's Suno account is not recorded.` | readiness `checks.musicapi_accounts` + `musicapi_accounts` > 0 |
| **Storage configured (B2/moto)** | upload (#12) and the WAV/B2 path fail | readiness `checks.storage` (it probes, not just reads config) |
| **Pricing rows exist** | charge bridge raises before the provider call | readiness `checks.pricing`; `/studio/pricing` returns non-zero |
| **`credits_only_v3_charge` = true** (`system_settings`) | the charge falls back to the legacy ledger and the cap no longer describes the spend | `SELECT value FROM system_settings WHERE key='credits_only_v3_charge';` |
| **Platform key in `musicapi.api_keys` with ≥ 20 credits** | generation answers `402 Insufficient credits` | SQL on `sunoapi` (§8), or `scripts/dev/seed-local-suno-key.py` |
| **Platform worker running** | queued work (ingest/packaging, retries) does not advance; exports can stall on missing B2 keys | `Get-CimInstance Win32_Process \| ? CommandLine -match 'platform_api\|run-platform-worker'` |
| **Credits in the test wallet ≥ cap** | the run stops early on `402` | `/quota` `credits_remaining` (the script prints it before planning) |

**One command** — the dry run is the gate. It logs in, reads readiness, pricing and quota,
evaluates every precondition above that is visible over HTTP, prints the plan with the
per-op price and the running total, and exits **without a provider call**:

```powershell
$env:PLATFORM_API_BASE_URL="http://127.0.0.1:8100"
$env:PLATFORM_STUDIO_INTERNAL_TOKEN="<same value musicapi runs with>"
$env:PLATFORM_TEST_EMAIL="<test account email>"
$env:PLATFORM_TEST_PASSWORD="<test account password>"
$env:PLATFORM_SUNO_CALLBACK_BASE_URL="https://<name>.trycloudflare.com"
$env:MUSICAPI_BASE_URL="http://127.0.0.1:4003"          # optional: direct pool health
node scripts/dev/provider-matrix.mjs --budget 320
```

Exit codes: `0` plan printed and every HTTP precondition green; `2` plan printed but a
precondition is red (blocking); `1` usage/config error.

The two facts that are not reachable over HTTP — the charge flag and the `musicapi` key
balance — in one further command each:

```powershell
psql "postgresql://postgres:postgres@127.0.0.1:5432/platform_db" -c "SELECT key, value FROM system_settings WHERE key='credits_only_v3_charge';" -c "SELECT ai_service, operation_type, sub_model, credits_per_operation FROM credit_pricing WHERE ai_service='suno' AND operation_type IN ('music','studio_edit','studio_stems_2','studio_stems_12') ORDER BY operation_type, sub_model;"
psql "postgresql://postgres:postgres@127.0.0.1:5432/sunoapi" -c "SELECT id, label, credits, revoked_at FROM api_keys ORDER BY created_at DESC LIMIT 5;"
```

(Adjust the DSN to `PLATFORM_DATABASE_URL` / `DATABASE_URL`; the sandbox stack may point at
`camxora_pfm_sandbox` — `scripts/dev/README.md`.)

---

## 8. The runner: `scripts/dev/provider-matrix.mjs`

Node 24, **no dependencies** (global `fetch`, `FormData`, `Blob`). Defaults to `--dry-run`.

```
node scripts/dev/provider-matrix.mjs --budget 320                 # plan + prices, no provider call
node scripts/dev/provider-matrix.mjs --budget 320 --execute       # paid run (gated on approval)
node scripts/dev/provider-matrix.mjs --self-test                  # offline: guards + the 188 arithmetic
  --out <dir>       output directory (default docs/studio/reports/provider-matrix/run-<ts>)
  --only a,b        subset of op ids
  --task <uuid>     reuse a successful generation instead of generating one
  --retries <n>     automatic retries across failed paid ops (default 0; the §6 estimate uses 2)
  --timeout <s>     per-operation poll timeout (default 900)
  --poll-interval <s>  default 5
```

Exit codes: `0` green · `2` preconditions not met (the plan is still printed) · `3` a row did
not reach a green terminal state · `1` usage/config error (including the callback refusal).

**Verified offline before commit** (`--self-test`, no network, no credit): the callback guard
rejects `localhost`, `127.0.0.1`, `10.x`, `192.168.x`, `[::1]` and an empty value and accepts a
public domain and a public IPv4; the per-op costs resolve to 10/0/0/0/12/12/12/12/12/12/12/12/
22/60; the base total is **188**; the cap guard runs everything at 320, stops at 58 + six
skipped rows at 60, and runs only the free rows at 5. `--execute` with a private callback
refuses before login:

```
provider-matrix: refusing to execute: PLATFORM_SUNO_CALLBACK_BASE_URL host 127.0.0.1 is
local/private — the provider cannot call back. Start the tunnel first (cloudflared tunnel
--url http://127.0.0.1:8100) — without a public callback the provider cannot report completion.
```

Behaviour that matters:

- **Refuses a local/private `PLATFORM_SUNO_CALLBACK_BASE_URL`** — hard stop before login in
  `--execute`, a blocking FAIL in `--dry-run` — and says why (generation cannot call back).
- **Refuses to execute if any price is 0** for a paid key, or if readiness is not green —
  a mispriced row must not silently become a free run.
- **Budget guard before every paid call**: if `spent + cost > budget`, the operation is
  recorded as `skipped_budget` and nothing is sent. Spend is tracked from
  `/quota.credits_remaining` deltas *and* each operation’s `credits_charged`.
- **Polls to terminal state** (`complete`/`error` for operations, `SUCCESS`/`FAILED`/
  `CANCELLED` for generations) and retries the WAV export on `400 … not ready yet`.
- Writes `provider-matrix.json` (full evidence) and `provider-matrix.md` (id/status table).

Output table columns: `op · endpoint · status · credits · platform id · musicapi job ·
provider clip id · persona id · started/finished · error`.

**Provider ids the API does not return** (generate only) — read-only capture to paste into
the report after the run:

```sql
SELECT id, status, model, external_task_id, audio_id_ok, audio_id_alt,
       created_at, updated_at
FROM suno_tasks
WHERE user_id = '<test user uuid>'
ORDER BY created_at DESC
LIMIT 10;
```

---

## 9. Risks specific to this matrix

| Risk | Mitigation |
|---|---|
| A single `mode` slip charges 60 instead of 12 for “2 stems” | the runner pins `vocal` for #2 and `advanced` for #3; the plan prints the price per row |
| The mashup fixture generation is forgotten in the cap | counted explicitly in §6 (22 for row 10) |
| WAV export blocks ~60 s and can 400 while Suno converts | generous client timeout (180 s) + bounded retries; it is free, so retries cost only rate limit |
| Voice persona cannot be automated | documented as the one manual step; the free clip-persona path is included so the persona row still produces a provider id |
| 12-track stems rate limit / provider refusal | it is last in the order, so a failure there still leaves 11 verdicts recorded |
| Refund path fails after a provider error | the cap is deliberately above the true spend (§6) |
| `musicapi` key runs dry between the two generations | the 20-credit key balance is checked before planning |

---

## 10. Status

- **Call chains:** complete for all 12 matrix operations + both exports (§3).
- **Cost keys:** mapped to `credit_pricing`, read at run time (§5).
- **Budget:** **188 clean / 210 realistic-retry / 308 worst case; approve 320** (§6).
- **Script:** delivered; verified offline (`--self-test`: guards, the 188/cap arithmetic) and
  never executed against a provider.
- **Blocking on you:** the cap, and a public tunnel URL. Until both exist, D4 stays BLOCKED
  and no credit is spent.
