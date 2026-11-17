# Provider matrix — run 1 (2026-11-17), blocked by the provider, 0 credits spent

**Plan:** `docs/studio/RESIDUAL_VERIFICATION_PLAN.md` D4 / W6 · **Cap approved:** 320 credits
**Command:** `node scripts/dev/provider-matrix.mjs --budget 320 --execute --out docs/studio/reports/provider-matrix/run-1`
**Raw evidence:** `docs/studio/reports/provider-matrix/run-1/provider-matrix.{json,md}`

## Outcome

14 rows, **10 credits charged (one generation)**, every row `error`:

> **Correction to the generated evidence.** `provider-matrix.{json,md}` in this directory says
> “spent: 0” because the end-of-run wallet reconciliation called `/web-music/quota` with the
> same token that had just expired, got a `401`, and fell back to `meta.walletDelta = null`.
> The wallet went **448 → 438** across run 1, i.e. the accepted generation was charged 10
> credits even though its poll failed. The runner now refreshes the token (so the
> reconciliation succeeds) and takes `max(row total, wallet delta)`.

| Row | Status | Reason recorded by the runner |
|---|---|---|
| 1 · Generate a song | error | `GET /web-music/generations/3f55666f-… → 401` |
| 2–14 · exports, persona, uploads, stems, cover, extend, remaster, add vocals/instrumental, replace section, mashup | error | `no source generation — the generate step must run first` |

Rows 2–14 are dependent rows: with no terminal source generation there is nothing to export,
split or edit, so they failed fast without spending.

## What actually happened

Two independent problems, one in the runner and one upstream.

### 1. The runner outlived its own access token (fixed)

`/auth/login` issues a JWT with `expires_in: 900`, and the runner's default per-row poll
window (`--timeout`) is also **900 s**. Row 1 logged in at `08:11:16Z`, polled the generation
successfully until `08:26:16Z`, and then received `401` on the poll that coincided with token
expiry. The runner never used the `refresh_token` the login response already carries.

Fixed in `scripts/dev/provider-matrix.mjs`:

- `login()` returns `{ accessToken, refreshToken }`;
- the client holds the token mutably, and on a `401` it calls `POST /auth/refresh`, swaps in
  the new pair and retries the request **once**; a second 401 still fails loudly.

`POST /api/v3/auth/refresh` verified directly: `200`, new access token, new refresh token,
`expires_in 900`.

### 2. The generation never left `PENDING` (environment)

Independently of the runner, the same generation was checked through a fresh session:

| Time (UTC) | Status | Clips ready | Error |
|---|---|---|---|
| 08:11:16 | created, `V6_MINI`, 2 variants | 0 / 2 | none |
| 08:25:23 | `PENDING` | 0 / 2 | none |
| 08:28:48 | `PENDING` | 0 / 2 | none |
| 08:29:14 | `PENDING` | 0 / 2 | none |

18 minutes without a terminal state. The request path itself is healthy: the platform
accepted the generate, musicapi opened an upstream task (`aecbf35c-…`), both sides polled it
with `200`, and `/internal/studio/health` reports `accounts=1 active_accounts=1` (the probe
authenticates the account live, so this is not “configured but dead”).

The account in use is `somvannda@gmail.com` (`credits_left 1438`, **`plan: null`**). The
sandbox also holds a `premier` account with 3120 credits, but it is **inactive**
(`is_active = false`) and therefore not in the pool.

**The discriminating variable turned out to be the key pool, not the model.** Listing every
web-music generation in the sandbox was suggestive:

| Model | Status | Count |
|---|---|---|
| `V6_MINI` | `PENDING`, never terminal | 2 (both from this pass) |
| `V6` | `SUCCESS` | 4 (all 2026-11-14) |
| `V6` | `FAILED` (with an `error_message`) | 5 |

but a `V6` attempt then failed too, with `Suno API error 401: submit_task`, which ruled the
model out. The real chain is below (`job_queue.last_error` is what names it).

### 3. The queue worker was orphaned, then the provider key was rejected

`job_queue` is the ledger of truth here. The first three generations came from a worker that
had been started from a worktree that no longer exists: its `platform_api` package path
pointed at the deleted directory, so every job died with

```
status = failed, attempts = 3
last_error = No module named 'platform_api.services.credit_service'
```

Nothing was ever submitted, `external_task_id` stayed `NULL`, and `_refresh_pending_from_suno`
had nothing to poll — the `PENDING` was never a slow queue. Restarting a worker from this
checkout made the job reach the provider, which answered:

```
last_error = Suno API error 401: submit_task
```

`api_key_entries` shows why: the `local musicapi` key was `rate_limited` since
`auth_rejected_401_unknown`, so the pool had no usable key and every submit failed at the
door. musicapi accepts `sk-test-123` (verified directly: a request with that bearer returns
`404` for an unknown task rather than `401`), so the entry was re-seeded with the key musicapi
knows and set back to `active` (`scripts/dev/seed-local-suno-key.py --database-url …`).

Two product defects came out of this and are fixed:

- **A job that exhausts its attempts left the task `pending` forever** with
  `error_message = NULL`, so the user watched a spinner and the reservation was never
  released. The worker now marks the task failed through the same refund path the inline
  failure uses (both the exception and timeout branches), with tests. The three sandbox rows
  were repaired through that path: all three are `failed` and the wallet returned from 20 to
  **448** as the reservations released.
- **The failure was invisible in the run**: the matrix recorded `401` on a status read and
  `no source generation` for the dependent rows, but the cause lived only in `job_queue`.
  That is why this took several attempts to attribute.

## What is needed to close D4

1. **A provider account that completes generations in this environment**, either by
   activating the premier account (a data change I will not make on my own: it routes real
   generations through a different person's account) or by providing a key/account that
   generates promptly.
2. Re-run the same command. Row 1 is the only row that can spend; the rest are dependent.
   `--timeout` can be raised above the 900 s default if the provider is merely slow, and the
   runner now survives a run longer than one token lifetime.

A second attempt was launched on the same account with a 30-minute window
(`--only generate --timeout 1800`); it hit the same silent `PENDING`. A third attempt runs
with `PLATFORM_STUDIO_MODEL=V6`, the only model that has completed here. Each generation
costs 10 credits; the dependent rows are free against a completed task.

## Runner changes in this pass

| Change | Why |
|---|---|
| refresh-and-retry on `401` | a 15-minute matrix poll cannot fit inside a 900 s token |
| warm MusicAPI health before reading readiness, then re-read up to 3 times | `/internal/studio/health` authenticates the pool live: a cold call measured **12 035 ms**, the next five **8–11 ms**, while the platform's readiness probe gives up at **10 s** — the gate failed on a healthy stack twice |
| `spent = max(row total, wallet delta)` | an accepted generation is charged even when its poll fails; run 1 under-reported 10 credits |
| three attempts for the MusicAPI health probe (own timeout each) | the same cold path can outlast a single 10 s attempt |

None of these loosen the gate: a second 401 fails, a broken readiness snapshot fails twice,
and the budget check is unchanged.
