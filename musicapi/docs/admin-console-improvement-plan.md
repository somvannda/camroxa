# MusicAPI Admin Console — Improvement Plan (Gap Analysis + Roadmap)

> Scope: **`musicapi/web-admin` only** — the active admin console at
> `admin.musicapi.camxora.com` (Next.js 16.3.4 / React 19.2.8 / Tailwind 4),
> plus the `/admin/*` backend routes in `musicapi/src/server.ts` that it consumes.
> Legacy trees (`admin_portal/`, `platform_api/`, etc.) are explicitly **out of scope**.
>
> Baseline: `main` @ `0d9445e2` (2026-10-05). Verified against
> `security/phase0-hardening` — `main` has **no** admin-surface diff beyond it
> (`git diff --stat security/phase0-hardening..main -- musicapi/web-admin musicapi/src/server.ts musicapi/migrations` is empty).
>
> Status: **analysis complete** (static). Local-run and live-browser verification still pending.
> Legend: `[ ]` pending · `[~]` partial · `[x]` done · `[!]` blocked / needs decision.

---

## 1. Executive summary

The admin console is **functionally wired** — 11 pages backed by 33 real `/admin/*`
routes, a server-side auth guard, audit logging, alerts, analytics and settings.
It is *not* production-grade as an operator tool yet. The main gaps are:

1. **Revenue and operational data are invisible.** There is no admin surface for
   `payment_transactions`, `credit_transactions`, or `jobs`, even though the
   backend writes all three and the ChmabaPay flow moves real money. "Revenue" on
   the dashboard is *estimated* from `credits_consumed`, not actual receipts.
2. **No shared UI layer.** Every page re-implements buttons, inputs, tables,
   modals and loading/error states with copy-pasted Tailwind. This is the largest
   maintainability and consistency problem.
3. **UX is raw.** Destructive actions use `window.prompt`/`window.confirm`; there
   are no toasts, almost no skeletons, no URL state, no responsive layout, and
   weak accessibility (unlabeled inputs, no modal focus management, no table scopes).
4. **Data scale isn't handled.** `/admin/logs` and `/admin/audit` hard-cap at 200
   rows with client-side filtering; users/keys return everything. No pagination,
   server-side filters, or sorting anywhere.
5. **Security/correctness holes.** `requireAdmin` ignores `status`, so a
   **suspended admin keeps full API access**; there is no last-admin/self-suspension
   guard; no 2FA; the keys page is read-only; there is no admin-account management.
6. **Build is not clean.** `npm run lint` reports **9 errors + 4 warnings**.

Estimated effort to reach "solid operator console": Phase 0–2 are small and high
leverage; Phase 3 is the largest; Phase 4 adds the missing domains.

---

## 2. Current state (verified)

### 2.1 Stack & structure

| Piece | Detail |
|---|---|
| `web-admin` | Next 16.3.4, React 19.2.8, Tailwind 4; dev on `:4002`, prod `admin.musicapi.camxora.com` |
| Backend | Fastify 5 + TypeScript monolith `musicapi/src/server.ts` (8,909 lines); `:4003` |
| DB | PostgreSQL `sunoapi`; 28 ordered migrations; 15 tables |
| Auth | Admin **email/password only** (bcrypt) → JWT in httpOnly `sunosession_admin` cookie, `SameSite=Lax`, `Secure` in prod |
| Guard | `web-admin/proxy.ts` (Next 16 `proxy` convention) forwards the cookie to `/auth/me`; non-admin/inactive → `/login` |

### 2.2 Pages (11)

Dashboard, Suno Accounts, Users, API Keys, Usage Logs, Audit Trail, Pricing,
Credit Packs, Analytics, API Updates, Settings.

### 2.3 Admin API (33 routes)

`/admin/keys`, `/admin/accounts` (GET/POST/PATCH/DELETE), `/admin/stats`,
`/admin/analytics`, `/admin/users` (GET/PATCH), `/admin/users/:id/credits`,
`/admin/users/:id/rate-limits` (GET/PUT), `/admin/pricing` (GET/POST/PUT/DELETE),
`/admin/credit-packs` (GET/POST/PUT/DELETE), `/admin/routing` (GET/POST/DELETE),
`/admin/logs`, `/admin/content` (GET/POST/PUT/DELETE), `/admin/audit`,
`/admin/settings` (GET/PUT), `/admin/settings/integrations` (PUT), `/admin/alerts`.

Every route calls `requireAdmin`, which re-reads `role` from the DB each request.

### 2.4 Data model (15 tables)

`users`, `api_keys`, `credit_transactions`, `usage_logs`, `suno_accounts`,
`routing_rules`, `pricing`, `credit_packs`, `blog_posts`, `rate_limits`,
`payment_transactions`, `jobs`, `audit_logs`, `app_settings`, `download_purchases`.

Notable admin-relevant columns: `users.email_subscription`,
`users.credit_alert_thresholds`, `api_keys.{safe_spend_limit,hourly,daily,total,ip_whitelist,credits_expire_at,last_used_at}`,
`payment_transactions.{provider,provider_payment_id,gateway_payment_id,checkout_url,status,paid_at,expires_at}`,
`jobs.{type,status,account_id,error,payload,callback_url,credits}`, `audit_logs.details`.

---

## 3. Method & coverage

| Area | Depth | Status |
|---|---|---|
| `web-admin` (all pages, components, lib, config, proxy, css) | line-by-line | `[x]` |
| Admin API slice (`server.ts` 5504–6539) | full | `[x]` |
| Auth/guard (`appAuth.ts`, `auth.ts`, `requireAdmin`, `requireAuth`, `/auth/*`, `/metrics`) | full | `[x]` |
| Schema (28 migrations) | full | `[x]` |
| `config.ts`, `serve.ts`, `db.ts`, `pool.ts`, `runtimeSettings.ts`, `jobQueue.ts`, `storage.ts` | full | `[x]` |
| Charge / rate-limit / audit / alert / settings internals | full | `[x]` |
| Payments backend (`/payments/chmaba/*`, settle/reverse, webhook) | full | `[x]` |
| Docs (REQUIREMENTS, roadmap, competitor, parity, readiness) | read | `[x]` |
| `npm run lint`, `npm run typecheck` | executed | `[x]` |
| Local DB probe | executed | `[x]` |
| **Local stack run + page walkthrough** | — | `[ ]` |
| **Live browser audit of admin.musicapi.camxora.com** | — | `[ ]` |
| Remaining ~7k lines of `server.ts` (job recovery/verify paths) | — | `[ ]` (optional) |

**Environment verified:** Node 24.13.0, npm 11.6.2, PostgreSQL 16 running on
`:5432`, ports 4001–4003 free, `musicapi/.env` complete (DATABASE_URL, JWT_SECRET,
COOKIE_ENCRYPTION_KEY, Suno/Google/Chmaba/B2 keys all set).

**Local DB snapshot:** 4 users, 8 API keys, 2 Suno accounts, 225 usage logs,
65 credit transactions, 45 jobs, 14 audit logs, 0 blog posts, 42 pricing rows,
4 credit packs, 1 app_settings row, 0 rate limits, 1 download purchase.
Admins: `admin@example.com` (active).

---

## 4. Findings

Severity: **P0** = blocks correct/safe operation · **P1** = major operator gap ·
**P2** = polish / scale.

### 4.1 Functional gaps — missing admin domains

- **`[P0]` Payments have no admin UI/API.** `payment_transactions` is written by
  the ChmabaPay create/status/webhook flow (uniquely keyed, HMAC-verified), but
  there is **no `/admin/payments`**. Operators cannot see pending/paid/expired/
  failed/refunded, reconcile a `provider_payment_id`/`gateway_payment_id`, or
  manually fulfil/refund. Dashboard "Revenue" is derived from credits spent, not
  receipts. *(Evidence: `server.ts` 9181–9399; only `/me/transactions` exists, for
  the user.)*
- **`[P0]` Credit ledger has no admin view.** `credit_transactions`
  (purchase/adjust/spend/refund, linked to `job_id`) is invisible to admins; no
  way to inspect where credits went, expire balances, or refund.
- **`[P1]` No jobs/queue console.** `jobs` is the system of record (status,
  account, error, payload, callback) and queue-backlog alerts exist, yet admins
  cannot list running/stuck/failed jobs, read the error, or retry/cancel.
  `/metrics` is JSON-only.
- **`[P1]` No system-health page.** `/health`, `/metrics`, DB pool, queue driver,
  B2 storage, captcha balance and Suno session freshness never surface in the UI.
- **`[P1]` API keys are read-only.** Admin can list (grouped by owner) but cannot
  enable/disable, delete, rotate, edit safe-spend limits or IP whitelist, or
  force credit expiry — all columns exist and users can edit their own via
  `/me/keys/:id`.
- **`[P1]` No user detail.** No `/admin/users/:id`. Cannot see a user's keys,
  transactions, usage, login method (Google vs password), language,
  `email_subscription`, `credit_alert_thresholds`, last activity, or delete.
- **`[P1]` No admin-account / RBAC management.** Admins are seeded via
  `scripts/seed.ts`/SQL only. No create/disable admin, no role change, no
  last-active-admin guard. `/admin/users/:id` can suspend **any** user including
  yourself/other admins.
- **`[P2]` Routing rules** are `model → policy` only: no enable/disable,
  priority/weight, per-account preference, or test.
- **`[P2]` Pricing/content/settings depth:** no bulk edit, change history, or
  "used by" warnings; content is a plain textarea (no markdown preview,
  scheduling, inline publish); Settings has no test buttons (Telegram/SMTP/
  2Captcha/Chmaba webhook/B2) or validation report.

### 4.2 Backend / API gaps

- **`[P1]` No pagination, filtering or sorting** on any admin list. `/admin/logs`
  = `LIMIT 200`; `/admin/audit` = up to 500 with only `action`/`actor_id` filters
  and no offset/date range/export; `/admin/users` and `/admin/keys` return all rows.
- **`[P2]` N+1 queries.** `/admin/users` runs 3 correlated subqueries per row
  (`credits`, `key_count`, `request_count`); `/admin/keys` runs 2.
- **`[P2]` Missing endpoints:** `/admin/users/:id`, `/admin/keys/:id` (mutate),
  `/admin/payments`, `/admin/transactions`, `/admin/jobs`, `/admin/health`,
  `/admin/admins`.
- **`[P2]` No idempotency/optimistic concurrency** on admin mutations.

### 4.3 Frontend / UI-UX gaps

- **`[P1]` No shared components.** Buttons, inputs, cards, tables, badges,
  banners, modals are copy-pasted with long identical class strings across all 11
  pages.
- **`[P1]` No data-fetching layer** (no React Query/SWR). Each page re-implements
  loading/error/refetch/cancellation; several `setState` after unmount. Only
  Analytics handles staleness.
- **`[P1]` Raw destructive UX.** `window.prompt` for credit adjustment
  (`users/page.tsx`), `window.confirm` for deletes (users/accounts/content/packs/
  pricing). No typed confirm, no impact preview.
- **`[P1]` No toasts**, no global error boundary, no route-level
  `loading.tsx`/`error.tsx`/`not-found.tsx`.
- **`[P1]` Not responsive.** Fixed `w-60` sidebar, `p-8` main, no mobile drawer;
  tables not scroll-safe.
- **`[P1]` Accessibility.** Labels not tied to inputs (`htmlFor`/`id`), modals
  lack `role="dialog"`/focus trap/ESC, tables lack `scope`, no skip link/focus
  rings, raw `<img>`.
- **`[P2]` No URL state** — filters/search/page reset on refresh/back.
- **`[P2]` Thin dashboard** — no alerts card, queue depth, payments-today, recent
  audit, or quick actions, despite `/admin/alerts` and `/metrics` already returning
  the data.
- **`[P2]` Sidebar** — no icons, grouping, badges (pending payments/alerts/queue),
  or collapse.
- **`[P2]` Login** — no show/hide password, caps-lock hint, or lockout feedback.
- **`[P2]` Misc** — dead `components/ComingSoon.tsx`; ~25 KB `favicon.ico`;
  inconsistent number/date formatting (local `toLocaleString`, no timezone);
  no copy-to-clipboard for IDs/prefixes; no unsaved-changes guard.

### 4.4 Build health (executed)

`npm run typecheck` → clean. `npm run lint` → **13 problems (9 errors, 4 warnings)**:

| File | Line | Rule | Severity |
|---|---|---|---|
| `app/admin/accounts/page.tsx` | 74 | `react-hooks/set-state-in-effect` | error |
| `app/admin/audit/page.tsx` | 32 | `react-hooks/set-state-in-effect` | error |
| `app/admin/content/page.tsx` | 32 | `react-hooks/set-state-in-effect` | error |
| `app/admin/content/page.tsx` | 84 | `@typescript-eslint/no-unused-expressions` | warning |
| `app/admin/credit-packs/page.tsx` | 39 | `react-hooks/set-state-in-effect` | error |
| `app/admin/keys/page.tsx` | 39 | `react-hooks/set-state-in-effect` | error |
| `app/admin/pricing/page.tsx` | 36 | `react-hooks/set-state-in-effect` | error |
| `app/admin/settings/page.tsx` | 111 | `react-hooks/set-state-in-effect` | error |
| `app/admin/users/page.tsx` | 39 | `react-hooks/set-state-in-effect` | error |
| `components/Sidebar.tsx` | 31 | `react-hooks/set-state-in-effect` | error |
| `app/login/page.tsx` | 46 | `@next/next/no-img-element` | warning |
| `components/Sidebar.tsx` | 46 | `@next/next/no-img-element` | warning |
| `lib/api.ts` | 23 | `@next/next/no-location-assign-relative-destination` | warning |

### 4.5 Security

- **`[P0]` `requireAdmin` does not check `status`.** It verifies `role` from the
  DB (`server.ts:1154`) but not `status`, so a **suspended admin's JWT still
  grants full admin API access** (only `proxy.ts` blocks the page). Fix: also
  require `status = 'active'` (and reject in `/auth/login` already does).
- **`[P1]` No last-admin / self-suspension guard.** `/admin/users/:id` PATCH can
  suspend the last active admin or the caller. Fix: block suspending/demoting the
  last active admin and warn on self.
- **`[P1]` No 2FA** for admins; 7-day JWT with no revocation list.
- **`[P2]` No CSP** in `next.config.ts` (API has helmet).
- **`[P2]` CSRF** is mitigated (SameSite=Lax + Origin allowlist in `requireAuth`)
  but not tokenized.
- Confirmed strong: API keys are sha256-hashed, Suno cookies AES-256-GCM
  encrypted, admin login rate-limited, `/metrics` admin-guarded, SSRF guard on
  callbacks.

---

## 5. Verification status / open unknowns

- **`[!]` Migration-filename mismatch.** The local `sunoapi` DB's
  `schema_migrations` does **not** match this branch's `migrations/`:

  | Prefix | Repo file | Local DB applied |
  |---|---|---|
  | 0025 | `0025_rate_limits_window.sql` | `0025_credit_pack_production_parity.sql` |
  | 0026 | `0026_pricing_production_sync.sql` | `0026_pricing_production_alignment.sql` |
  | 0027 | `0027_pricing_full_production_sync.sql` | `0027_credit_pack_relaunch.sql` |
  | 0028 | `0028_usage_logs_net_failed_credits.sql` | `0028_credit_pack_reprice.sql` |

  Consequence: running `scripts/migrate.ts` now would apply repo `0025–0028` on
  top of a differently-seeded DB. **Resolve before any local-run verification.**
  Decide which branch's migrations are authoritative.
- **`[ ]` Local run not performed** — API + `web-admin` not booted this session.
- **`[ ]` Live audit not performed** — `admin.musicapi.camxora.com` not inspected.
- **`[ ]` Remaining `server.ts`** job recovery/verify paths not read (not needed
  for the admin plan).

---

## 6. Related in-flight work (avoid duplication)

The repository already has admin-oriented branches that may cover some findings
above — reconcile before starting:

- `origin/feature/admin-sidebar-nav-groups`
- `origin/feature/admin-dashboard-live-ops`
- `origin/feature/admin-users-search-filters`
- `origin/feature/admin-user-generated-songs` / `feature/admin-user-detail(s)`
- `origin/bugfix/admin-dashboard-credit-cards-cleanup`
- `origin/bugfix/admin-health-via-api-proxy`
- `origin/feature/admin-provider-today-usage`, `feature/admin-fail-absorb-ui`
- `hotfix_admin_*` deploy scripts (legacy `admin_portal` lineage — out of scope)

---

## 7. Roadmap

Each phase = its own branch off `main`, one logical change per commit. Phase 3's
security fixes should land first if speed matters.

### Phase 0 — Hygiene `[ ]`
Small, safe, unblocks everything.
- Fix the 9 lint errors + 4 warnings (convert effect-body loads to a data hook).
- Remove dead `components/ComingSoon.tsx`.
- Replace raw `<img>` with `next/image`; fix `lib/api.ts` navigation warning.
- Add per-route `loading.tsx` / `error.tsx` / `not-found.tsx`; add a root error
  boundary; `robots: noindex` on the console.
- Acceptance: `npm run lint` and `npm run typecheck` clean.

### Phase 1 — UI foundation `[ ]`
Pure refactor, no behavior change.
- `components/ui/`: Button, IconButton, Input, Select, Textarea, Checkbox,
  Field, Card, StatCard, Badge, Table (+sort/paginate), Pagination, Modal,
  ConfirmDialog, Toast/Toaster, Skeleton, EmptyState, ErrorState, Tabs, Tooltip,
  CopyButton, Drawer, PageHeader, Breadcrumbs.
- `AppShell`: responsive sidebar/drawer + topbar + quick actions.
- Hooks: `useResource` (fetch/loading/error/refetch/cancel), `useToast`,
  `useConfirm`, `useMediaQuery`.
- Migrate existing pages onto the primitives.
- Acceptance: no visual regression; no duplicate class strings left.

### Phase 2 — UX polish `[ ]`
- Replace `prompt`/`confirm` with `ConfirmDialog` (typed confirmation for
  destructive actions) and add toasts for success/error.
- Skeletons, empty states and retry on every page.
- Form validation + inline errors + disabled/loading states.
- A11y: label associations, modal focus trap/ESC/`role`, table `scope`, skip
  link, focus-visible.
- URL state for filters/search/page.
- Acceptance: keyboard-only walkthrough of every page passes.

### Phase 3 — Data scale + correctness `[ ]`
- Backend pagination/filter/sort for `/admin/logs`, `/admin/audit`,
  `/admin/users`, `/admin/keys`; add indexes (`usage_logs(created_at)`,
  `usage_logs(status)`) as needed.
- Add `/admin/users/:id` detail; keys mutate endpoints (enable/disable/delete/
  rotate/safe-spend/IP).
- **Security fixes:** `requireAdmin` status check; last-admin/self-suspension guard.
- Acceptance: all tables server-driven; security tests cover suspended admin and
  last-admin.

### Phase 4 — New admin domains `[ ]`
- **Payments**: list/filter, status, reconcile, manual fulfil/refund, export.
- **Credit ledger**: transactions, filter by type/user, manual grant/refund.
- **Jobs/queue**: running/failed, error detail, retry/cancel.
- **System health**: `/health` + `/metrics` + DB/queue/B2/captcha/Suno sessions.
- **Admin accounts/RBAC**: create/disable admins, role change, guards.
- **User detail** page: keys, transactions, usage, profile fields.
- Acceptance: every `payment_transactions`/`credit_transactions`/`jobs` row is
  inspectable; admin lifecycle manageable without SQL.

### Phase 5 — Depth `[ ]`
- Dashboard: alerts card, queue depth, payments-today, recent audit, quick actions.
- Analytics: cost/profit, error-message breakdown, custom range, exports.
- Content: markdown editor + preview, scheduling, inline publish.
- Settings: test buttons (Telegram/SMTP/2Captcha/Chmaba webhook/B2), config report.

### Phase 6 — Hardening `[ ]`
- Admin 2FA (TOTP), session revocation, CSRF token, CSP headers.
- Tests: component/unit + e2e for critical admin flows; wire into
  `.github/workflows/pr-checks.yml`.

---

## 8. Open decisions

1. **Migrations:** which branch's `0025–0028` are authoritative? (blocks local run)
2. **Design direction:** keep the current dark violet theme, or align with a
   design system? (affects Phase 1 tokens)
3. **Deprecate vs port:** do any `origin/feature/admin-*` branches supersede items
   in Phase 3/4?
4. **2FA requirement:** is TOTP mandatory before wider rollout?

---

## 9. Reference index

- Frontend: `musicapi/web-admin/{app,components,lib,proxy.ts,next.config.ts,globals.css}`
- Admin API: `musicapi/src/server.ts:5504–6539`
- Auth/guard: `musicapi/src/appAuth.ts`, `musicapi/src/server.ts:1126–1168`, `musicapi/web-admin/proxy.ts`
- Payments: `musicapi/src/server.ts:9014–9399`
- Settings engine: `musicapi/src/runtimeSettings.ts`
- Pool/routing: `musicapi/src/pool.ts`
- Schema: `musicapi/migrations/0001–0028`
- Lint: `cd musicapi/web-admin; npm run lint`

---

## 10. Progress & branch map (2026-10-05)

Implementation tracks this plan across several local branches. Suggested review /
merge order (rebase the stacked branches onto `main` after the foundation lands):

| Branch | Base | Scope |
|---|---|---|
| `docs/musicapi-admin-console-plan` | `main` | this document |
| `admin/ui-foundation` | `main` | Phase 0 + Phase 1 |
| `admin/auth-guards` | `main` | Phase 3 security fix (`requireAdmin` status; last-admin/self guards) |
| `admin/perf-indexes` | `main` | Phase 3 — migration `0029_admin_perf_indexes.sql` |
| `admin/payments-ledger` | `admin/ui-foundation` | Phase 4 — Payments + Credit Ledger |
| `admin/keys-management` | `admin/payments-ledger` | Phase 3 — key enable/disable/delete |
| `admin/system-health` | `admin/ui-foundation` | Phase 4 — System Health + Jobs |
| `admin/user-detail` | `admin/ui-foundation` | Phase 4 — user drill-down |
| `admin/pagination` | `admin/ui-foundation` | Phase 3 — paginated logs + audit |
| `admin/users-pagination` | `admin/ui-foundation` | Phase 3 — paginated users |
| `admin/rbac` | `admin/ui-foundation` | Phase 4 — administrator management |
| `admin/security-headers` | `admin/ui-foundation` | Phase 6 — security headers + CSP |
| `admin/dashboard-alerts` | `admin/ui-foundation` | Phase 5 — dashboard alerts |
| `admin/analytics-errors` | `admin/ui-foundation` | Phase 5 — analytics top failures |
| `admin/login-a11y` | `admin/ui-foundation` | Login label/input association |
| `admin/keys-pagination` | `admin/ui-foundation` | Phase 3 — paginated / searchable API keys |
| `admin/robots` | `admin/ui-foundation` | `robots.txt` disallow |
| `admin/readme` | `admin/ui-foundation` | Real `web-admin` README |
| `admin/tests` | `admin/ui-foundation` | `node:test` unit tests for the shared formatters (`npm test`) |

### Completed

- **Phase 0** — lint/build hygiene (all 9 errors + 4 warnings fixed), route
  boundaries, `noindex`.
- **Phase 1** — UI kit (`Button`, `Card`/`StatCard`, `Badge`, `Field` +
  `Input`/`Select`/`Textarea`, `Feedback`, `Modal`, `ConfirmDialog`, `Toast`),
  `useResource`, `format.ts`, responsive `AppShell`; every page migrated
  (Analytics keeps its bespoke charts by design).
- **Phase 2** — `window.prompt`/`window.confirm` replaced by dialogs; toasts
  everywhere; URL-state persistence for every list page (payments, ledger, logs,
  audit, users, keys, jobs); login label/input association.
- **Phase 3** — server-side pagination + filters for logs, audit, users and API
  keys; migration `0029` indexes; CSV export for payments, ledger and users;
  manual ChmabaPay refund.
- **Phase 4** — Payments, Credit Ledger, Jobs, System Health, User detail, Admin
  RBAC.
- **Phase 5 (partial)** — dashboard alerts; analytics top-failure breakdown.
- **Phase 6 (partial)** — baseline security headers + production CSP + HSTS;
  `robots.txt` disallow.
- **Verification** — local end-to-end run passed (2026-10-05) against a separate
  scratch DB (`sunoapi_admin_dev`, all 28 migrations applied), which sidesteps the
  shared-DB migration mismatch: login, every page, pagination shapes, CSV export
  and the credit-adjustment + audit write path, with **zero console errors**. The
  live production site was audited read-only (login page only — no credentials).

### Not done

- Admin 2FA; CSRF tokenization.
- Automated tests: formatter tests added (`admin/tests`, `npm test`); wiring them into CI is still pending.

### Branch strategy note

Each feature branch touches shared files (`musicapi/src/server.ts`,
`web-admin/components/AppShell.tsx`), so they must be merged sequentially with
conflict resolution. Merge `admin/ui-foundation` first, then rebase the rest onto
it (or onto `main` once the foundation lands).

---

## 11. Local DB / migration mismatch (diagnosed 2026-10-05)

The local `sunoapi` database was built from a different schema lineage than this
branch. `schema_migrations` lists differently-named `0025–0028` files
(`0025_credit_pack_production_parity`, `0026_pricing_production_alignment`,
`0027_credit_pack_relaunch`, `0028_credit_pack_reprice`), and
`payment_transactions` carries an extra `external_id` column — so this branch's
`migrations/0025–0028` are **not** applied.

Concretely, the code expects columns the database is missing:

- `rate_limits.requests_per_window` and `rate_limits.max_concurrent_jobs`
  (branch migration `0025_rate_limits_window`) are **absent** locally. This
  breaks the per-user rate-limit read (`loadUserRateLimits`), so every API-key
  request (`/v1/*`, `/me/*`) and the admin rate-limits editor would fail at
  runtime. The local `rate_limits` table has only
  `id, user_id, requests_per_minute, requests_per_day`.

**Do not** blindly run `scripts/migrate.ts` against the shared local DB: this
branch's `0026`/`0027` pricing syncs would rewrite pricing, and `0028` backfills
`usage_logs`. Reconcile deliberately — rebuild the local DB from this branch's
migrations, or apply only `0025_rate_limits_window` as a targeted fix — before a
local end-to-end run.
