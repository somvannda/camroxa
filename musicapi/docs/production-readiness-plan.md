# musicapi — Production Go-Live Plan

> Scope: the deployable surfaces **inside `musicapi/` only** — Core API (`src/`), `web-user`, `web-admin`, PostgreSQL `sunoapi`, and ops/deploy.
> Rules: one task → one branch; commit per task; sandbox before production (`.cursor/rules/sandbox-first-deploy.mdc`).

Legend: `[ ]` pending · `[~]` in progress · `[x]` done

> Last verified: 2026-09-28 — Phase 0 and 1.1–1.2 confirmed in code on `musicapi`
> (working tree matches the `feat/musicapi-baseline` tip).

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
| 1.3 | Enforce `charge()` on all `/me/*`; atomic select+charge | `fix/musicapi-charge-race` | no free jobs under concurrency ✅ (8× concurrent → 1 job, credits ≥ 0, 1 ledger row) | `[x]` |
| 1.4 | Atomic KHQR confirm + admin top-up | `fix/musicapi-payment-atomic` | double-poll credits once ✅ (8× concurrent settle → 1 credit, 1 ledger row; admin 8×+10 no lost update) | `[x]` |
| 1.5 | Callback URL allowlist (block SSRF/private ranges) | `fix/musicapi-callback-ssrf` | external URL rejected ✅ (14/14 cases) | `[x]` |
| 1.6 | Encrypt Suno `client_cookie` at rest | `feat/musicapi-cookie-encryption` | DB ciphertext; pool works ✅ (`enc:v1`, resilient per-row decrypt) | `[x]` |
| 1.7 | OAuth per-request client, signed `state`, verified email | `fix/musicapi-oauth-hardening` | CSRF blocked; flow works ✅ (signed+expiring state; redirect_uri from state; forged/expired/non-allowlisted rejected; `email_verified` enforced) | `[x]` |
| 1.8 | Rotate leaked secrets; scrub `.env`/`accounts.json` | ops (user-led) | old creds invalid | `[ ]` |

**Gate:** no free-credit or forgeable-token path; secrets safe.
> Note: 1.1–1.2 landed as commits on `feat/musicapi-baseline` (Phase 0's branch) instead of their own branches. 1.3, 1.4, 1.5, 1.6, 1.7 done; 1.8 remains (ops/user-led secret rotation).

---

## Phase 2 — Durability & correctness

| # | Task | Branch | Verification | Status |
|---|---|---|---|---|
| 2.1 | Persist jobs (Postgres or Redis/BullMQ); recover on restart | `feat/musicapi-job-persistence` | restart mid-job resolves ✅ (`jobs` table + boot recovery) | `[x]` |
| 2.2 | `.catch()` detached workers + `unhandledRejection`/`SIGTERM` | `fix/musicapi-worker-safety` | graceful drain ✅ (detached workers never reject; close waits for in-flight job — 810ms for an 800ms worker — bounded by `SHUTDOWN_DRAIN_MS`; failing worker ends job `error` with 0 unhandled rejections) | `[x]` |
| 2.3 | Refund on terminal failure; `spend`/`refund` ledger rows | `feat/musicapi-refunds-ledger` | failed job restores credit ✅ (refund ledger nets out) | `[x]` |
| 2.4 | TTL/LRU eviction for job map | `chore/musicapi-job-eviction` | memory bounded ✅ (TTL reaps finished jobs; size cap holds at cap+1; live jobs never evicted) | `[x]` |
| 2.5 | `trustProxy` so IP whitelist sees real client IP | `fix/musicapi-trust-proxy` | whitelist enforced (spoofed XFF rejected when off; honored when on) | `[x]` |
| 2.6 | Ordered idempotent migration runner | `feat/musicapi-migrations` | fresh + existing DB migrate ✅ `migrations/0001–0021` + `schema_migrations` + advisory lock | `[x]` |
| 2.7 | Missing indexes (`usage_logs.api_key_id`, `credit_transactions.user_id`) | `perf/musicapi-indexes` | `EXPLAIN` uses index ✅ (`idx_usage_logs_api_key` added; `idx_credit_transactions_user` now in schema.sql — was live-DB drift) | `[x]` |

**Gate:** restart-safe; no lost/refunded-money bugs; clean migrations.

> **Note (2.6):** replaced the ad-hoc `scripts/migrate.ts` (which `readFileSync("scripts/schema.sql")`) with an ordered, tracked, idempotent runner. Migration SQL now lives in `migrations/0001_init.sql` … `0020_champapay_gateway.sql`, folding in the deleted `scripts/schema.sql` and the ad-hoc `migrate-*` scripts (including `scripts/migrate-champapay.ts`). The runner applies each file **in filename order**, records it in `schema_migrations (version TEXT PK, applied_at)`, and applies the file together with its bookkeeping row **in one transaction** — a failure rolls the whole file back and leaves the DB untouched. A session-level `pg_advisory_lock(4172001)` stops two runners from racing. `MIGRATIONS_DIR` is resolved relative to the script (not the CWD). All SQL is written `IF NOT EXISTS`/guarded so a pre-existing DB is adopted safely. New `.sql` files are caught by the repo-wide `*.sql` ignore (intended for DB dumps), so a `!migrations/*.sql` negation was added to `musicapi/.gitignore`.
>
> **Verification:** `npm run typecheck` clean. Existing `sunoapi` DB → adopted (`0020` applied as a no-op, 19 already up to date), immediate re-run → `0 applied`; fresh throwaway DB → all 20 applied, re-run → `0 applied`.
>
> **Drift reconciled (fresh-vs-live diff):** the legacy local DB diverged from the migration set in two places. (1) `payment_transactions.gateway_payment_id` / `webhook_event_id` + `idx_payment_tx_gateway` existed **only** in the live DB (added by the ad-hoc `scripts/migrate-champapay.ts`), yet `src/server.ts`'s ChmabaPay flow requires them (`INSERT … gateway_payment_id`, `SELECT … WHERE gateway_payment_id`, `SET webhook_event_id`) — a fresh DB would have broken payments. Captured as `0020_champapay_gateway.sql`; the ad-hoc script is deleted. (2) `app_settings.value` is `text` on the legacy DB but `jsonb` + `updated_by` in `0010` — inert at the time, since nothing under `musicapi/` read or wrote `app_settings` (dormant table), so it was left unchanged; **since reconciled by `0021_app_settings_reconcile.sql`** when §4.10 activated the table (see the §4.10 entry). The legacy DB also carries an unused nullable `external_id` column and inert `payment_method`/`provider` defaults (`'chmaba'` vs `'khqr'`/`'bakong'`) — both unused by the app (every payment insert passes `payment_method` explicitly and nothing reads `provider`).

---

## Phase 3 — Frontend production readiness

| # | Task | Branch | Verification | Status |
|---|---|---|---|---|
| 3.1 | Env-driven backend URL (both apps) | `fix/musicapi-fe-backend-url` | prod host via env ✅ `BACKEND_URL` baked into both rewrites | `[x]` |
| 3.2 | Real session (httpOnly cookie or documented token + 401 logout) | `feat/musicapi-session` | expired → `/login` ✅ `sunosession` httpOnly cookie + CSRF | `[x]` |
| 3.3 | web-admin server-side guard (`middleware.ts` + role check) | `feat/musicapi-admin-guard` | non-admin blocked ✅ cookie → `/auth/me` → `/login` | `[x]` |
| 3.4 | web-user authenticated downloads (blob) | `fix/musicapi-fe-downloads` | downloads 200 ✅ authenticated blob (401 → `/login`) | `[x]` |
| 3.5 | Remove fake dashboard chart → real usage data | `fix/musicapi-fe-dashboard` | no fake data ✅ fabricated `Math.random()` chart removed | `[x]` |
| 3.6 | Delete dead `/app/*` tree + unused components/deps | `chore/musicapi-fe-cleanup` | routes still work ✅ no `/app/*`, 21 routes build | `[x]` |
| 3.7 | Fix admin pricing edit (track `editingId`, PUT) | `fix/musicapi-admin-pricing-edit` | update, no duplicate ✅ `PUT /admin/pricing/:id` | `[x]` |
| 3.8 | Admin `/auth/callback`; align redirect URIs | `feat/musicapi-admin-oauth` | Google admin login | `[x]` |
| 3.9 | Wire/hide placeholders; mark stubs "coming soon" | `chore/musicapi-fe-placeholders` | no dead UI | `[x]` |

**Gate:** both apps build against prod env; no spoofable auth; no fake data.

> **Note (3.1):** the functional switch already landed in Phase 0.5 — both Next apps rewrite `/backend/:path*` to `process.env.BACKEND_URL` (falling back to `http://localhost:4003` when unset) and the browser only ever calls the relative `/backend` path, so no host is hardcoded client-side. This task closes the deploy contract: each app now ships its own `.env.example` documenting `BACKEND_URL` (with a `!.env.example` negation in each app's `.gitignore`, since the templates ignore `.env*`). Env is read at **build** time by `next.config.ts` `rewrites()`. Verified by building both apps with `BACKEND_URL=https://api.camxora.example` and reading `.next/routes-manifest.json` — the rewrite `destination` is `https://api.camxora.example/:path*` for **both** `web-user` and `web-admin`; rebuilding without the var restores `http://localhost:4003/:path*`.
>
> **Note (3.2):** browser sessions moved off `localStorage` to an **httpOnly cookie**.
> The API (`src/appAuth.ts`) now emits `Set-Cookie: sunosession=<JWT>; Path=/; HttpOnly;
> SameSite=Lax; Max-Age=604800` (`Secure` when `SESSION_COOKIE_SECURE=true`, which
> defaults to on in production) from `POST /auth/login` and `POST /auth/google/callback`,
> and `POST /auth/logout` clears it (`Max-Age=0`). `requireAuth` reads the cookie first
> and still accepts `Authorization: Bearer` as a fallback, so non-browser/API-key callers
> are unaffected. Because the cookie is sent automatically, cookie-authenticated requests
> get a defense-in-depth **CSRF Origin check** on top of `SameSite=Lax`: an `Origin` that
> isn't in `FRONTEND_ORIGINS` (comma-separated, defaults to the two local dev frontends
> `http://localhost:4001,http://localhost:4002`) is rejected `403`; same-origin/missing-Origin
> requests pass. The check runs **regardless of HTTP method** (not just unsafe methods) so it
> also guards state-changing work reachable over GET such as the credit-spending
> `/me/download` routes. Route handlers still return `{ token, user }`, so the documented
> token flow remains valid for API clients.
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
> **Verification:** `npm run typecheck` clean; `next build` passes for both apps. Runtime
> smoke test against a live API (`SESSION_COOKIE_SECURE=false`): `POST /auth/login`
> → `200` + `Set-Cookie: sunosession=…; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800`
> (no `Secure`, as expected for the local override); `GET /auth/me` with that cookie and
> allowed `Origin: http://localhost:4002` → `200`; the same cookie with
> `Origin: http://evil.com` → `403 {"error":"Cross-origin request blocked."}`;
> `POST /auth/logout` → `Set-Cookie: sunosession=; …; Max-Age=0`.
>
> **Note (3.3):** web-admin access control is now **server-side**. The old guard was a
> client component (`app/admin/layout.tsx` + `app/page.tsx` calling `getUser()` and
> `router.replace`) reading a `localStorage` profile that any visitor could spoof — it
> blocked nobody who opened devtools. Replaced by `web-admin/proxy.ts` (Next.js **16**
> renamed the `middleware.ts` file convention to `proxy.ts` and the exported function from
> `middleware` to `proxy`; a stale `middleware.ts` would still typecheck but is **never
> executed** at runtime, so following the old convention here would have been a silent
> hole — this worktree had no `middleware.ts`, so none needed removing). For `/` and
> `/admin/:path*` the guard reads the httpOnly `sunosession` cookie, forwards it to the
> API's `GET /auth/me`, and only calls `NextResponse.next()` when the response is OK and
> `role === "admin"` **and** `status === "active"`; every other outcome (missing cookie,
> non-2xx, backend unreachable, wrong role, suspended) redirects to `/login`. A rejected
> session also clears the dead cookie (`Expires=1970`) so the login page starts clean; a
> backend that's down is treated as **fail-closed** (redirect, cookie kept). The API stays
> the authority — every `/admin/*` route still calls `requireAdmin` — and `JWT_SECRET`
> never leaves the API. The `admin` layout and root page became server components that
> only handle chrome / `redirect("/admin")`. `.env.example` documents that the guard calls
> `${BACKEND_URL}/auth/me` (same value the `/backend/*` rewrite uses, read at build time).
>
> **Verification:** `npm run typecheck` clean; `npm run build` passes with
> `ƒ Proxy (Middleware)`. Runtime matrix against a stub `/auth/me` (port 4103, web-admin on
> 4102): no cookie → `307 /login`; `role=user` → `307 /login` + cookie cleared;
> `role=admin, status=suspended` → `307 /login` + cookie cleared; unknown/invalid session
> (`401`) → `307 /login` + cookie cleared; `role=admin, status=active` → `200` on `/admin`;
> `/` + active admin → `307 /admin`; stub stopped (backend down) + admin cookie → `307
> `/login` (fail-closed, cookie kept).
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
> can't creep back; a leftover **unused** `clipDownloadUrl` import in
> `app/dashboard/logs/page.tsx` (which already used `downloadClip`) was dropped too.
> Verified: `npm run typecheck` clean and `npm run build` succeeds; the underlying
> `GET /me/download` (MP3/WAV → HTTP 200 real audio bytes) is already verified in
> `ENDPOINT_STATUS.md` rows 1.15–1.16.
>
> **Note (3.5):** the dashboard's "Real-time Success Rate" line chart was **entirely
> fabricated** — every one of its 14 points came from `Math.random()` (`85 + rand*15`), with
> an invented per-minute X axis derived from `new Date()` and a meaningless `success_24h`
> conditional. It looked like live telemetry but was pure noise, the exact "no fake data"
> violation the gate checks. The chart and its supporting code (`successRateSeries`,
> `maxMin`, `timeStr`, the `new Date()` clock, and the now-unused optional `success`/`failed`
> fields on the `Usage.series` interface) were removed from
> `app/dashboard/page.tsx`, leaving the dashboard with only API-backed visuals: the real
> `Last 24 Hours` success/failure/other card, the real remaining-credits card, and the real
> daily usage bar chart driven by `series` from `GET /me/usage`. Verified: `Math.random`
> no longer appears anywhere in `web-user`; `npm run typecheck` clean and `npm run build`
> succeeds.
>
> **Note (3.6):** `web-user` carried a **dead legacy route tree** at `app/app/*`
> (`api-keys`, `billing`, `playground`, `updates`, `usage`, `logs`, `layout.tsx`, `page.tsx`)
> — a duplicate of the real `app/dashboard/*` app. Its `layout.tsx` was only a client
> redirect stub (`/app/* → /dashboard/*`), so the tree was pure dead weight served at
> duplicate URLs. Also removed: `components/Sidebar.tsx` (a stale duplicate of the
> dashboard's inline sidebar, importing the old `clearSession` flow and linked to `/app`
> routes, imported nowhere) and `components/ComingSoon.tsx` (no usages). Repointed the
> remaining live redirect targets from `/app` to `/dashboard`: `components/auth-modal.tsx`
> (`redirectTo` + `onSuccess`), `components/google-signin-button.tsx` (`redirectTo` default),
> and `app/auth/callback/page.tsx` (post-OAuth fallback). **Deviation from the reference
> worktree:** that tree also deleted `qrcode.react` as unused — here it is **kept**, because
> this worktree's `app/dashboard/billing/page.tsx` is a newer KHQR checkout that renders the
> payment QR with `QRCodeSVG`. No other unused deps. Verified: `npm run typecheck` clean and
> `npm run build` succeeds — 21 static pages, all `/dashboard/*` routes present and **no
> `/app/*` route remains** (a stale `.next` had cached `validator.ts` entries for the deleted
> routes, cleared before the clean run).
>
> **Note (3.7):** the admin pricing page's **Edit** button only pre-filled the form — it
> never remembered *which* row was being edited. On save the page always `POST`ed to
> `/admin/pricing`, whose upsert matches on `(endpoint, model)`. Editing a row's
> `endpoint`/`model` therefore inserted a **new** row and left the old one behind (a
> duplicate); the `pricing` table has no DB-level uniqueness to catch it. Fixed by tracking
> `editingId` in the form state (`web-admin/app/admin/pricing/page.tsx`), wiring
> Edit/Cancel/toggle to set/clear it, and routing updates to a new `PUT /admin/pricing/:id`
> endpoint (`src/server.ts`) that updates `endpoint`, `model`, and `credit_cost` by id (404
> when missing) and deletes any other row that would now collide on `(endpoint, model)` so
> `costFor` has a single source of truth. New prices still use `POST`. **Deviation from the
> reference worktree:** that `PUT` (and the sibling's `POST`) also writes an audit record via
> `recordAudit` — this worktree's `server.ts` has no audit-log helper, and adding one is
> out of scope for 3.7, so the route matches the existing local route style (no audit).
> Verified: `tsc --noEmit` clean for core + `web-admin`; `next build` succeeds (13/13 static
> pages, `/admin/pricing` present).
>
> **Note (3.8):** the core API already allowlisted **both** Google redirect URIs
> (`GOOGLE_REDIRECT_URI_USER` → `…:4001/auth/callback`,
> `GOOGLE_REDIRECT_URI_ADMIN` → `…:4002/auth/callback` in `src/server.ts`) and
> `GET /auth/google/url` accepts a `redirect_uri` + returns a signed `state`, but
> `web-admin` had **no client for it**: no `/auth/callback` route and no Google button, so
> the admin redirect URI was dead and admins could only sign in with email/password.
> Added `web-admin/components/google-signin-button.tsx` (uses
> `window.location.origin/auth/callback`, falls back to `http://localhost:4002/auth/callback`
> to match the API allowlist; default post-login `redirectTo` `/admin`; persists the intended
> destination under `google_auth_redirect`) and `web-admin/app/auth/callback/page.tsx`
> (Suspense-wrapped, single-exchange `started` ref guard against StrictMode double-run,
> role-gated: a non-admin Google account is told "This area is for administrators only."
> instead of being bounced by the proxy). The `/login` page gained an "or" divider + the
> Google button under the email/password form. `/auth/callback` is intentionally **not** in
> `proxy.ts`'s matcher (`/`, `/admin/:path*`) — it must render before a session exists.
> **Deviation from the reference worktree:** the sibling also stashes `google_auth_state` as a
> query-param fallback; this worktree's user-side callback does not use it, so the admin copy
> matches the local convention and relies on the `state` query param Google echoes back.
> Verified: `tsc --noEmit` clean for `web-admin`; `next build` succeeds with `/auth/callback`
> present (14/14 static pages).
>
> **Note (3.9):** audited both apps for dead/inert UI. **Inert controls removed:** the
> dashboard shell (`web-user/app/dashboard/layout.tsx`) had a non-wired `…` "more" button in
> the sidebar header, a do-nothing `English` language row (only one language today), and two
> placeholder support links — `https://discord.gg/yourinvite` and `https://t.me/yourchannel`
> — whose invite URLs don't exist, so they're hidden rather than shipping a fake destination.
> The admin `Sidebar`'s bottom `Settings` **button** (a duplicate of the real
> `/admin/settings` NAV link that did nothing) was also removed. **Placeholder email wired:**
> the landing page's `mailto:support@yourdomain.com` (×2 in `web-user/app/page.tsx`) now
> points at `support@camxora.com`. **Stubs marked:** `web-admin/app/admin/{analytics,settings}`
> still render the shared `ComingSoon` component; its copy changed from "This section is under
> construction." to "This section is coming soon." **Deviation from the reference worktree:**
> the sibling removed the `Logs` nav items from both sidebars because those routes don't exist
> there; in this worktree **both routes exist and are real, wired pages**
> (`web-user/app/dashboard/logs/page.tsx` = live job/log table; `web-admin/app/admin/logs/page.tsx`
> = `/admin/logs` request table), so both nav items were **kept**. The `server.ts` comment
> showing `app.yourdomain.com`/`admin.yourdomain.com` was left as-is — it's an example of the
> prod redirect-URI values to register, not user-facing copy. Verified: `npm run typecheck`
> clean in `web-user` + `web-admin`; `npm run build` clean in both (web-user 21/21,
> web-admin 14/14 static pages) with both `logs` routes still present.

---

## Phase 4 — Ops & deployment

| # | Task | Branch | Verification | Status |
|---|---|---|---|---|
| 4.1 | Process management (PM2/systemd/Docker) | `ops/musicapi-process` | survives reboot | `[x]` systemd units + boot enable ✅ |
| 4.2 | nginx vhosts + TLS + `/backend` proxy; align `trustProxy` | `ops/musicapi-nginx` | HTTPS, real IPs | `[x]` nginx vhosts + `TRUST_PROXY` ✅ |
| 4.3 | CORS/helmet + rate limiting + structured logging + `/metrics` | `feat/musicapi-edge-hardening` | public `/v1` safe | `[x]` helmet + CORS + rate limit + pino logs + `/metrics` ✅ |
| 4.4 | Deploy scripts: `sync_musicapi_sandbox.py`, `deploy_musicapi_production.py` | `ops/musicapi-deploy-scripts` | sandbox deploy works | `[x]` deploy scripts + `.gitattributes` ✅ |
| 4.5 | CI: typecheck + build + smoke gate | `ops/musicapi-ci` | PR blocked on failure | `[x]` `musicapi-checks` + `musicapi-smoke` ✅ |
| 4.6 | DB backups + monitoring/alerts | `ops/musicapi-observability` | restore drill; alerts fire | `[x]` nightly `pg_dump` + 5-min health probe + Telegram alerts ✅ |

**Gate:** deployed + smoked on **sandbox**; production only on explicit ask.

> **Gate result (2026-10-01) — sandbox deploy + smoke ✅.** The three hostnames
> (`musicapi`/`app.musicapi`/`admin.musicapi.sandbox.camxora.com`) are **DNS-only (grey cloud)**
> `A` records → `46.250.235.83`; Cloudflare proxying is deliberately **off** because the vhosts
> use the origin IP model (`TRUST_PROXY=127.0.0.1`, no `CF-Connecting-IP`), and orange-cloud
> would also break the certbot HTTP-01 challenge. `sync_musicapi_sandbox.py --issue-cert`
> uploaded the tarball, built the core (`tsc`), applied migrations
> (`[migrate] done: 10 applied, 10 already up to date.`), installed all seven units and
> enabled the two timers; sentinel `MUSICAPI_SANDBOX_DEPLOYED`. TLS is a single Let's Encrypt
> cert (`issuer CN=YR1, O=Let's Encrypt`) with SAN covering all three names, `notAfter`
> 2026-12-30; `ssl_verify_result=0` on all three. Smoke from off-host, over the public
> hostnames: `/health` → `{"ok":true,...}`; `/metrics` → **401**; `POST /auth/register` →
> **405**; port-80 → **301** → https; `app.musicapi…/` → **200** and its `/backend/health` →
> `{"ok":true,...}` (same-origin proxy works); `admin.musicapi…/` → **307 → `/login`** (the
> web-admin auth guard) and `/login` → **200**; backup dir lists the first `.dump` snapshot.

> **Caveat — certbot lock collision.** The first `--issue-cert` run **skipped HTTPS** because
> the pre-existing `certbot.timer` was mid `certbot -q renew`, holding
> `/var/lib/letsencrypt/.certbot.lock` (`Another instance of Certbot is already running.`); the
> cert + vhost were then applied by hand. The remote script's TLS bootstrap already tolerates
> this (`|| log WARN` + the `if [[ -f "${CERT}" ]]` re-check), but a fresh deploy that lands
> during a renew silently ends up HTTP-only until re-run — worth serialising against the
> timer (or retrying) in a future pass.

> **Verification drills (2026-10-01) — all three green ✅.** (1) **Reboot drill:** `systemctl
> reboot` on the sandbox; the host came back in ~75 s, `boot_id` changed, and all three
> services + both timers auto-started (`enabled`; the two oneshot `.service` units are
> `static`, pulled by their timers). Post-reboot, off-host: `/health` ok, `app` 200, `admin`
> 307→`/login`, `/metrics` 401, port-80 → 301. (2) **Restore drill:** `pg_restore
> --exit-on-error` of the latest snapshot (`sunoapi-20261001T104903Z.dump`) into a scratch
> `sunoapi_restore_check` DB returned 0 with **16** `public` tables (all app tables), then the
> scratch DB was dropped. (3) **Alert drill:** `PORT=1 musicapi-healthcheck.sh` flipped the
> state file `ok → down`, exited 1 and **delivered a real Telegram `UNHEALTHY`**; the normal
> run flipped `down → ok` and delivered `RECOVERED` — so the reuse of the platform ops bot
> works end-to-end. Note: the reboot restarts the **whole VPS**, which is shared with the
> platform services.

> **Note (4.1):** chose **systemd** (matches the platform's existing `camxora-api`,
> `camxora-worker-*`, `camxora-website/portal/music` units rather than introducing PM2/Docker).
> Three versioned units under `scripts/deploy/systemd/`: `camxora-musicapi.service` (core,
> `npm run start` → `node dist/serve.js`, `PORT=4003`), `camxora-musicapi-web-user.service`
> (`next start -p 4001`) and `camxora-musicapi-web-admin.service` (`next start -p 4002`). All
> run as `camxora` from `/opt/camxora/repo`, `Restart=always` + `RestartSec=5` (crash
> recovery) and `WantedBy=multi-user.target` (boot autostart). The core unit sets
> `TimeoutStopSec=45`: on `SIGTERM`, `src/serve.ts` awaits `app.close()`, whose `onClose` hook
> drains detached in-flight job workers (bounded by `SHUTDOWN_DRAIN_MS`, default 25 s) so a
> running generation can persist its terminal state, then closes the DB pool and exits;
> systemd's 45 s `SIGKILL` is the outer backstop. Jobs still running when the drain times out
> are marked failed and refunded on the next boot by
> `recoverInterruptedJobs()`/`refundJobCredits()`. Frontends bind `127.0.0.1` only (nginx
> fronts them — task 4.2). Idempotent installer
> `scripts/deploy/systemd/install_musicapi_services.sh` copies the units into
> `/etc/systemd/system`, runs `systemctl enable` + an **unconditional `restart`** (so a
> redeploy never silently keeps the previous `dist/serve.js`), then asserts every unit is
> `active` **and** that `camxora-musicapi`'s `ActiveEnterTimestamp` does not precede the
> built `dist/serve.js` (catches the stale-code footgun). Build/deploy of the tree is task
> 4.4. Verified locally: `npm run build` in `musicapi` emits `dist/serve.js` (the core
> `ExecStart` target). As of task 4.6 the installer installs all **seven** units — the three
> long-running services plus the two backup/healthcheck `service`+`timer` pairs — enabling
> the timers with `systemctl enable --now "${TIMERS[@]}"` (see Note 4.6). **Deviations from
> the reference worktree:** (a) the reference `src/serve.ts` also arms a 35 s hard
> `process.exit` timer as an extra shutdown backstop; here the chain is the 25 s
> `SHUTDOWN_DRAIN_MS` drain plus systemd's 45 s `TimeoutStopSec`; (b) the sandbox deploy ran
> and the units are live, and the explicit **reboot drill** and **restore/alert drills** are
> now green (see the Drills note above).

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
> the browser's relative `/backend/*` calls keep the `sunosession` cookie first-party — this
> is the production replacement for the Next.js `next.config.ts` rewrite
> (`/backend/:path*` → `${BACKEND_URL}`) that the apps use in dev, and it takes precedence at
> the edge because nginx routes before the Next upstream; (c) a dedicated
> `location /me/download` forwarding `Range` + `proxy_buffering off` for large MP3/WAV
> streams; (d) no Cloudflare headers — nginx is the only edge. `trustProxy` was **already
> aligned** in this worktree (task 2.5): `resolveTrustProxy()` in `src/config.ts` feeds
> Fastify's `trustProxy`, and `musicapi/.env.example` already documents `TRUST_PROXY` as a
> comma-separated proxy-IP list, so the deployment sets `TRUST_PROXY=127.0.0.1` (nginx is the
> only hop) — it feeds `requireKey`'s `ip_whitelist.includes(req.ip)` and defaults off so a
> directly reachable server can't be spoofed. No `.env.example` change was needed for 4.2.
> Applier `scripts/deploy/apply_musicapi_nginx.py --env <sandbox|production>` mirrors
> `apply_nginx.py` (upload → `ln -sf` → `nginx -t` → `systemctl reload nginx` →
> `NGINX_APPLIED_<ENV>`), with an optional `--issue-cert` that stands up a temporary :80
> block, runs the three-name `certbot --nginx … --expand --non-interactive --redirect`, then
> applies. **Deviation from the reference worktree:** the applier resolves the target via this
> worktree's `resolve_sandbox_ssh()`/`resolve_production_ssh()` (which also refuse
> cross-environment targets) rather than reading `VPS_HOST`/`PRODUCTION_VPS_HOST` directly.
> Verified locally: `python -m py_compile` clean; the confs are byte-equivalent to the
> reference (which passed `nginx -t` on the sandbox). HTTPS issue/apply rides with the
> Phase-4 sandbox deploy (needs `A` records for the three hostnames).
>
> **Note (4.3):** edge hardening lives in `src/server.ts`. `buildServer` is now **async**
> (returns `Promise<FastifyInstance>`) so the three `@fastify/*` plugins register **before any
> route is declared** — `@fastify/cors` and `@fastify/rate-limit` attach per-route hooks at
> registration time, so routes added earlier would silently miss them; `serve.ts` now does
> `const app = await buildServer({ pool })`. Registered: **helmet** (CSP disabled — the API
> serves JSON, not HTML; `crossOriginResourcePolicy: cross-origin` so the panels can read
> media across the `app.`/`admin.` origins), **CORS** via a `delegator` that returns
> `{ origin: "*" }` for the public `/v1/` + `/api/v1/` prefixes (key-credentialed, no cookies)
> and `{ origin: [...frontendOrigins, ...apiCorsOrigins], credentials: true }` for everything
> else, and **rate-limit** (`global: true`, `RATE_LIMIT_MAX`/window) with a stricter
> `RATE_LIMIT_AUTH_MAX` budget applied per-route (`{ config: authRateLimit }`) to
> `POST /auth/login` and `POST /auth/register`. Logging switched from `logger: false` to a
> **pino** logger at `LOG_LEVEL` with `redact` on `authorization`/`cookie`/`set-cookie`.
> Added an admin-only `GET /metrics` snapshot (uptime, request counters split client/server
> errors via an `onResponse` hook, job counts by status, pool size) — guarded by `requireAdmin`.
> New `config.ts` fields: `logLevel`, `apiCorsOrigins`, `rateLimit { max, windowMs, authMax }`;
> new `.env.example` vars `API_CORS_ORIGINS`, `RATE_LIMIT_MAX`/`RATE_LIMIT_WINDOW_MS`/
> `RATE_LIMIT_AUTH_MAX`, `LOG_LEVEL`. **Deviation from the reference worktree:** this worktree's
> `server.ts` keeps `parseAs: "buffer"` + `config.trustProxy` (the reference uses
> `parseAs: "string"` + a `trustProxyOption()` helper — functionally equivalent); the
> per-user `RATE_LIMIT_PER_USER_*` limits and the alert config are **Phase-5** and were not
> ported. Verified locally: `npm run typecheck` (tsc `--noEmit`) and `npm run build` both clean.
>
> **Note (4.4):** deploy machinery mirrors the platform driver `scripts/deploy/deploy.py`
> (`load_*_secrets`, `resolve_*_ssh`, `ensure_deploy_key`/`ensure_paramiko`, `ssh_connect`,
> `tar_filter`) — no new SSH conventions. `scripts/deploy/sync_musicapi_sandbox.py` packages
> only `musicapi/` + `scripts/deploy/` (so the platform app trees are untouched), uploads the
> tarball + `camxora-musicapi-remote.sh` over SFTP, then runs the remote installer and gates on
> the `MUSICAPI_SANDBOX_DEPLOYED` sentinel. `deploy_musicapi_production.py` reuses the same
> `deploy()` and refuses to run without `--yes`. `camxora-musicapi-remote.sh` (LF-enforced)
> installs nginx/certbot/Node 20 + PostgreSQL, creates the `musicapi` role + `sunoapi` DB,
> writes `musicapi/.env` (generated secrets persisted to `/opt/camxora/.deploy-secrets` so JWT
> sessions/cookies survive redeploys), builds the core (`tsc`) and both Next apps, runs
> migrations, installs the systemd units, takes a first backup/health probe, and applies the
> env-specific nginx vhost (with optional `ISSUE_CERT=1` certbot bootstrap). **Security
> deviation from the reference worktree:** `sync_musicapi_sandbox.py` adds a
> `musicapi_tar_filter` that drops `musicapi/accounts.json` — this worktree has a real,
> cookie-bearing `accounts.json` on disk (the reference checkout does not), and it must never
> be uploaded; the server loads accounts from PostgreSQL and the new `serve.ts` `existsSync`
> guard now starts cleanly with an empty pool when the file is absent. Root `.gitattributes`
> added (`*.sh`/`*.service`/`*.conf`/`*.timer` → `text eol=lf`) so Windows `core.autocrlf`
> can't rewrite the deploy scripts/units/nginx confs to CRLF (`set: pipefail: invalid option
> name`); this also re-normalizes the pre-existing CRLF platform scripts on their next `git
> add`. The remote script also wires task 4.6: it writes the alert/backup env
> (`ALERT_TELEGRAM_*`, `BACKUP_DIR`, `BACKUP_RETENTION_DAYS`) into `musicapi/.env`, creates the
> backup dir, runs a first `camxora-musicapi-backup.service` / `-healthcheck.service` with
> `|| log WARN` guards, and lists the two timers + backup snapshots in its health tail.
> Verified locally: `python -m py_compile` clean on both scripts, `musicapi_tar_filter` drops
> `accounts.json` and keeps `src/serve.ts`, deploy `*.sh`/`*.service`/`*.conf` are CRLF-free,
> and `npm run typecheck` + `npm run build` pass after the `serve.ts` guard.

> **Note (4.5):** extended the repo's single workflow. The current worktree's
> `.github/workflows/pr-checks.yml` runs `on: pull_request` → `main`/`master` and already
> had three jobs (`changed-python-syntax`, `no-secrets-in-diff`, `admin-portal-build`); two
> **path-gated** jobs were appended **after** those, each guarded by a
> `git diff --name-only "$BASE"...HEAD -- musicapi/` check so they only run when `musicapi/`
> changed (same convention as `admin-portal-build`).
> `musicapi-checks` does `npm ci` + `npm run typecheck` + `npm run build` for the core
> (`musicapi`), `web-user` and `web-admin` (node 20, `cache: npm`, three lockfiles in
> `cache-dependency-path`); `musicapi-smoke` boots the API against a throwaway `postgres:16`
> service container, applies migrations with `scripts/migrate.ts` (the ordered runner from
> task 2.6 — it takes no path argument), then asserts `/health` → `{"ok":true,...}`, `/metrics` →
> **401** (admin-only) and `POST /auth/register` → **405** (self-registration disabled),
> tearing the server down via a trap. `src/config.ts` throws at import unless `JWT_SECRET`
> (≥32 chars) and `COOKIE_ENCRYPTION_KEY` (64 hex) are set — and `scripts/migrate.ts` imports
> it too — so both are provided as job-level env (throwaway CI values).
> Two frontend lockfiles had to be regenerated to make `npm ci` usable as the gate: both
> `web-user` and `web-admin` `package-lock.json` were internally inconsistent (npm 10
> reported `Missing: @emnapi/runtime@… / @emnapi/core@… from lock file` — the known npm
> optional-dependency lockfile bug, previously masked because the remote deploy uses `npm ci
> || npm install`). Regenerated with **npm 10** (the version CI pins via node 20) rather than
> the local npm 11 (`npx npm@10 install --package-lock-only`); the core lockfile was already
> clean. Verified: `npx npm@10 ci --dry-run` now exits 0 for all three packages, and the
> regenerated `web-user` lockfile is byte-identical to the reference worktree's around the
> key deps (`next` 16.3.4, `postcss` 8.5.23). The exact CI assertions were also reproduced
> **locally** against a real Postgres on port 4099: `/health` → `{"ok":true,"accounts":1,"jobs":0}`,
> `/metrics` → `401`, `POST /auth/register` → `405`, plus helmet headers and rate-limit
> headers (`x-ratelimit-limit: 300` global / `10` auth). No push — CI takes effect on the
> next PR into `main`/`master`.

> **Note (4.6):** added backups + monitoring without inventing a new alert channel.
> `scripts/deploy/musicapi-backup.sh` does a nightly `pg_dump --format=custom --compress=6
> --no-owner --no-privileges` into `/opt/camxora/backups/musicapi/` (overridable via
> `BACKUP_DIR`), verifies the archive with `pg_restore --list`, and prunes snapshots older
> than `BACKUP_RETENTION_DAYS` (default **14**). It resolves `DATABASE_URL` from
> `musicapi/.env` when not exported (so it also works run by hand). Driven by
> `camxora-musicapi-backup.{service,timer}` (`OnCalendar=*-*-* 03:30:00`, `Persistent=true`,
> `RandomizedDelaySec=300`).
> `scripts/deploy/musicapi-healthcheck.sh` probes `http://127.0.0.1:${PORT:-4003}/health`
> and `systemctl is-active` for the three services, then **alerts only on state change**
> (healthy→down and the recovery) using `/opt/camxora/.musicapi-health.state` so a long
> outage pages once. `camxora-musicapi-healthcheck.{service,timer}` run it every 5 min
> (`OnCalendar=*:0/5`).
> The Telegram channel is **reused from the platform ops bot** rather than a new one:
> dedicated `MUSICAPI_ALERT_TELEGRAM_BOT_TOKEN`/`_CHAT_ID` win if set, otherwise
> `sync_musicapi_sandbox.py` forwards the existing `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`
> (or `PLATFORM_TELEGRAM_*`); the remote installer writes `ALERT_TELEGRAM_*` into
> `musicapi/.env` and the probe also falls back to `platform_api/.env`.
> `install_musicapi_services.sh` gained the four units (services `enable --now` for the
> long-running set, timers `enable --now`); `camxora-musicapi-remote.sh` was already
> 4.6-aware (created in 4.4) — it creates the backup dir, starts one backup + one probe
> immediately (with `|| log WARN` guards), and lists timers/snapshots in its health tail.
> **Deploy status (updated 2026-10-01):** the sandbox deploy has since run — the remote
> installer created the backup dir, ran a first `camxora-musicapi-backup.service` +
> `camxora-musicapi-healthcheck.service` (both `|| log WARN`-guarded) and listed the two
> timers with the first `.dump` snapshot, so the units are live (see the Phase-4 gate result
> above). Reproduced here on 2026-10-01: the reference's explicit `pg_restore` drill into a
> scratch DB and its forced-`PORT=1` alert drill delivering Telegram UNHEALTHY/RECOVERED
> (see the Drills note). Verified **locally** here: `bash -n` clean on both new scripts + the updated installer + the remote
> installer; all new/edited `.sh`/`.service`/`.timer` files are CRLF-free (LF enforced by the
> root `.gitattributes` from 4.4); `python -m py_compile` clean on both deploy drivers; and
> the env contract lines up — the remote installer writes `DATABASE_URL`, `BACKUP_DIR`,
> `BACKUP_RETENTION_DAYS`, `ALERT_TELEGRAM_BOT_TOKEN`/`_CHAT_ID` into `musicapi/.env`, which
> is exactly what the backup/healthcheck units read via `EnvironmentFile`.

---

## Phase 5 — Feature completion (may follow launch)

- `[x]` Per-user/per-key rate limits (REQUIREMENTS §4.4) — limits live in the
  `rate_limits` table (req/min, req/day, unique per user via `0008`) and are
  enforced at the API-key choke point (`requireKey`), so one budget is shared
  across all of a user's keys. Admin-managed via `GET`/`PUT
  /admin/users/:id/rate-limits` (admin panel **Users → Limits**); responses
  advertise `x-user-rate-limit`/`x-user-rate-remaining` and 429s carry
  `retry-after`. Verified on the local build 2026-10-01: 2/min limit → 1st/2nd
  `200`, 3rd `429` (`retry-after=24`).
- `[x]` Audit log for admin actions (§4.11) — append-only `audit_logs`
  (`0009_audit_logs.sql`: `actor_id` `ON DELETE SET NULL`, `actor_email` snapshot,
  `action`, `target_type`, `target_id`, `details JSONB`, `ip`, `created_at`, indexed
  on `created_at DESC`/`actor_id`/`action`). A best-effort `recordAudit()` helper in
  `src/server.ts` swallows write failures so it can never break the action it records;
  every admin mutation writes an entry (`account.create`, `user.status`, `user.credits`,
  `user.rate_limits`, `pricing.upsert`/`update`/`delete`, `routing.upsert`/`delete`,
  `content.create`/`update`/`delete`). Read side `GET /admin/audit` (admin-only, newest
  first, optional `action`/`actor_id`, `limit` default 200 cap 500) plus an admin panel
  **Audit Trail** page. Verified on the local build 2026-10-01 (**19/19** checks): anon
  `401`, non-admin `403`, mutations recorded with actor email + target + `details` + `ip`,
  newest-first, `action` filter, `limit` cap, and a 404 mutation correctly **not**
  recorded; fixtures cleaned up (0 leftover audit rows).
- `[x]` Credit-pack admin CRUD (§4.5) — `GET`/`POST`/`PUT`/`DELETE
  /admin/credit-packs` in `src/server.ts`. The admin list returns **all** packs
  (incl. inactive) with `id, amount, price, currency, is_active`; the public
  `/pricing` and `/me/billing` reads still return only active packs, so toggling
  `is_active` hides a pack from buyers without deleting it. `amount` must be a
  positive integer and `price` a non-negative number (else `400`); `currency` is
  upper-cased (default `USD`); a duplicate active `amount`+`currency` is `409`; a
  `PUT` to an unknown id is `404`. Each mutation writes an audit entry
  (`credit_pack.create`/`update`/`delete`). Admin panel **Credit Packs** page
  (add/edit/delete/active-toggle). Verified on the local build 2026-10-01
  (**25/25** checks): anon `401`, non-admin `403`, create `201`, four validation
  rejections `400`, duplicate `409`, update persisted, unknown-id `404`, inactive
  pack shown in admin list but absent from public `/pricing`, delete removes it,
  and audit rows for create (×3)/update/delete; fixtures cleaned up (0 leftover).
  Remaining Phase 5: none — the last item (§4.10) closed out just below.
- `[x]` Real usage analytics (§4.7) — `GET /admin/analytics?days=N` (admin-only) in
  `src/server.ts`, derived entirely from `usage_logs`. Returns `range.days`
  (clamped **7–90**, default 30), `credits_per_usd`, `totals`, and four breakdowns:
  `by_endpoint`, `by_model`, `by_user` (top 50 by requests) and a daily `series`.
  Every bucket carries `count`, `success`, `failed`, `credits`, `revenue`; a row
  counts as success when its job reached `complete` and a failure otherwise, so
  success + failed always equals the total. Revenue converts `credits_consumed` to
  USD using the **same cheapest-active-pack rate** as the user-facing `/me/usage`
  (now a shared `creditsPerUsdRate()` helper), so the two views never disagree. The
  `ComingSoon` placeholder `web-admin/app/admin/analytics/page.tsx` was replaced
  with a real dashboard (7/30/90-day range toggle, summary cards, a revenue bar
  chart and the three breakdown tables). Both packages typecheck + build clean
  (`/admin/analytics` route emitted). Verified on the local build 2026-10-01
  (**23/23** checks) with unique endpoint/model fixtures so each bucket is exact:
  anon `401`, non-admin `403`, exact per-user/endpoint/model buckets, the
  40-day-old row excluded at 30 d but included at 90 d, `days=1`→7 / `days=500`→90 /
  `days=abc`→30, window-independent consistency (sum of `by_endpoint`/`by_model`/
  `series` equals `totals`; success + failed = count) and revenue =
  `credits / credits_per_usd`; fixtures cleaned up (0 leftover). A `/me/usage`
  regression check also passed (`200`, shared rate honored).
- `[x]` Admin settings + alert config (§4.10) — operator settings + alerts in
  `src/server.ts`. `app_settings` (migration `0010_app_settings.sql`: `key TEXT
  PRIMARY KEY`, `value JSONB`, `updated_at`, `updated_by UUID REFERENCES users(id)
  ON DELETE SET NULL`) stores **one JSONB document per logical group** (`brand`,
  `alerts`) so a new group needs no migration. `GET /admin/settings` returns both
  groups with defaults filled in; `PUT /admin/settings` takes a partial
  `{brand}`/`{alerts}` patch, validates it (400 on empty `brand.name`, non-string
  URLs, non-string/non-`[string]` `languages`, non-boolean switches, or numeric
  thresholds outside range), merges onto the stored values, upserts the changed
  rows and writes a `settings.update` audit entry via `recordAudit`. Brand =
  `name`, `docs_url`, `support_telegram_url`, `languages[]`; alert config =
  `enabled`, `low_credits_threshold`, `captcha_locked`, `failure_rate_threshold`,
  `failure_rate_min_requests`, `window_minutes`. `evaluateAlerts()` checks the
  three §4.10 conditions — Suno accounts at/below the credit threshold
  (`pool.listHealth()`), Suno currently demanding a captcha (`captchaRequired()`),
  and a failure-rate spike over a sliding window of `usage_logs` (only once
  `failure_rate_min_requests` is reached) — surfaced by `GET /admin/alerts` as
  `{enabled, checked_at, thresholds, alerts[], summary}`. `GET /admin/accounts`
  now reads its low-credit badge threshold from the same `alerts` document so
  badge and alert never disagree. Delivery reuses the existing ops healthcheck
  bot: `syncAlertState()` diffs severities/messages and pushes to
  `ALERT_TELEGRAM_*` **only on state change** (one message per newly-raised/changed
  alert, one `[RESOLVED]` per cleared alert), driven by a background loop
  (`ALERT_CHECK_INTERVAL_MS`, default 5 min; `0` disables; started in `onReady`,
  cleared in `onClose`) or by opening the panel. The `ComingSoon` placeholder
  `web-admin/app/admin/settings/page.tsx` was replaced with a real page (brand +
  alert-config forms and a live alerts panel with per-condition stat cards, a
  re-check button and a severity-coloured list). Both packages typecheck + build
  clean (`/admin/settings` route emitted).
  **Legacy-schema reconciliation:** the shared `sunoapi` DB already carried a
  legacy `app_settings(key text, value text, updated_at)` table from the archived
  python/electron app (one `chmaba_webhook_secret` row), so 0010's `CREATE TABLE IF
  NOT EXISTS` was a silent no-op and the new code could not write JSONB. Added
  migration `0021_app_settings_reconcile.sql` (idempotent: adds `updated_by`,
  coerces a text `value` to JSONB via `to_jsonb`, enforces `NOT NULL`/default) and
  applied it; the legacy row is preserved as a JSON string, out of the way of the
  `brand`/`alerts` documents. Verified on the local build 2026-10-01 (**31/31**
  checks) against port 4011: anon `401` and non-admin `403` on all three
  endpoints, default setting shapes, seven validation `400`s, a valid `PUT`
  round-tripping through a fresh `GET` (brand name/languages,
  `low_credits_threshold`, `window_minutes`, `captcha_locked`), the `app_settings`
  rows persisted with `updated_by`, the `audit_logs` `settings.update` entry, the
  `/admin/alerts` report shape (thresholds reflect saved settings), and the
  disabled path (`enabled:false` → empty `alerts`); fixtures cleaned up
  (`app_settings` restored to its pre-run snapshot, fixture audit rows + users
  deleted).
- `[x]` Suno account edit/remove + health badges (§4.2) — account management in
  `src/server.ts` + `src/pool.ts`. `AccountPool` gained `captchaFor()` (a 60 s
  best-effort `captchaRequired()` cache that never throws; falls back to the last
  known value), a widened `listHealth()` returning `AccountStatus`
  (`id/plan/credits/models/captchaRequired`), a shared `loadCreds()` and a
  `reload()` that re-reads active accounts and clears the health/captcha caches.
  `GET /admin/accounts` now attaches a per-account `health`
  (`disabled: !is_active`, `low_credits: live_credits <= threshold`,
  `captcha_required`) where the threshold is read from the `app_settings.alerts`
  document (`low_credits_threshold`, default **50**) — the same value §4.10 uses, so
  badge and alert never disagree. `POST` now rejects a duplicate `label`
  (`409`) and calls `pool.reload()` so a new account is routable immediately, and
  writes `account.create`. New `PATCH /admin/accounts/:id` validates each field
  (`label` non-empty + duplicate-excluding-self `409`; `type` free|paid;
  `client_cookie` non-empty → encrypted; `device_id` non-empty; `is_active`
  boolean), rejects an empty body (`400`), guards against deactivating the last
  active account (`409`), reloads the pool and writes `account.update`. New
  `DELETE /admin/accounts/:id` guards the last active account (`409`), returns
  `404` on unknown ids, reloads the pool and writes `account.delete`. Admin panel
  **Suno Accounts** page gained per-row health badges (Healthy / Low credits /
  Captcha required / Disabled), an inline Edit form (cookie/device blank = keep
  current, Active toggle) and a confirm-guarded Remove. Both packages typecheck +
  build clean. Verified on the local build 2026-10-01 (**23/23** checks) against
  port 4011: anon `401`, every account carries the three boolean health flags,
  `POST` missing-fields `400` / create `201` / duplicate `409`, `PATCH` empty `400`
  / bad type `400` / duplicate label `409` / valid `200` with persisted
  label+type+device / unknown `404`, `DELETE` unknown `404`, the last-active guard
  (`PATCH`/`DELETE` both `409` once the other account is deactivated) and
  `account.create`/`update`/`delete` audit rows; pre-existing active accounts were
  parked and restored and fixtures cleaned up (0 leftover).

---

## Definition of "ready to go live"

- `[~]` Core + both apps build & typecheck clean, **committed from `main`** — builds/typechecks
  clean and the reference worktree has it committed on `main`; in this worktree `musicapi/`,
  `scripts/deploy/*` and `.gitattributes` are still **untracked** ([`fix/progress-music-count-distinct-songs`]),
  so the commit/merge is outstanding.
- `[x]` No free-credit or forgeable-token path — Phase 1 gate (1.3 charge race, 1.4 atomic
  payments, 1.5 SSRF, 1.7 OAuth).
- `[~]` Secrets rotated; cookies encrypted at rest — cookies ✅ (1.6 `enc:v1`); **secret
  rotation 1.8 still open**.
- `[x]` Jobs survive restart; workers/refunds safe — Phase 2 gate + sandbox **reboot drill**.
- `[x]` Both apps point at prod backend via env; admin auth server-enforced — Phase 3 gate.
- `[x]` nginx + TLS + process manager + backups + monitoring in place — live on the sandbox
  (3 vhosts + LE cert, 3 systemd services, nightly `pg_dump` + 5-min probe with Telegram alerts).
- `[x]` Deployed and smoked on sandbox first — 2026-10-01 gate (see Phase 4).
