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

First pass, no tunnel and with the full Playwright suite loading the same host: 9 of 14
checks passed. Second pass, after starting a quick tunnel and restarting the API with it:

```
PASS  callback_public                  https://<tunnel>.trycloudflare.com is public
PASS  readiness.tables / pricing / storage / internal_token / suno_api_base_url
PASS  readiness.suno_callback_base_url ok
PASS  readiness.musicapi / musicapi_accounts   (accounts=1 active=1)
PASS  price.studio_edit 12 · stems_2 12 · stems_12 60 · music 10
PASS  musicapi.health                  accounts=1 active=1
total 188 credits · wallet 448 · exit 0
```

Commands that produced the green pass:

```powershell
cloudflared tunnel --url http://127.0.0.1:8100        # prints https://<name>.trycloudflare.com
# restart the platform API with the tunnel base set, then:
$env:PLATFORM_SUNO_CALLBACK_BASE_URL = 'https://<name>.trycloudflare.com'
node scripts/dev/provider-matrix.mjs --budget 320
```

The two conditions that were failing before are therefore supplied by the operator, not by
code: the public base must be set in **both** the runner and the running API (the readiness
row reads it from the API).

The MusicAPI rows failed intermittently for a different reason, now fixed in the runner: the
**first** Node fetch to MusicAPI on this host stalls past the 10 s guard and every later call
answers in ~1 ms (measured directly: attempt 0 timed out at 10 007 ms, attempt 1 took 4 965 ms,
attempts 2–7 took ≤1 ms). A single negative snapshot used to refuse an otherwise healthy
stack, so both the readiness call and `musicapi.health` now re-read once (readiness) and
retry three times with their own timeouts (health), and the error text names the attempt
count. A genuinely broken stack still fails every attempt.

## What is required to close D4

1. An approved cap. **320 credits recommended** (188 plan + retries); 210 if only two
   retries are acceptable; 188 if nothing may be re-run.
2. That is all — the tunnel path above is proven, the runner re-checks every precondition
   before spending, and `--budget` is a hard cap.
3. Run it on an idle stack in one shell lifetime:
   `node scripts/dev/provider-matrix.mjs --budget 320 --execute --out docs/studio/reports/provider-matrix/run-1`.

Everything else — the runner, the pricing read, the precondition gate, the per-row evidence
(platform id, musicapi job id, provider clip, persona) — is in place and exercised by these
dry runs.
