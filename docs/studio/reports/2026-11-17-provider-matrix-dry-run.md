# Provider matrix — W6 dry run (2026-11-17)

`docs/studio/RESIDUAL_VERIFICATION_PLAN.md` D4 asks for the twelve paid provider operations
to be proven end to end against the real provider. The runner already exists and refuses to
spend anything without an approved cap, so this pass records exactly what it will do and
what it still needs. **No provider call was made and no credit was spent.**

## Command

```powershell
$env:PLATFORM_API_BASE_URL = 'http://127.0.0.1:8100'
$env:PLATFORM_STUDIO_INTERNAL_TOKEN = '<musicapi STUDIO_INTERNAL_TOKEN>'
$env:MUSICAPI_BASE_URL = 'http://127.0.0.1:4003'
$env:PLATFORM_TEST_EMAIL = 'somvannda@gmail.com'      # local sandbox user
$env:PLATFORM_TEST_PASSWORD = 'StudioLocal!2026'
node scripts/dev/provider-matrix.mjs --budget 320
```

`--budget` is required and is a hard cap: a row whose cost would cross it is skipped, never
partial. `--execute` is the only flag that can spend, and it re-checks every precondition
first. Exit `2` means preconditions were not met (the plan is still printed).

## Plan (prices read from the live pricing table, not hard-coded)

| # | Operation | Credits | Endpoint |
|---|---|---|---|
| 1 | Generate a song | 10 | `POST /web-music/generate` |
| 2 | Export WAV | 0 | `GET /web-music/generations/{task_id}/download-wav?variant=ok` |
| 3 | Export MP3 | 0 | `GET /web-music/generations/{task_id}/download?variant=ok` |
| 4 | Voice persona | 0 | `POST /web-music/studio/voice/personas` |
| 5 | Bounce / upload (upload + upload-extend) | 12 | `POST /web-music/studio/uploads` → `/uploads/{id}/extend` |
| 6 | Stems — 2 track | 12 | `POST /web-music/studio/generations/{task_id}/stems` |
| 7 | Cover | 12 | `POST /web-music/studio/generations/{task_id}/cover` |
| 8 | Extend | 12 | `POST …/extend` |
| 9 | Remaster | 12 | `POST …/remaster` |
| 10 | Add vocals | 12 | `POST …/add-vocals` |
| 11 | Add instrumental | 12 | `POST …/add-instrumental` |
| 12 | Replace section | 12 | `POST …/replace-section` |
| 13 | Mashup (+ fixture generation) | 22 | `POST /web-music/studio/mashup` |
| 14 | Stems — 12 track | 60 | `POST …/stems` |
| | **total** | **188** | |

Wallet read at plan time: **448 credits** (sandbox). A 320 cap still leaves 128 credits of
headroom for retries of a single non-terminal row, which is why 320 was recommended over the
bare 188.

## Preconditions

Passing now: `readiness.tables`, `readiness.pricing`, `readiness.storage`,
`readiness.internal_token`, `readiness.suno_api_base_url`, and all four prices
(`studio_edit` 12, `stems_2` 12, `stems_12` 60, `music` 10).

Failing, and why:

| Precondition | State | What it needs |
|---|---|---|
| `callback_public` | **FAIL** — not set, so a generation would call back to `https://localhost` | a public tunnel to `:8100` (e.g. `cloudflared tunnel --url http://127.0.0.1:8100`) exported as `PLATFORM_SUNO_CALLBACK_BASE_URL`, and the same value in the platform API's environment before it starts |
| `readiness.suno_callback_base_url` | **FAIL** — same cause, read from the running API | restart the API with the tunnel base set |
| `readiness.musicapi` / `readiness.musicapi_accounts` | **FAIL** — these mirror the probe below | follow from the next row |
| `musicapi.health` | **FAIL** — `AbortSignal.timeout(10000)` expired while the full Playwright suite was running against the same stack | re-probe on an idle stack; `GET :4003/internal/studio/health` with the internal token answers `{"ok":true,"accounts":1,"active_accounts":1,"jobs":1}` in well under a second when the host is not saturated |

## What is required to close D4

1. An approved cap. **320 credits recommended** (188 plan + retries); 210 if only two
   retries are acceptable; 188 if nothing may be re-run.
2. A public tunnel to the platform API, with `PLATFORM_SUNO_CALLBACK_BASE_URL` set before
   the API starts.
3. An idle stack for the run: one shell lifetime, `--budget 320 --execute`, writing to
   `docs/studio/reports/provider-matrix/run-1`.

Everything else — the runner, the pricing read, the precondition gate, the per-row evidence
(platform id, musicapi job id, provider clip, persona) — is in place and exercised by this
dry run.
