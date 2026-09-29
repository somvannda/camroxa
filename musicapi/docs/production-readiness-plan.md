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
| 3.3 | web-admin server-side guard (`proxy.ts` + role check) | `feat/musicapi-admin-guard` | non-admin blocked ✅ cookie → `/auth/me` → `/login` | `[x]` |
| 3.4 | web-user authenticated downloads (blob) | `fix/musicapi-fe-downloads` | downloads 200 ✅ authenticated blob (401 → `/login`) | `[x]` |
| 3.5 | Remove fake dashboard chart → real usage data | `fix/musicapi-fe-dashboard` | no fake data ✅ fabricated `Math.random()` chart removed | `[x]` |
| 3.6 | Delete dead `/app/*` tree + unused components/deps | `chore/musicapi-fe-cleanup` | routes still work ✅ `/app/*` removed, `/dashboard/*` served | `[x]` |
| 3.7 | Fix admin pricing edit (track `editingId`, PUT) | `fix/musicapi-admin-pricing-edit` | update, no duplicate ✅ PUT `/admin/pricing/:id` | `[x]` |
| 3.8 | Admin `/auth/callback`; align redirect URIs | `feat/musicapi-admin-oauth` | Google admin login ✅ `/auth/callback` + admin role gate | `[x]` |
| 3.9 | Wire/hide placeholders; mark stubs "coming soon" | `chore/musicapi-fe-placeholders` | no dead UI ✅ 404 links + inert controls removed | `[x]` |

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
> **Note (3.3):** web-admin access control is now **server-side**. The old guard was a
> client component (`app/admin/layout.tsx` + `app/page.tsx` calling `getUser()` and
> `router.replace`) reading a `localStorage` profile that any visitor could spoof — it
> blocked nobody who opened devtools. Replaced by `web-admin/proxy.ts` (Next.js **16**
> renamed the `middleware.ts` file convention to `proxy.ts` and the exported function
> from `middleware` to `proxy`; a stale `middleware.ts` still typechecks but is **never
> executed** at runtime, so shipping one would have been a silent hole). For `/` and
> `/admin/:path*` the guard reads the httpOnly `sunosession` cookie, forwards it to the
> API's `GET /auth/me`, and only calls `NextResponse.next()` when the response is OK and
> `role === "admin"` **and** `status === "active"`; every other outcome (missing cookie,
> non-2xx, backend unreachable, wrong role, suspended) redirects to `/login`. A rejected
> session also clears the dead cookie (`Expires=1970`) so the login page starts clean; a
> backend that's down is treated as **fail-closed** (redirect, cookie kept). The API stays
> the authority — every `/admin/*` route still calls `requireAdmin` — and `JWT_SECRET`
> never leaves the API. The `admin` layout and root page became server components that
> only handle chrome / `redirect("/admin")`. `.env.example` documents that the guard calls
> `${BACKEND_URL}/auth/me` (same value the `/backend/*` rewrite uses). Verified against a
> stub `/auth/me` (port 4103): no cookie → `/login`; `role=user` → `/login` + cookie
> cleared; `role=admin, status=suspended` → `/login` + cookie cleared; `role=admin,
> status=active` → `200` on `/admin` and `/admin/users`; stub stopped → `/login`
> (fail-closed). `npm run typecheck` + `npm run build` pass (`ƒ Proxy (Middleware)`).
>
> **Note (3.4):** `app/dashboard/playground/page.tsx` was the last place downloading clips
> with a raw `<a href="/backend/me/download?..."> target="_blank"` — a plain navigation that
> the browser issues **without** the session (it was 401 → a JSON error page in a new tab
> before 3.2, and still bypassed the `401 → /login` handling and popup-blocked in some
> browsers). It now renders a `ClipDownloadButtons` client component that calls the shared
> `downloadClip()` helper (`components/playground.tsx`), exactly like the `ClipCard` used
> by every other dashboard page: `authorizedFetch` sends `credentials: "same-origin"` so
> the httpOnly `sunosession` cookie authenticates the request, the response body becomes a
> `Blob` → object URL → synthetic `<a download>`, the server-provided filename is honored,
> a non-OK status surfaces its `{ error }` inline, and a `401` triggers `redirectToLogin()`.
> The now-unused `clipDownloadUrl()` export was deleted so the unauthenticated pattern
> can't creep back. Verified: `npm run typecheck` clean and `npm run build` succeeds
> (26/26 static pages, `/dashboard/playground` present); the underlying
> `GET /me/download` (MP3/WAV → HTTP 200 real audio bytes) is already verified in
> `ENDPOINT_STATUS.md` rows 1.15–1.16.
>
> **Note (3.5):** the dashboard's "Real-time Success Rate" line chart was **entirely
> fabricated** — every one of its 14 points came from `Math.random()` (`85 + rand*15`),
> with an invented per-minute X axis, so it showed a fake 85–100% success rate regardless
> of reality. The real `GET /me/usage` returns only `total_24h`/`success_24h`/`failed_24h`
> plus a **daily** `series` of `{ day, count, credits, spend }` — there is no per-minute (or
> per-day success/failed) time series to back it, so no honest version of that chart is
> possible from the API today. The chart and its supporting code (`successRateSeries`,
> `maxMin`, `timeStr`, the `new Date()` clock, and the now-unused optional
> `success`/`failed` fields on the `series` interface) were removed, leaving the dashboard
> with only API-backed visuals: the real 24h success/failure/other card and the real daily
> usage bar chart (both driven by `/me/usage`). Verified: no `Math.random()` remains in
> `web-user`; `npm run typecheck` clean and `npm run build` succeeds (26/26 static pages,
> `/dashboard` present).
>
> **Note (3.6):** `web-user` carried a **dead legacy route tree** at `app/app/*`
> (`api-keys`, `billing`, `playground`, `updates`, `usage`, `layout.tsx`, `page.tsx`) — a
> duplicate of the real `app/dashboard/*` app. Its `layout.tsx` was only a client redirect
> stub (`/app/* → /dashboard/*`), so the tree was pure dead weight served at duplicate
> URLs. Also removed: `components/Sidebar.tsx` (a stale duplicate of the dashboard's inline
> sidebar, imported nowhere) and `components/ComingSoon.tsx` (no usages). Deleted the
> unused `qrcode.react` dependency (never imported in any `.ts`/`.tsx`; removed from
> `package.json` and lockfile). Repointed the remaining live redirect targets from `/app`
> to `/dashboard`: `components/auth-modal.tsx` (`redirectTo` + `onSuccess`),
> `components/google-signin-button.tsx` (`redirectTo` default), and
> `app/auth/callback/page.tsx` (post-OAuth fallback). Verified: `npm run typecheck` clean
> and `npm run build` succeeds — 20/20 static pages, all `/dashboard/*` routes present and
> no `/app/*` route remains.
>
> **Note (3.7):** the admin pricing page's **Edit** button only pre-filled the form — it
> never remembered *which* row was being edited. On save the page always `POST`ed to
> `/admin/pricing`, whose upsert matched on `(endpoint, model)`. Editing a row's
> `endpoint`/`model` therefore inserted a **new** row and left the old one behind (a
> duplicate); the `pricing` table has no DB-level uniqueness to catch it. Fixed by tracking
> `editingId` in the form state (`web-admin/app/admin/pricing/page.tsx`), wiring
> Edit/Cancel/toggle to set/clear it, and routing updates to a new `PUT /admin/pricing/:id`
> endpoint (`src/server.ts`) that updates `endpoint`, `model`, and `credit_cost` by id
> (404 when missing). New prices still use `POST`. Verified: `tsc --noEmit` clean for core +
> `web-admin`; `next build` succeeds (12/12 static pages, `/admin/pricing` present).
>
> **Note (3.8):** the core API already allowlisted **both** Google redirect URIs
> (`GOOGLE_REDIRECT_URI_USER` → `…:4001/auth/callback`, `GOOGLE_REDIRECT_URI_ADMIN` →
> `…:4002/auth/callback`, see `src/server.ts` + `.env.example`), but `web-admin` had no
> client for it: no `/auth/callback` route, no Google button — admin sign-in was
> email/password only, so the admin redirect URI was dead. Added
> `web-admin/components/google-signin-button.tsx` (4002 fallback, `/admin` default) and
> `web-admin/app/auth/callback/page.tsx`, and wired the button into the admin login page
> behind an "or" divider. The callback **re-checks `role === "admin"`** before redirecting
> (mirrors the login page's gate) rather than relying on `proxy.ts` to bounce a non-admin.
> `/auth/callback` sits outside the proxy matcher (`["/", "/admin/:path*"]`), so it is
> reachable while signed out. Verified: `tsc --noEmit` clean; `next build` succeeds
> (13/13 static pages, `/auth/callback` + `/admin` present). Prod action: register the real
> `https://admin.yourdomain.com/auth/callback` in Google Cloud Console and set
> `GOOGLE_REDIRECT_URI_ADMIN` to match.
>
> **Note (3.9):** audited both apps for dead/inert UI. **404 links removed:** the dashboard
> sidebar's `Logs` item (`/dashboard/logs`) and the admin sidebar's `Logs` item
> (`/admin/logs`) both pointed at routes that don't exist (confirmed absent from `next
> build`'s route list) — deleted from `web-user/app/dashboard/layout.tsx` and
> `web-admin/components/Sidebar.tsx`. **Inert controls removed** from the dashboard shell:
> the non-wired `…` "more" button in the sidebar header, the do-nothing `English` language
> row (only one language today), and the two placeholder support links
> (`https://discord.gg/yourinvite`, `https://t.me/yourchannel`) — no real invite exists yet,
> so they're hidden rather than shipping a fake URL. The admin Sidebar's bottom `Settings`
> **button** (a duplicate of the real `/admin/settings` NAV link that did nothing) was also
> removed. **Placeholder email wired:** the landing page's `mailto:support@yourdomain.com`
> (×2) now points at `support@camxora.com` (the brand domain already used throughout
> `docs/`). **Stubs marked:** `web-admin/app/admin/{analytics,settings}` still render the
> shared `ComingSoon` component; its copy now reads "This section is coming soon." (matching
> the plan's wording). The Billing page's Buy buttons stay intentionally disabled behind a
> visible "Payment processing is not yet connected" note (payments are a later phase).
> Verified: `npm run typecheck` clean in `musicapi`; `npm run build` clean in both apps
> (web-user 20/20, web-admin 13/13 static pages) with no `*logs` route in either.
>
> **Verification:** `npm run typecheck` clean in `musicapi`, `web-user`, and `web-admin`.
> Product decisions baked in (cookie name `sunosession`, `SameSite=Lax`, `Secure` in
> prod, Origin-allowlist CSRF, `credentials: "same-origin"`, `401 → /login`) — see the
> note above; adjust `FRONTEND_ORIGINS` in prod to the real frontend origins.

---

## Phase 4 — Ops & deployment

| # | Task | Branch | Verification | Status |
|---|---|---|---|---|
| 4.1 | Process management (PM2/systemd/Docker) | `ops/musicapi-process` | survives reboot | `[x]` systemd units + boot enable ✅ |
| 4.2 | nginx vhosts + TLS + `/backend` proxy; align `trustProxy` | `ops/musicapi-nginx` | HTTPS, real IPs | `[x]` nginx vhosts + `TRUST_PROXY` ✅ |
| 4.3 | CORS/helmet + rate limiting + structured logging + `/metrics` | `feat/musicapi-edge-hardening` | public `/v1` safe | `[x]` edge hardening ✅ |
| 4.4 | Deploy scripts: `sync_musicapi_sandbox.py`, `deploy_musicapi_production.py` | `ops/musicapi-deploy-scripts` | sandbox deploy works | `[x]` sandbox deploy + smoke ✅ |
| 4.5 | CI: typecheck + build + smoke gate | `ops/musicapi-ci` | PR blocked on failure | `[x]` two path-gated jobs ✅ |
| 4.6 | DB backups + monitoring/alerts | `ops/musicapi-observability` | restore drill; alerts fire | `[x]` nightly pg_dump + 5-min health probe ✅ |

**Gate:** deployed + smoked on **sandbox**; production only on explicit ask.

> **Note (4.1):** chose **systemd** (matches the platform's existing `camxora-api`,
> `camxora-worker-*`, `camxora-website/portal/music` units rather than introducing PM2/Docker).
> Three versioned units under `scripts/deploy/systemd/`: `camxora-musicapi.service` (core,
> `npm run start` → `node dist/serve.js`, `PORT=4003`), `camxora-musicapi-web-user.service`
> (`next start -p 4001`) and `camxora-musicapi-web-admin.service` (`next start -p 4002`). All
> run as `camxora` from `/opt/camxora/repo`, `Restart=always` + `RestartSec=5` (crash
> recovery) and `WantedBy=multi-user.target` (boot autostart). The core unit sets
> `TimeoutStopSec=45` so systemd's `SIGTERM` lets `src/serve.ts` drain in-flight job workers
> (its own 35 s forced-exit guard) before `SIGKILL`; frontends bind `127.0.0.1` only (nginx
> fronts them — task 4.2). Idempotent installer
> `scripts/deploy/systemd/install_musicapi_services.sh` copies the units into
> `/etc/systemd/system` and runs `systemctl enable --now` (build/deploy of the tree is task
> 4.4). Verified locally: `npm run build` in `musicapi` emits `dist/serve.js` (the core
> `ExecStart` target). Reboot drill lands with the sandbox deploy (Phase-4 gate).
>
> **Note (4.2):** nginx terminates TLS for **three musicapi vhosts** (chose our own
> subdomains rather than reusing the platform's `app`/`admin`, since the core's own docs
> already advertise `https://musicapi.camxora.com`):
> `musicapi.<env>` → core API `127.0.0.1:4003`, `app.musicapi.<env>` → web-user `:4001`,
> `admin.musicapi.<env>` → web-admin `:4002` (sandbox `*.sandbox.camxora.com`, production
> bare). Versioned pair `scripts/deploy/nginx-musicapi-{sandbox,production}.conf` with one
> shared Let's Encrypt cert per env (`/etc/letsencrypt/live/musicapi.<env>/`) and a port-80
> → 443 redirect. Key decisions: (a) `proxy_read_timeout/proxy_send_timeout 600s` on every
> core-API location, because the core's Fastify `requestTimeout` is 600 s — copying the
> platform's 300 s would 504 the browser while the upstream still succeeded (the incident
> class in `DEPLOYMENT_OPERATIONS.md` §5); (b) a same-origin `/backend/` location on the two
> frontend vhosts (`proxy_pass http://127.0.0.1:4003/`, trailing slash strips the prefix) so
> the browser's relative `/backend/*` calls keep the `sunosession` cookie first-party; (c) a
> dedicated `location /me/download` forwarding `Range` + `proxy_buffering off` for large
> MP3/WAV streams; (d) no Cloudflare headers — nginx is the only edge. `trustProxy` aligned
> by documenting `TRUST_PROXY=127.0.0.1` in `musicapi/.env.example` (`trustProxyOption()` in
> `src/server.ts` reads it; it feeds `requireKey`'s `ip_whitelist.includes(req.ip)`, and
> defaults off so a directly reachable server can't be spoofed). Applier
> `scripts/deploy/apply_musicapi_nginx.py --env <sandbox|production>` mirrors `apply_nginx.py`
> (upload → `ln -sf` → `nginx -t` → `systemctl reload nginx` → `NGINX_APPLIED_<ENV>`), with an
> optional `--issue-cert` that stands up a temporary :80 block, runs the three-name
> `certbot --nginx … --expand --non-interactive --redirect`, then applies. Sandbox apply +
> smoke ride with the Phase-4 gate / task 4.4 deploy scripts.
>
> **Note (4.3):** edge hardening in `src/server.ts`, all three plugins registered in
> `buildServer()` **before any route** (`@fastify/cors`/`@fastify/rate-limit` attach
> per-route hooks at registration time, so routes declared earlier would silently miss
> them — that is why `buildServer` is now `async` and `src/serve.ts` awaits it).
> (a) **CORS** uses a `delegator(req, cb)`: public `/v1/*` and `/api/v1/*` get
> `origin: '*'` with **no** credentials (Bearer-key auth, never cookies), while the
> cookie-session routes reflect only `FRONTEND_ORIGINS` + the new `API_CORS_ORIGINS`
> with `credentials: true` — a hostile page can't ride a `sunosession`. The panels
> actually reach the API same-origin via the nginx `/backend` proxy, so the allowlist
> is defense-in-depth. (b) **helmet** with `contentSecurityPolicy: false` (JSON API,
> no HTML documents to protect) and `crossOriginResourcePolicy: cross-origin` so the
> public API stays readable from any origin. (c) **rate limiting** in-memory, keyed on
> `req.ip` (real client IP only when `TRUST_PROXY` trusts nginx — task 4.2), global
> `RATE_LIMIT_MAX`/`RATE_LIMIT_WINDOW_MS` (default 300/min) plus a stricter
> `RATE_LIMIT_AUTH_MAX` (default 10) on `/auth/login` + `/auth/register`; no DB writes
> per request (per-user credits/quotas stay Phase 5). (d) **structured logging**: the
> pino logger that was `logger: false` is now enabled (`LOG_LEVEL`, JSON, request ids,
> redacting `authorization`/`cookie`/`set-cookie`); boot/shutdown `console.*` lines are
> unchanged. (e) **`GET /metrics`** returns an admin-guarded JSON snapshot — uptime,
> request/error counters (in-memory, from an `onResponse` hook), jobs by status,
> account-pool size — since this deployment has no Prometheus/scrape stack. Verified at
> runtime against the local Postgres via `app.inject()`: `/v1` → `ACAO: *`;
> disallowed origin → no `ACAO`; `http://localhost:4001` → reflected origin +
> `Allow-Credentials: true`; helmet headers present with no CSP / no `X-Powered-By`;
> 11th `/auth/login` → `429` with `Retry-After: 60`; `/metrics` → `401` anon,
> `403` non-admin, `200` JSON for admin; plus `npm run typecheck` + `npm run build`
> clean.
>
> **Note (4.4):** sandbox-first deploy chain, mirroring the platform's `deploy.py`
> conventions (env-split secrets, ed25519 key bootstrap, SFTP upload + sentinel
> verify). Root cause of the CRLF failure below was repo hygiene, not the units:
> `core.autocrlf=true` with **no** `.gitattributes` meant the committed blobs were
> already LF (`git ls-files --eol` → `i/lf`) but every Windows **checkout** rewrote
> them to CRLF, and the deploy tars the *working tree* — so the damage came back on
> each checkout. A root `.gitattributes` now pins `*.sh`/`*.service`/`*.conf`/`*.timer`
> to `eol=lf` — extension-scoped rather than a `scripts/deploy/**` glob, which also
> matched a binary `.csv` artifact and made Git report it modified on every checkout —
> with Windows-only `*.bat`/`*.cmd`/`*.ps1` left CRLF, so the checkout is LF regardless
> of `autocrlf`.
> `scripts/deploy/sync_musicapi_sandbox.py` tars `musicapi/` + `scripts/deploy/`,
> uploads it and runs `scripts/deploy/camxora-musicapi-remote.sh` over SSH;
> `scripts/deploy/deploy_musicapi_production.py` is the same driver guarded by a
> mandatory `--yes`. The remote installer is env-driven (`MUSICAPI_ENV`,
> `MUSICAPI_DOMAIN` = `sandbox.camxora.com` / `camxora.com`) so sandbox and production
> share one script: apt/Node 20, `camxora` user, Postgres role `musicapi` + DB
> `sunoapi`, then extract, `.env` (mode 600), core `npm ci || npm install` + `tsc`
> build, migrations, both Next builds, `install_musicapi_services.sh`, nginx, health
> checks. Generated `MUSICAPI_DB_PASSWORD` / `JWT_SECRET` /
> `COOKIE_ENCRYPTION_KEY` are persisted to `/opt/camxora/.deploy-secrets` (merging,
> not clobbering, the platform's keys) so JWT sessions and encrypted Suno cookies
> survive redeploys. Two fixes were required to make the first deploy actually boot:
> (a) the 4.1 systemd units + installer shipped with **CRLF** line endings, which
> Linux `bash` rejects (`set: pipefail: invalid option name`) — normalised to LF,
> matching the repo's LF remote scripts (`camxora-sandbox-remote.sh`); (b)
> `src/serve.ts` crashed on boot (`ENOENT: accounts.json`) on a fresh DB with no
> `suno_accounts` rows, so the JSON fallback is now guarded by `existsSync` and the
> server starts with an empty pool (generation returns "No Suno accounts configured."
> until an account is seeded). Verified on the sandbox: `MUSICAPI_SANDBOX_DEPLOYED`,
> `npm run build` + `scripts/migrate.ts` clean, `/health` → `{"ok":true,"accounts":0,"jobs":0}`,
> web-user `200` / web-admin `307`, all three units `enabled` (reboot-safe),
> `/metrics` → `401` anon, helmet headers present, `x-ratelimit-limit: 300` global /
> `10` on `/auth/login`, `/v1/*` preflight → `204` + `ACAO: *` while `/auth/*`
> reflects only the allowlisted origin with `Allow-Credentials: true`. The HTTPS
> vhost is skipped until `A` records for `musicapi|app.musicapi|admin.musicapi.sandbox.camxora.com`
> exist (still `NXDOMAIN`); re-run with `--issue-cert` to bootstrap Let's Encrypt.
> Production was **not** touched.

> **Note (4.5):** extended the repo's single workflow (`.github/workflows/pr-checks.yml`,
> `on: pull_request` → `main`/`master`) with **two path-gated jobs** that only run when
> `musicapi/` changed (`git diff --name-only "$BASE"...HEAD -- musicapi/`, same convention
> as the existing `admin-portal-build` job). `musicapi-checks` does `npm ci` + `npm run
> typecheck` + `npm run build` for `musicapi`, `web-user` and `web-admin` (node 20, `cache:
> npm`, three lockfiles in `cache-dependency-path`); `musicapi-smoke` boots the API against
> a throwaway `postgres:16` service container, applies `scripts/migrate.ts`, then asserts
> `/health` → `{"ok":true,...}`, `/metrics` → **401** (admin-only) and `POST /auth/register`
> → **405** (self-registration disabled), tearing the server down via a trap.
> `src/config.ts` throws at import unless `JWT_SECRET` (≥32 chars) and
> `COOKIE_ENCRYPTION_KEY` (64 hex) are set — and `scripts/migrate.ts` imports it too — so
> both are provided as job-level env (throwaway CI values).
> Two frontend lockfiles had to be regenerated to make `npm ci` usable as the gate: both
> `web-user` and `web-admin` `package-lock.json` were internally inconsistent (npm
> reported `Invalid: lock file's @emnapi/wasi-threads@1.2.1 does not satisfy …` / `Missing:
> @emnapi/core…`) — a known npm optional-dependency lockfile bug, previously masked because
> the remote deploy uses `npm ci || npm install`. Regenerated with **npm 10** (the version CI
> pins via node 20) rather than the local npm 11, then verified `npx npm@10 ci` is clean for
> all three packages and `typecheck` + `build` pass for all three. No push — the workflow
> only takes effect on PRs into `main`/`master`.

> **Note (4.6):** added backups + monitoring without inventing a new alert channel.
> `scripts/deploy/musicapi-backup.sh` does a nightly `pg_dump --format=custom --compress=6
> --no-owner --no-privileges` into `/opt/camxora/backups/musicapi/` (overridable via
> `MUSICAPI_BACKUP_DIR`), verifies the archive with `pg_restore --list`, and prunes
> snapshots older than `MUSICAPI_BACKUP_RETENTION_DAYS` (default **14**). It resolves
> `DATABASE_URL` from `musicapi/.env` when not exported. Driven by
> `camxora-musicapi-backup.{service,timer}` (`OnCalendar=*-*-* 03:30:00`, `Persistent=true`,
> `RandomizedDelaySec=300`).
> `scripts/deploy/musicapi-healthcheck.sh` probes `http://127.0.0.1:${PORT:-4003}/health`
> and `systemctl is-active` for the three services, then **alerts only on state change**
> (healthy→down and the recovery) using `/opt/camxora/.musicapi-health.state` so a long
> outage pages once. `camxora-musicapi-healthcheck.{service,timer}` run it every 5 min
> (`OnCalendar=*:0/5`).
> The Telegram channel is **reused from the platform ops bot** rather than a new one:
> dedicated `MUSICAPI_ALERT_TELEGRAM_BOT_TOKEN`/`_CHAT_ID` win if set, otherwise
> `sync_musicapi_sandbox.py` forwards the existing `TELEGRAM_*`/`PLATFORM_TELEGRAM_*`;
> the remote installer writes `ALERT_TELEGRAM_*` into `musicapi/.env` and the probe also
> falls back to `platform_api/.env`. `install_musicapi_services.sh` gained the four units
> (services `enable --now`, timers `enable --now`); the remote installer creates the backup
> dir, runs one backup + one probe immediately, and lists timers/snapshots in its health tail.
> **Verified on the sandbox** via `sync_musicapi_sandbox.py` (`MUSICAPI_SANDBOX_DEPLOYED`):
> both timers listed, first snapshot `sunoapi-20260929T063322Z.dump` (26K, `camxora:camxora`),
> `/health` → `{"ok":true,...}`. **Restore drill** — `pg_restore --exit-on-error` of the latest
> snapshot into a scratch `sunoapi_restore_check` DB exited `0` with **13** app tables
> (users, jobs, api_keys, suno_accounts, credit_packs, credit_transactions, payment_transactions,
> pricing, rate_limits, routing_rules, usage_logs, blog_posts, schema_migrations), then the
> scratch DB was dropped. **Alert drill** — `PORT=1` forced `down` (Telegram "UNHEALTHY"
> delivered) and the next real probe reported `ok` ("RECOVERED" delivered). Production was
> **not** touched.

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
