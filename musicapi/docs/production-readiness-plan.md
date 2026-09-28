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
| 1.3 | Enforce `charge()` on all `/me/*`; atomic select+charge | `fix/musicapi-charge-race` | no free jobs under concurrency ✅ atomic `chargeUserKey` + concurrency check | `[x]` |
| 1.4 | Atomic KHQR confirm + admin top-up | `fix/musicapi-payment-atomic` | double-poll credits once | `[ ]` |
| 1.5 | Callback URL allowlist (block SSRF/private ranges) | `fix/musicapi-callback-ssrf` | external URL rejected | `[ ]` |
| 1.6 | Encrypt Suno `client_cookie` at rest | `feat/musicapi-cookie-encryption` | DB ciphertext; pool works | `[ ]` |
| 1.7 | OAuth per-request client, signed `state`, verified email | `fix/musicapi-oauth-hardening` | CSRF blocked; flow works | `[ ]` |
| 1.8 | Rotate leaked secrets; scrub `.env`/`accounts.json` | ops (user-led) | old creds invalid | `[ ]` |

**Gate:** no free-credit or forgeable-token path; secrets safe.
> Note: 1.1–1.2 landed as commits on `feat/musicapi-baseline` (Phase 0's branch) instead of their own branches. 1.3 replaced the non-atomic `pickUserKey()` + ignored `charge()` pattern on every `/me/*` route with a single-statement atomic `chargeUserKey()` that both selects and deducts, and 402s when it fails. 1.4–1.8 remain pending.

---

## Phase 2 — Durability & correctness

| # | Task | Branch | Verification | Status |
|---|---|---|---|---|
| 2.1 | Persist jobs (Postgres or Redis/BullMQ); recover on restart | `feat/musicapi-job-persistence` | restart mid-job resolves | `[ ]` |
| 2.2 | `.catch()` detached workers + `unhandledRejection`/`SIGTERM` | `fix/musicapi-worker-safety` | graceful drain | `[ ]` |
| 2.3 | Refund on terminal failure; `spend`/`refund` ledger rows | `feat/musicapi-refunds-ledger` | failed job restores credit | `[ ]` |
| 2.4 | TTL/LRU eviction for job map | `chore/musicapi-job-eviction` | memory bounded | `[ ]` |
| 2.5 | `trustProxy` so IP whitelist sees real client IP | `fix/musicapi-trust-proxy` | whitelist enforced | `[ ]` |
| 2.6 | Ordered idempotent migration runner | `feat/musicapi-migrations` | fresh + existing DB migrate | `[ ]` |
| 2.7 | Missing indexes (`usage_logs.api_key_id`, `credit_transactions.user_id`) | `perf/musicapi-indexes` | `EXPLAIN` uses index | `[ ]` |

**Gate:** restart-safe; no lost/refunded-money bugs; clean migrations.

---

## Phase 3 — Frontend production readiness

| # | Task | Branch | Verification | Status |
|---|---|---|---|---|
| 3.1 | Env-driven backend URL (both apps) | `fix/musicapi-fe-backend-url` | prod host via env | `[ ]` |
| 3.2 | Real session (httpOnly cookie or documented token + 401 logout) | `feat/musicapi-session` | expired → `/login` | `[ ]` |
| 3.3 | web-admin server-side guard (`middleware.ts` + role check) | `feat/musicapi-admin-guard` | non-admin blocked | `[ ]` |
| 3.4 | web-user authenticated downloads (blob) | `fix/musicapi-fe-downloads` | downloads 200 | `[ ]` |
| 3.5 | Remove fake dashboard chart → real usage data | `fix/musicapi-fe-dashboard` | chart matches API | `[ ]` |
| 3.6 | Delete dead `/app/*` tree + unused components/deps | `chore/musicapi-fe-cleanup` | routes still work | `[ ]` |
| 3.7 | Fix admin pricing edit (track `editingId`, PUT) | `fix/musicapi-admin-pricing-edit` | update, no duplicate | `[ ]` |
| 3.8 | Admin `/auth/callback`; align redirect URIs | `feat/musicapi-admin-oauth` | Google admin login | `[ ]` |
| 3.9 | Wire/hide placeholders; mark stubs "coming soon" | `chore/musicapi-fe-placeholders` | no dead UI | `[ ]` |

**Gate:** both apps build against prod env; no spoofable auth; no fake data.

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
