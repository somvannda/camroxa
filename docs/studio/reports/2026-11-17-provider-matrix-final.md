# Provider matrix — D4 PASS (2026-11-17)

**Plan:** `RESIDUAL_VERIFICATION_PLAN.md` D4 / W6 · **Cap approved:** 320 credits
**Command (generate):** `--budget 320 --execute --only generate --timeout 900`
**Command (dependent rows):** `--only export_wav,…,stems_12 --task 3b6943ab-…`
**Evidence:** `docs/studio/reports/provider-matrix/run-8-generate-v6/`,
`docs/studio/reports/provider-matrix/run-9-dependent-rows/`

## Result

All fourteen rows reached a green terminal state. **188 credits spent** — exactly the plan
total — from a 448-credit wallet, leaving 260. Model `V6`.

| # | Operation | Status | Credits | Platform id | musicapi job | Provider clip |
|---|---|---|---|---|---|---|
| 1 | Generate a song | SUCCESS | 10 | `3b6943ab-91fe-413a-9323-d92bfc559e0c` | — | 2 ready clips |
| 2 | Export WAV | downloaded | 0 | `3b6943ab-…` | — | real RIFF bytes |
| 3 | Export MP3 | downloaded | 0 | `3b6943ab-…` | — | real MP3 bytes |
| 4 | Voice persona | complete | 0 | `87ae84b9-4e3d-46b9-a3ad-9d1efd0d5af8` | `bfaeadc2-d27d-4e89-9656-a31597aee90c` | persona `faaa9123-…` |
| 5 | Bounce / upload + extend | complete | 12 | `addacd54-3fef-4f56-9616-6a74878c8658` | `58007ee7-114d-4df0-9f55-b485605a073e` | `7972b27b-…` |
| 6 | Stems — 2 track | complete | 12 | `0effb534-255b-41a5-a4c2-a6817ec1cb65` | `1ff097b8-9b26-4501-90e5-4104d4de570b` | `28bdb83c-…` |
| 7 | Cover | complete | 12 | `344d96d5-6bad-4706-9867-410753238727` | `77a0a310-7e23-43a8-b886-790901a4a07d` | `28bdb83c-…` |
| 8 | Extend | complete | 12 | `1a5e35ce-c8e5-418b-9e0d-ce13e6f7bb6c` | `12d4d01b-0b9a-4b4a-a87b-ee04ef123bcf` | `28bdb83c-…` |
| 9 | Remaster | complete | 12 | `856aa1e2-f089-4f27-94a3-02c2a61cd745` | `d4664135-a5ed-4e9f-be1f-780ade57b2bd` | `28bdb83c-…` |
| 10 | Add vocals | complete | 12 | `7bc564be-8f41-4bc7-b57a-e777dbc38f18` | `b0224499-268d-4dc1-bd7c-bdad08c34cd1` | `28bdb83c-…` |
| 11 | Add instrumental | complete | 12 | `870181a0-2743-422d-a366-64215e77e53f` | `3f73e5b7-2693-4b38-8a76-2f36367b3a5d` | `28bdb83c-…` |
| 12 | Replace section | complete | 12 | `24048721-188f-49a9-a7e7-6c3407932ae0` | `e2482180-f99c-456c-9290-fce86c487468` | `28bdb83c-…` |
| 13 | Mashup (+ fixture generation) | complete | 12 + 10 fixture | `c9303483-8dba-4b59-823d-69755d7e664c` | `bbb6b1f5-79de-4d63-b142-198306ba15ed` | `28bdb83c-…` |
| 14 | Stems — 12 track | complete | 60 | `41147dc2-1ce3-4f12-b932-df5619ff5c69` | `187159d3-3764-433b-ad1e-781063daac2f` | `28bdb83c-…` |

Every row carries a platform id **and** a musicapi job id, so each operation can be followed
from the platform record to the provider job without guessing. The dependent run re-uses the
generated source (`--task`) instead of paying for a second song, which is why the generate row
appears once at 10 credits.

## What it took to get here

The matrix failed nine times before this pass, and none of the failures was the Studio code.
The chain, in the order it was discovered:

| Cause | Evidence | Fix |
|---|---|---|
| The first three generations never left `pending` | `job_queue`: `No module named platform_api.services.credit_service` — the worker had been started from a since-deleted worktree | started a worker from this checkout |
| A dead generate job left the task pending forever | `suno_tasks.status = pending`, `error_message = NULL`, reservation held | **product fix**: the worker now fails the task through the refund path on exhausted attempts (tests + sandbox repair) |
| Submits returned `401 submit_task` with a valid key | worker traceback: `401 … https://musicapi.camxora.com/api/v1/generate` | the worker needs `PLATFORM_SUNO_API_BASE_URL=http://127.0.0.1:4003`; `platform_api/.env` does not set it, so anything not started by `scripts/dev/studio-stack.ps1` silently targets production |
| The runner refused healthy stacks | `/internal/studio/health` cold call measured **12 035 ms** and **23 277 ms**, warm 8–11 ms; the platform's readiness probe allows 10 s | warm the endpoint before reading readiness; raise the runner probe to 30 s |
| A 15-minute run outlived its token | JWT `expires_in: 900`, poll window 900 s | refresh-and-retry once on `401` |
| Spend was under-reported | wallet 448 → 438 while the report said 0 | `spent = max(row total, wallet delta)` |

The environment rule worth remembering: **a process that submits to the provider needs
`PLATFORM_SUNO_API_BASE_URL` in its own environment**, and the fallback is production.

## Reproducing

```powershell
# stack in one shell lifetime, worker included and pointed at local musicapi
$env:PLATFORM_SUNO_API_BASE_URL = 'http://127.0.0.1:4003'
$env:PLATFORM_SUNO_CALLBACK_BASE_URL = 'https://<tunnel>.trycloudflare.com'
python scripts/dev/run-platform-worker.py

python scripts/dev/seed-local-suno-key.py --database-url postgresql+asyncpg://postgres:postgres@localhost:5432/camxora_pfm_sandbox

$env:PLATFORM_STUDIO_MODEL = 'V6'
node scripts/dev/provider-matrix.mjs --budget 320 --execute --only generate --timeout 900
node scripts/dev/provider-matrix.mjs --budget 320 --execute --task <task_id> --only export_wav,export_mp3,persona,bounce_upload,stems_2,cover,extend,remaster,vocals,instrumental,replace,mashup,stems_12 --timeout 900
```

`V6` is used because it is the model every successful generation in this sandbox has used;
`V6_MINI` has never completed here.
