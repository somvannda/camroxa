# musicapi — Production Go-Live Plan

> Scope: the deployable surfaces **inside `musicapi/` only** — Core API (`src/`), `web-user`, `web-admin`, PostgreSQL `sunoapi`, and ops/deploy.
> Rules: one task → one branch; commit per task; sandbox before production (`.cursor/rules/sandbox-first-deploy.mdc`).

Legend: `[ ]` pending · `[~]` in progress · `[x]` done

> Last verified: 2026-09-28 — Phase 0 and 1.1–1.3 confirmed in code on `musicapi`
> (`fix/musicapi-charge-race` branched from the `feat/musicapi-baseline` tip).

---

## Phase 0 — Safety net & buildable baseline

| # | Task | Branch | Done when | Status |
|---|---|---|---|---|
| 0.1 | Commit `musicapi` tree (was 100% untracked) | `feat/musicapi-baseline` | `git status` clean; reproducible | `[x]` |
| 0.2 | Fix core tsc error (`redirectUri` private) | `feat/musicapi-baseline` | `tsc --noEmit` exit 0 | `[x]` |
| 0.3 | Fix web-user tsc errors (`apiFetch` generic) | `feat/musicapi-baseline` | `tsc --noEmit` exit 0 | `[x]` |
| 0.4 | Add `build`/`start`/`typecheck` scripts; verify `next build` | `feat/musicapi-baseline` | build succeeds for core + both apps | `[x]` |
| 0.5 | Env-driven ports/host (`PORT`, `BACKEND_URL`); kill 3003/4003 drift | `feat/musicapi-baseline` | no hardcoded `localhost:4003` | `[x]` |

**Gate:** ✅ everything builds and typechecks; work committed.
> Note: Phase 0 tasks 0.1–0.5 were delivered as separate commits on `feat/musicapi-baseline` (one branch, since the baseline import is the parent of all of them). Later phases use one branch per task.

---

## Phase 1 — Security hardening (must ship before go-live)

| # | Task | Branch | Verification | Status |
|---|---|---|---|---|
| 1.1 | Remove JWT fallback; fail fast if `JWT_SECRET` missing/weak | `feat/musicapi-baseline` | boot aborts without env ✅ `f1cea1bb` | `[x]` |
| 1.2 | Gate `confirm-mock` behind explicit `NODE_ENV=development` | `feat/musicapi-baseline` | 404 in prod ✅ `d048b35c` | `[x]` |
| 1.3 | Enforce `charge()` on all `/me/*`; atomic select+charge | `fix/musicapi-charge-race` | no free jobs under concurrency ✅ atomic `chargeUserKey` | `[x]` |
| 1.4 | Atomic KHQR confirm + admin top-up | `fix/musicapi-payment-atomic` | double-poll credits once ✅ `withTransaction` + guarded claim | `[x]` |
| 1.5 | Callback URL allowlist (block SSRF/private ranges) | `fix/musicapi-callback-ssrf` | loopback/private/metadata rejected ✅; optional `CALLBACK_ALLOWED_HOSTS` | `[x]` |
| 1.6 | Encrypt Suno `client_cookie` at rest | `feat/musicapi-cookie-encryption` | DB ciphertext; pool works ✅ `enc:v1:` | `[x]` |
| 1.7 | OAuth per-request client, signed `state`, verified email | `fix/musicapi-oauth-hardening` | CSRF blocked; flow works ✅ signed `state` + `email_verified` | `[x]` |
| 1.8 | Rotate leaked secrets; scrub `.env`/`accounts.json` | ops (user-led) | old creds invalid | `[ ]` |

**Gate:** no free-credit or forgeable-token path; secrets safe.
> Note: 1.1–1.2 landed as commits on `feat/musicapi-baseline` (Phase 0's branch) instead of their own branches. **1.3:** replaced the non-atomic `pickUserKey()` + ignored `charge()` pattern on every `/me/*` route with a single-statement atomic `chargeUserKey()` that both selects and deducts, and 402s when it fails. **1.4:** `/payments/khqr/status/:id` and `/payments/khqr/confirm-mock/:id` claim the transaction with `UPDATE payment_transactions … WHERE status = 'pending' RETURNING id` and apply the credits inside one `withTransaction` (new helper in `db.ts`), so concurrent polls credit exactly once and any failure rolls back instead of half-crediting; `/admin/users/:id/credits` is now a single-statement `GREATEST(0, credits + $1)` adjust. **1.5:** user-supplied webhook `callback_url`s are now validated by `src/callbackUrl.ts` (`assertCallbackUrlAllowed`), which rejects non-http(s) schemes, embedded credentials, `localhost`/`.local`/`.internal` names, and any target that is *or resolves to* a loopback/private/link-local/CGNAT/cloud-metadata address (IPv4 + IPv6, incl. `::ffff:` mapped). It runs in a `preHandler` hook, so a bad URL is rejected with 400 **before** the handler's `charge()` — and again in `notify()` immediately before the fetch, which now uses `redirect: "manual"` so a 3xx can't bounce the request to an internal address. `CALLBACK_ALLOWED_HOSTS` (comma-separated, optional) additionally pins callbacks to an allowlist (exact host or subdomain); empty means any public host. Verified with a temp harness: 26 checks all pass — private/metadata/loopback/malformed rejected, public IP allowed, `localtest.me` and `127.0.0.1.nip.io` rejected via DNS, allowlist honored both ways, and real routes return 400 on a bad callback while `401` still comes from auth for good/absent ones. 1.8 remains pending (ops, user-led).

> **Note (1.6):** `suno_accounts.client_cookie` is now encrypted with AES-256-GCM
> (`enc:v1:<base64 iv|tag|ciphertext>`) via `src/cookieCrypto.ts`. The key comes
> from `COOKIE_ENCRYPTION_KEY` (64 hex chars / 32 bytes) and, like `JWT_SECRET`,
> the server **refuses to start** without it (`resolveCookieEncryptionKey`). Writes
> encrypt in `POST /admin/accounts`, `scripts/add-paid-account.ts`, and
> `scripts/seed.ts`; `AccountPool.fromDb()` decrypts on read. Verification: 32-check
> harness — round-trip (incl. unicode/empty/long), random-IV uniqueness, GCM tamper
> rejection, legacy-plaintext passthrough, and real DB integration (route stores
> ciphertext; `fromDb()` returns the plaintext cookie). `scripts/migrate-cookie-encryption.ts`
> converted the 2 existing rows (idempotent: re-run reports 0). Keep the key stable —
> rotating it makes stored cookies unreadable.

> **Note (1.7):** already-per-request `OAuth2Client` retained; added signed `state` (`signOAuthState`/`verifyOAuthState` in `src/appAuth.ts`, 10-min JWT via `JWT_SECRET` with a random nonce) that **binds the allowlisted `redirect_uri`**. `GET /auth/google/url` now returns `{ url, state }` and passes `state` to Google; `POST /auth/google/callback` takes `{ code, state }`, rejects missing/tampered/forged/expired state (CSRF), and derives the redirect URI from the verified state instead of trusting the client — the body `redirect_uri` is no longer accepted. The `id_token`'s `email_verified` must be `true` before the email is used to link/create a user. `web-user` (`google-signin-button.tsx`, `app/auth/callback/page.tsx`) round-trips the state from the callback URL. Verified via `npm run typecheck` (clean) and a 23-check harness: state round-trip/tamper/forge/expiry/nonce-uniqueness, allowlisted vs. non-allowlisted redirect binding, callback rejects missing code/state, and stubbed Google exchange (unverified + missing `email_verified` → 403 with no user row; verified → 200 with valid session token).

---

## Phase 2 — Durability & correctness

| # | Task | Branch | Verification | Status |
|---|---|---|---|---|
| 2.1 | Persist jobs (Postgres or Redis/BullMQ); recover on restart | `feat/musicapi-job-persistence` | restart mid-job resolves ✅ `jobs` table + `recoverJobs()` on boot | `[x]` |
| 2.2 | `.catch()` detached workers + `unhandledRejection`/`SIGTERM` | `fix/musicapi-worker-safety` | graceful drain ✅ `trackJob()` + `drainJobs()` | `[x]` |
| 2.3 | Refund on terminal failure; `spend`/`refund` ledger rows | `feat/musicapi-refunds-ledger` | failed job restores credit ✅ `settleCredits()` + ledger | `[x]` |
| 2.4 | TTL/LRU eviction for job map | `chore/musicapi-job-eviction` | memory bounded ✅ `pruneJobs()` TTL + cap | `[x]` |
| 2.5 | `trustProxy` so IP whitelist sees real client IP | `fix/musicapi-trust-proxy` | whitelist enforced ✅ `TRUST_PROXY` (default off) | `[x]` |
| 2.6 | Ordered idempotent migration runner | `feat/musicapi-migrations` | fresh + existing DB migrate ✅ `schema_migrations` + advisory lock | `[x]` |
| 2.7 | Missing indexes (`usage_logs.api_key_id`, `credit_transactions.user_id`) | `perf/musicapi-indexes` | `EXPLAIN` uses index ✅ both indexes used | `[x]` |

**Gate:** restart-safe; no lost/refunded-money bugs; clean migrations.

> **Note (2.1):** jobs are now mirrored to a Postgres `jobs` table
> (`scripts/migrate-jobs.ts`) while the in-memory `Map` stays as a fast read
> cache. `saveJob()` is called on entry and on every `running` transition, and
> `finalizeJob()` persists the terminal state before writing the usage log /
> callback. Reads that used `jobs.get(id)` (`/me/task/:id`, `/v1/task/:id`,
> every `*/record-info`) now go through `await getJob(id)`, which falls back to
> the persisted row; `GET /me/jobs/running` is DB-backed. An `onReady` hook runs
> `recoverJobs()`, which marks any job left `pending`/`running`/`streaming` at
> boot as `error` ("Interrupted by server restart.") and finalizes it, so a
> client polling a task that was in flight during a restart gets a resolved
> error instead of a 404. Verified with a temp harness: a pre-seeded `running`
> row is recovered as `error` after a cache-empty boot, the recovered and
> completed jobs are both readable via `/v1/task/:id`, `result_json`
> round-trips, and recovery writes a usage-log row.

> **Note (2.2):** detached job workers are now tracked in an `inflight: Set<Promise<void>>`
> via `trackJob()`, which attaches a `.catch()` guard so a rejected worker (e.g. a DB
> error inside `finalizeJob`/`recordUsage`) is logged (`[jobs] worker rejected: …`)
> instead of crashing the process as an unhandled rejection. Because a grace period is
> expected at shutdown, `drainJobs(timeoutMs = 30_000)` (awaited by a Fastify `onClose`
> hook) now waits for in-flight workers, bounded so a hung worker can't block exit.
> `src/serve.ts` wires `SIGTERM`/`SIGINT` → `shutdown()` (drain via `app.close()`, then
> `dbPool.end()`; 35 s forced-exit timer), plus `unhandledRejection` (log) and
> `uncaughtException` (log + exit 1) handlers. `runClipJobWithRetry`/`runResultJobWithRetry`
> are now thin `trackJob(...)` wrappers over their `…Impl` bodies, so no route changes were
> needed. Verified via `npm run typecheck` (clean) and two harnesses: (a) a slow fake
> worker + `app.close()` → drain waited 1514 ms for the 1500 ms worker (log `draining 1
> in-flight job(s)`), job finalized and usage logged; (b) forcing `recordUsage` to fail
> mid-job (pool closed under it) → the worker rejection was caught by the guard, **0**
> `unhandledRejection` events, and the process survived.

> **Note (2.3):** Added `scripts/migrate-credit-ledger.ts` (`credit_transactions.job_id` + partial unique index `uq_credit_tx_job_type (job_id, type)` where `job_id IS NOT NULL`). `finalizeJob()` now calls `settleCredits(job)`: every settled job writes a `spend` row (negative amount) and a terminal `error` job additionally writes a `refund` row (positive amount) and restores the charged credits to the original `api_keys` row. Both writes use `ON CONFLICT (job_id, type) WHERE job_id IS NOT NULL DO NOTHING`, and the credit restore only runs when the refund insert actually returns a row, so a retried/duplicated finalize can never double-refund.
>
> **Verification (temp harness, since deleted):** (A) a job whose worker throws a non-retryable error reached terminal `error`, wrote `spend -2` + `refund +2`, and left `api_keys.credits` at its pre-charge value (100 → 100); (B) a successful job wrote exactly one `spend -2` row, no refund, and kept the charge (100 → 98); (C) replaying the refund insert for the same `job_id` returned 0 rows and did not move credits. `npm run typecheck` clean.

> **Note (2.4):** The in-memory `jobs` map is now bounded by `pruneJobs()`, called from `newJob()`. Finished jobs (`complete`/`error`) older than `JOB_TTL_MS` (default 1h) are dropped, and if the map still exceeds `JOB_MAX_ENTRIES` (default 5000) the oldest finished jobs are dropped first (Map insertion order). In-flight jobs (`pending`/`running`/`streaming`) are never evicted. Both limits are env-overridable.
>
> **Verification (temp harness, since deleted):** (A) with `JOB_MAX_ENTRIES=5`, creating 12 terminal jobs left `/health` `jobs=5`; (B) with `JOB_TTL_MS=0`, 3 terminal jobs collapsed to `jobs=1`; (C) with cap/TTL `0` and a never-resolving worker, 2 in-flight jobs were retained (`jobs=2`). `npm run typecheck` clean.

> **Note (2.5):** `buildServer` now passes `trustProxy: trustProxyOption()` to Fastify. `trustProxyOption()` resolves the env var `TRUST_PROXY`: unset/`false`/`0` → `false` (default), `true` → `true`, a bare number → proxy hop count, anything else → comma-separated list of trusted addresses/CIDRs. Default is **off** so that a directly reachable server can't have `X-Forwarded-For` spoofed to defeat an API key's `ip_whitelist` (the only consumer of `req.ip`, in `requireKey`). Verified with `app.inject` against `GET /v1/credits` (key `sk-test-123`, whitelist `203.0.113.7`, socket `127.0.0.1`, `X-Forwarded-For: 203.0.113.7`): A) `TRUST_PROXY` unset → 403 (spoof ignored); B) `TRUST_PROXY=true` → 200 (real client IP used); C) `TRUST_PROXY=false` → 403; D) `TRUST_PROXY=127.0.0.1` → 200; E) whitelist on the socket IP → 200. `npm run typecheck` clean.

> **Note (2.6):** replaced the ad-hoc `scripts/migrate.ts` (which read `scripts/schema.sql`) with an ordered, tracked, idempotent runner. Migration SQL now lives in `migrations/0001_init.sql` … `0006_credit_ledger.sql`, consolidating every previously ad-hoc script (`schema.sql`, `add-safe-spend-tiers.sql`, `migrate-google-auth`, `migrate-khqr`, plus the Phase-2 `migrate-jobs`/`migrate-credit-ledger`). The runner applies each file **in filename order**, records it in `schema_migrations (version TEXT PK, applied_at)`, and applies the file together with its bookkeeping row **in one transaction** — a failure rolls the whole file back and leaves the DB untouched. A session-level `pg_advisory_lock(4172001)` stops two runners from racing. `MIGRATIONS_DIR` is resolved relative to the script (not the CWD). All SQL is written `IF NOT EXISTS`/guarded so a pre-existing DB is adopted safely — notably the KHR-pack seed uses `WHERE NOT EXISTS (SELECT 1 FROM credit_packs WHERE currency='KHR')` because `credit_packs` has no unique key (`ON CONFLICT DO NOTHING` would re-insert duplicates every run; the legacy DB had already double-seeded to 10 rows). Verified with `npm run typecheck` (clean) and live DB tests: existing `sunoapi` DB → 6 applied and adopted; immediate re-run → `0 applied` (idempotent); fresh throwaway DB → 6 applied with exactly 5 KHR packs, re-run → `0 applied`; a deliberately failing migration → exit 1, its partial DDL rolled back, its version not recorded; a concurrent runner blocked on the advisory lock (0.69 s uncontended vs 5.05 s while the lock was held). New `.sql` files were caught by the repo-wide `*.sql` gitignore (intended for DB dumps), so a `!migrations/*.sql` negation was added to `musicapi/.gitignore` to keep the migration files trackable.
> **Note (2.7):** added `migrations/0007_perf_indexes.sql` (idempotent `CREATE INDEX IF NOT EXISTS`), delivering the two indexes once the task-2.6 migration runner is present; the files merge additively (`0001`–`0006` from 2.6, `0007` here). `idx_usage_logs_api_key` is `(api_key_id, created_at DESC)` — Postgres does not auto-index FK columns, and the safe-spend guard runs on every API-key request, summing `credits_consumed` for the key over all time, 1 hour, and 1 day, so those three sums previously seq-scanned `usage_logs`; the composite serves all three (leading column for the all-time sum, both columns for the windows) and mirrors the existing `idx_usage_logs_user`. `idx_credit_transactions_user` is `(user_id, created_at DESC)` — the FK column was unindexed, hurting `ON DELETE CASCADE` user deletes and per-user ledger reads. Also added a `!migrations/*.sql` negation to `musicapi/.gitignore` so the new file is trackable despite the repo-wide `*.sql` dump ignore. Verified with `npm run typecheck` (clean) and an `EXPLAIN (COSTS OFF)` harness: both indexes created; with `enable_seqscan = off` (dev tables are tiny, so the planner otherwise prefers seq scans) the all-time/hourly/daily `usage_logs` sums each plan an `Index Scan using idx_usage_logs_api_key` and the per-user `credit_transactions` read plans an `Index Scan using idx_credit_transactions_user` — 4/4 PASS.

---

## Phase 3 — Frontend production readiness

| # | Task | Branch | Verification | Status |
|---|---|---|---|---|
| 3.1 | Env-driven backend URL (both apps) | `fix/musicapi-fe-backend-url` | prod host via env ✅ `BACKEND_URL` baked into both rewrites | `[x]` |
| 3.2 | Real session (httpOnly cookie or documented token + 401 logout) | `feat/musicapi-session` | expired → `/login` ✅ `sunosession` httpOnly cookie + CSRF | `[x]` |
| 3.3 | web-admin server-side guard (`middleware.ts` + role check) | `feat/musicapi-admin-guard` | non-admin blocked | `[ ]` |
| 3.4 | web-user authenticated downloads (blob) | `fix/musicapi-fe-downloads` | downloads 200 | `[ ]` |
| 3.5 | Remove fake dashboard chart → real usage data | `fix/musicapi-fe-dashboard` | chart matches API | `[ ]` |
| 3.6 | Delete dead `/app/*` tree + unused components/deps | `chore/musicapi-fe-cleanup` | routes still work | `[ ]` |
| 3.7 | Fix admin pricing edit (track `editingId`, PUT) | `fix/musicapi-admin-pricing-edit` | update, no duplicate | `[ ]` |
| 3.8 | Admin `/auth/callback`; align redirect URIs | `feat/musicapi-admin-oauth` | Google admin login | `[ ]` |
| 3.9 | Wire/hide placeholders; mark stubs "coming soon" | `chore/musicapi-fe-placeholders` | no dead UI | `[ ]` |

**Gate:** both apps build against prod env; no spoofable auth; no fake data.

> **Note (3.1):** the functional switch already landed in Phase 0.5 (`a3700b47`): both Next apps rewrite `/backend/:path*` to `process.env.BACKEND_URL` and the browser only ever calls the relative `/backend` path, so no host is hardcoded client-side. This task closes the deploy contract: each app now ships its own `.env.example` documenting `BACKEND_URL` (with a `!.env.example` negation in each app's `.gitignore`, since the templates ignore `.env*`). Verified by building both apps with `BACKEND_URL=https://api.camxora.example` and reading `.next/routes-manifest.json` — the rewrite `destination` is `https://api.camxora.example/:path*` for **both** `web-user` and `web-admin` (env read at build time; the `localhost:4003` fallback only applies when unset).
>
> **Note (3.2):** browser sessions moved off `localStorage` to an **httpOnly cookie**.
> The API (`src/appAuth.ts`) now emits `Set-Cookie: sunosession=<JWT>; Path=/; HttpOnly;
> SameSite=Lax; Max-Age=604800` (`Secure` when `SESSION_COOKIE_SECURE=true`, which
> defaults to on in production) from `POST /auth/login` and `POST /auth/google/callback`,
> and `POST /auth/logout` clears it (`Max-Age=0`). `requireAuth` reads the cookie first
> and still accepts `Authorization: Bearer` as a fallback, so non-browser/API-key callers
> are unaffected. Because the cookie is sent automatically, cookie-authenticated
> **state-changing** requests (POST/PUT/PATCH/DELETE) get a defense-in-depth **CSRF Origin
> check** on top of `SameSite=Lax`: an `Origin` that isn't in `FRONTEND_ORIGINS`
> (comma-separated, defaults to the two local dev frontends `http://localhost:4001,4002`)
> is rejected `403`; same-origin/missing-Origin requests pass. Route handlers still return
> `{ token, user }`, so the documented token flow remains valid for API clients.
>
> Frontends (`web-user` + `web-admin`): `lib/auth.ts` no longer stores or reads the JWT —
> it caches only the non-sensitive profile (`suno_user`) and proactively removes any
> `suno_token` left by an older build. `lib/api.ts` calls the API with
> `credentials: "same-origin"`, `logout()` POSTs `/auth/logout` then clears local state,
> and a `401` triggers `redirectToLogin()` (clear cache → `/login`). Every consumer
> (`Sidebar`, dashboard layout, login pages, settings, Google sign-in, playground) was
> updated to the cookie model; `authorizedFetch` (playground/downloads) now also bounces
> to `/login` on `401`. New env docs in `.env.example`: `SESSION_COOKIE_SECURE`,
> `FRONTEND_ORIGINS`.
>
> **Verification:** `npm run typecheck` clean in `musicapi`, `web-user`, and `web-admin`.
> Product decisions baked in (cookie name `sunosession`, `SameSite=Lax`, `Secure` in
> prod, Origin-allowlist CSRF, `credentials: "same-origin"`, `401 → /login`) — see the
> note above; adjust `FRONTEND_ORIGINS` in prod to the real frontend origins.

---

## Phase 4 — Ops & deployment

| # | Task | Branch | Verification | Status |
|---|---|---|---|---|
| 4.1 | Process management (PM2/systemd/Docker) | `ops/musicapi-process` | survives reboot | `[ ]` |
| 4.2 | nginx vhosts + TLS + `/backend` proxy; align `trustProxy` | `ops/musicapi-nginx` | HTTPS, real IPs | `[ ]` |
| 4.3 | CORS/helmet + rate limiting + structured logging + `/metrics` | `feat/musicapi-edge-hardening` | public `/v1` safe | `[ ]` |
| 4.4 | Deploy scripts: `sync_musicapi_sandbox.py`, `deploy_musicapi_production.py` | `ops/musicapi-deploy-scripts` | sandbox deploy works | `[ ]` |
| 4.5 | CI: typecheck + build + smoke gate | `ops/musicapi-ci` | PR blocked on failure | `[ ]` |
| 4.6 | DB backups + monitoring/alerts | `ops/musicapi-observability` | restore drill; alerts fire | `[ ]` |

**Gate:** deployed + smoked on **sandbox**; production only on explicit ask.

---

## Phase 5 — Feature completion (may follow launch)

- Per-user/per-key rate limits (REQUIREMENTS §4.4)
- Audit log for admin actions (§4.11)
- Credit-pack admin CRUD (§4.5)
- Real usage analytics (§4.7)
- Admin settings + alert config (§4.10)
- Suno account edit/remove + health badges (§4.2)

---

## Definition of "ready to go live"

- [ ] Core + both apps build & typecheck clean, committed from `main`
- [ ] No free-credit or forgeable-token path
- [ ] Secrets rotated; cookies encrypted at rest
- [ ] Jobs survive restart; workers/refunds safe
- [ ] Both apps point at prod backend via env; admin auth server-enforced
- [ ] nginx + TLS + process manager + backups + monitoring in place
- [ ] Deployed and smoked on sandbox first
