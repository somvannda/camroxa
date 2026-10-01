# musicapi — State of the Art & Remediation Roadmap

> Scope: the deployable surfaces inside `musicapi/` — Core API (`src/`), `web-user`, `web-admin`,
> PostgreSQL `sunoapi`, and ops/deploy.
> Written: 2026-09-30. Baseline commit: `integration/musicapi-phase2` @ `3117ea6b`.
> Companion docs: [REQUIREMENTS.md](../REQUIREMENTS.md) · [production-readiness-plan.md](./production-readiness-plan.md) · [ENDPOINT_STATUS.md](../ENDPOINT_STATUS.md)

Legend: `[ ]` pending · `[~]` in progress · `[x]` done · `[!]` blocked on explicit approval

---

## 1. What musicapi is

A **white-label, commercial AI music-generation platform** built on the reverse-engineered **Suno
web interface**. It exposes a REST API in the shape of `docs.sunoapi.org` to paying customers,
bills them in **credits**, and drives a pool of real Suno accounts behind the scenes.

Three deployables:

| Piece | Stack | Port |
|---|---|---|
| Core API | Fastify 5, TypeScript (ESM, `tsx`) | **4003** |
| `web-user` | Next.js 16.3.4, React 19.2.8, Tailwind 4 | **4001** |
| `web-admin` | Next.js 16.3.4, React 19.2.8, Tailwind 4 | **4002** |
| PostgreSQL | db `sunoapi` | 5432 |

**Request path:** `Authorization: Bearer <key>` → Fastify edge (helmet, CORS, rate-limit,
IP-whitelist) → key hash lookup → **credit reserve** → job persisted to `jobs` → routed to a pooled
Suno account → Suno web API driven (auth/generate/poll/captcha) → credits charged on success,
**refunded + ledgered** on terminal failure.

**Key modules:** [src/serve.ts](../src/serve.ts) (boot/shutdown) ·
[src/config.ts](../src/config.ts) (fail-fast env contract) · [src/server.ts](../src/server.ts)
(all routes) · [src/pool.ts](../src/pool.ts) (account pool + routing) ·
[src/cookieCrypto.ts](../src/cookieCrypto.ts) (AES-256-GCM cookie encryption) ·
[migrations/](../migrations) (`0001`–`0019`, idempotent ordered runner).

---

## 2. Verified current state (2026-09-30)

| Fact | Evidence |
|---|---|
| Runs locally end-to-end | Core API `200 /health` (2 Suno accounts), `web-user` `200`, `web-admin` `200` |
| DB schema current | `0001`–`0019` applied against `sunoapi` |
| Phases 0–4 of the go-live plan complete | [production-readiness-plan.md](./production-readiness-plan.md) — all `[x]`, sandbox-verified |
| Phase 5 feature completion | All six items `[x]` (rate limits, audit log, credit packs, analytics, settings/alerts, account health) |
| Only open plan item | `1.8` provider rotation — `[~]` (audit + runbook done; provider-side rotation user-led) |
| ~~Branch not on origin~~ **resolved 2026-10-01** | `integration/musicapi-phase2` landed on `origin/main` via **PR #185** (merge commit `5d9cdf58`); `git merge-base --is-ancestor 5d7611ab origin/main` → true |
| ~~Worktree sprawl~~ **resolved 2026-10-01** | Was **56 worktrees total, 43** of them `MusicGenerator-musicapi*`. R7 pruned the musicapi family to **1** (`-integration`); a separate user-approved follow-on then removed 7 merged+clean legacy worktrees → **7 total** |
| Doc drift | `ENDPOINT_STATUS.md` dated **2026-09-09** and pointing at a stale `e:/Development/SunoAPI` path |
| **Route surface re-verified** | **205** registered routes (not 100). Full-tree sweep: `{"200":6,"400":2,"401":194,"404":1,"405":1,"503":1}` — the single `404` and the `405`/`503` are all intentional (see [ENDPOINT_STATUS.md](../ENDPOINT_STATUS.md)) |
| **Public-API validation intact** | 62 `POST` probes on `/v1/*` + `/api/v1/*` with a valid key + empty body → **62 × `400`**, zero `500`s |
| **Live-Suno correctness still unproven** | No job-submission route has a success path proven on this commit; last deep evidence is 2026-09-09 on another tree |

---

## 3. Gaps (ranked by risk)

### G1 — Unverifiable endpoint truth  *(partially resolved 2026-09-30)*
The old [ENDPOINT_STATUS.md](../ENDPOINT_STATUS.md) reported **16 VERIFIED · 8 PROBABLY WORKS ·
76 NOT VERIFIED** and described a **different, older tree** (it also undercounted the surface as
"100 registered routes"). As of 2026-09-30 the report is rewritten against this commit and **axis A
is now fully known**: 205 routes, 194 correctly auth-gated, 62/62 public-API `POST`s validating
input, zero genuine not-routed routes.
**What remains unknown (axis B):** no job-submission route has a live-Suno success path proven on
this commit — the entire revenue surface (`/v1/*` + `/api/v1/*`, 102 routes) and all 32 admin routes
have still never handled a real success request. Closing this needs R1.2, which spends real quota.

### G2 — No integration branch  *(resolved 2026-10-01 — see R2)*
The whole platform existed only on a local feature branch with no upstream; the branch had drifted
162 ahead / 67 behind `main`. Landed on `origin/main` via PR #185 (merge commit `5d9cdf58`), so
`main` is now the shared source of truth.

### G3 — Divergent local config across worktrees  *(resolved 2026-10-01 — see R7)*
The 43 musicapi worktrees carried **at least three different `COOKIE_ENCRYPTION_KEY` values**. The
`suno_accounts` rows are encrypted with `d53e92c7…`; using any other key makes the server fail to
boot (`Unsupported state or unable to authenticate data`). This was a live footgun — it already cost
a boot failure on 2026-09-30. R7 removed the 42 merged worktrees (their 12 non-canonical `.env`
files were archived first), leaving only `-integration`, which already holds the canonical key.

### G4 — In-memory job queue  *(resolved 2026-09-30 — see R4)*
[REQUIREMENTS.md](../REQUIREMENTS.md) §Queue: Redis/BullMQ was `[PENDING]`; jobs ran on an in-memory
LRU/TTL map mirrored to Postgres. Restart recovery and single-node correctness were handled (Phase
2.1), but this **could not scale past one process** and offered no real work queue. R4 adds BullMQ
behind `QUEUE_DRIVER` (default `memory`), plus serializable job descriptors so work stranded by a
crashed process is re-queued on boot and adopted elsewhere. Staging caveat: only descriptor-backed
ops move onto workers so far — composite submissions still run in-process.

### G5 — Go-live checklist never signed off  *(reviewed 2026-09-30 — see R5.1)*
The plan's own *"Definition of ready to go live"* section was **entirely unchecked**. Reviewed
2026-09-30 into evidence-backed, owner-tagged lines: 5 met, 2 `[~]` — "committed from `main`"
(blocked by G2) and "secrets rotated" (blocked by `1.8`), plus the live-Suno half of "smoked on
sandbox" (blocked by R1.2).

### G6 — Stale status markers inside REQUIREMENTS.md  *(resolved 2026-09-30 — see R1.4)*
`REQUIREMENTS.md` claimed Suno cookie encryption was `[PENDING]` and per-user rate limits were
`[PENDING]`, but both shipped (Phase 1.6 and 5.1). Readers couldn't trust the requirement tables.
Corrected on 2026-09-30; the last genuinely open marker (the Redis queue) closed with R4.

### G7 — Deploy footgun  *(resolved 2026-09-30 — see R8)*
`install_musicapi_services.sh` only `systemctl enable --now`s the units — a **no-op on an already
running service** — so a redeploy silently keeps the old `node dist/serve.js` until someone runs
`systemctl restart camxora-musicapi` manually. Hit on every Phase 5 task (5.1–5.6). Fixed by
restarting unconditionally after `enable`, then asserting `ActiveEnterTimestamp` is newer than
`dist/serve.js`'s mtime.

---

## 4. Recommendations & execution plan

Ordered by risk reduction per unit of effort. Items marked **[GATE]** stop for explicit user
approval before proceeding.

### R1 — Re-verify endpoints against the live tree and reconcile the status doc
**Addresses G1, G6.** Highest value: it converts an unknown into a known.
- [x] R1.1 Stand up the local stack (core 4003 + a seeded test API key) and run the existing
      probes: [scripts/smoke-test-all-routes.ts](../scripts/smoke-test-all-routes.ts),
      [probe_e2e.ts](../probe_e2e.ts), [scripts/smoke-test-sunoapi-aliases.ts](../scripts/smoke-test-sunoapi-aliases.ts).
      *(done 2026-09-30 — full-tree sweep over all **205** routes, now a permanent tool:
      [scripts/smoke-test-reachability.ts](../scripts/smoke-test-reachability.ts). The three probe
      scripts named above have stale base URLs (`3003`/`3000`) and an existing T3 tier that spends
      real credits; the sweep replaces them for axis A and never spends.)*
- [ ] R1.2 Execute the P0–P5 priorities from `ENDPOINT_STATUS.md` §Next Priorities, starting with
      P0 (`POST /me/generate` → poll → download) and P3 (public `/v1/*` with a real API key).
      **Blocked on a decision to spend real Suno quota/credits.**
- [x] R1.3 Rewrite `ENDPOINT_STATUS.md` against **this** tree: correct the path references, the
      handler line numbers, the ports, and the ✅/🟡/⚠️ counts. Add a "last verified" date.
      *(done 2026-09-30 — re-dated, `e:/Development/SunoAPI` → this worktree, **100 → 205** routes,
      added axis A/B split and the T1/T2 histograms.)*
- [x] R1.4 Correct the stale `[PENDING]` markers in `REQUIREMENTS.md` (cookie encryption,
      per-user rate limits, admin panel) so the requirement tables match shipped reality.
      *(done 2026-09-30 — Security/Rate-limiting → `[DONE]`, Durability → `[PARTIAL]`, phasing 2/3
      → `[DONE]`, ports 3001/3002 → 4001/4002, Auth row rewritten for Google-only signup.)*

**Done when:** every route family has a status backed by evidence gathered on this commit, and both
docs carry a verification date.

### R2 — Land musicapi on a shared branch  *(done 2026-10-01)*
**Addresses G2.**
- [x] R2.1 Confirm target (merge into `main` vs. a long-lived `musicapi` branch on `origin`).
      *(chosen 2026-10-01 — **merge into `main`**.)*
- [x] R2.2 Reconcile the 67 commits of divergence from `origin/main`; resolve conflicts.
      *(done 2026-10-01 — `git merge-tree --write-tree origin/main integration/musicapi-phase2`
      produced a clean tree: **no conflicts**. The two trees never touched the same files.)*
- [x] R2.3 Push the branch and open a PR so the CI gate (`musicapi-checks`, `musicapi-smoke`)
      runs for the first time on this work.
      *(done 2026-10-01 — branch pushed, **PR #185** opened; all 5 checks green. One CI-only
      regression — a Windows `npm install` had pruned the Linux-only `@emnapi` WASI shims from both
      frontend lockfiles, breaking `npm ci` — fixed in `5d7611ab`. Merged with a merge commit as
      `5d9cdf58`.)*
- [x] R2.4 Verify `main`'s go-live checklist line "committed from `main`" can be ticked.
      *(done 2026-10-01 — ticked in `production-readiness-plan.md`; `origin/main` now contains the
      full `musicapi/` subtree.)*

### R3 — Standardize local configuration
**Addresses G3.**
- [x] R3.1 Fix the canonical worktree's `.env`: add the missing `COOKIE_ENCRYPTION_KEY` (set to the
      value the DB rows are actually encrypted with) and correct `GOOGLE_REDIRECT_URI_*` from
      3001/3002 → 4001/4002. *(done 2026-09-30)*
- [x] R3.2 Document the canonical dev `.env` values in `.env.example` comments (without secrets) so
      new worktrees don't invent a new key.
      *(done 2026-09-30 — header block added; the `COOKIE_ENCRYPTION_KEY` entry now says **do not
      generate a new key** when pointed at the shared `sunoapi` DB, reuse the canonical worktree's.)*
- [x] R3.3 Add a boot-time hint: when cookie decryption fails, log a message naming
      `COOKIE_ENCRYPTION_KEY` and pointing at the rotation runbook (`production-readiness-plan.md` §1.8).
      *(done 2026-09-30 — [cookieCrypto.ts](../src/cookieCrypto.ts) `decryptCookie()` now translates
      the GCM auth failure into an actionable message; [serve.ts](../src/serve.ts) catches the
      boot-time `AccountPool.fromDb()` failure and exits with that hint instead of a raw rejection.)*
- [x] R3.4 Decide the rotation story for the shared key — either freeze it, or run
      [scripts/migrate-cookie-encryption.ts](../scripts/migrate-cookie-encryption.ts) after
      re-encrypting with the new key.
      *(decided 2026-09-30 — **freeze for dev, rotate-together for prod.** Every worktree sharing the
      `sunoapi` DB must reuse one key, so dev freezes it. In production the key is rotated only
      **together with the Suno cookie** (§1.8): re-issuing the cookie means re-entering the row, which
      re-encrypts under the new key. Note the existing script is a one-way *plaintext → encrypted*
      backfill that skips already-encrypted rows — it is **not** a re-key tool, so a pure key swap
      without cookie re-entry is unsupported.)*

### R4 — Replace the in-memory queue with Redis
**Addresses G4.** Only needed before multi-node or durability claims.
- [x] R4.1 Add Redis + a queue library (BullMQ) behind a config flag; keep the DB `jobs` table as
      the system of record.
      *(done 2026-09-30 — `QUEUE_DRIVER=memory|redis`, `REDIS_URL` and `QUEUE_CONCURRENCY` in
      [src/config.ts](../src/config.ts); [src/jobQueue.ts](../src/jobQueue.ts) is the driver
      abstraction (`memory` is a no-op that preserves pre-R4 behaviour). BullMQ owns its socket — a
      plain `ConnectionOptions`, not one shared ioredis client. The `jobs` table stays the system of
      record: **job ids, not payloads, travel through Redis**.)*
- [x] R4.2 Move job execution to workers; keep `trackJob()`/`drainJobs()` semantics and graceful
      `SIGTERM` drain.
      *(done 2026-09-30 — **staged, by design**: a submission is split into a serializable
      descriptor (`payload jsonb`, migration `0012_jobs_payload.sql`, resolved by the
      [src/jobOps.ts](../src/jobOps.ts) registry) and the live `SunoClient`. Pure `(client, id)` ops
      — detail / download / stems / wav / cover / midi / video / lyrics — are converted and can run
      on any worker; composite submits (the music/sounds/lyrics builders, which close over
      builders) keep today's in-process path and today's restart semantics. `onClose` runs
      `queue.drain()` then `queue.close()`; `trackJob()`/`drainJobs()` are untouched.)*
- [x] R4.3 Keep `recoverJobs()` correctness for jobs stranded by a worker crash, not just a restart.
      *(done 2026-09-30 — verified end-to-end against a local `redis:7` on `:6380`: a `running`
      descriptor-backed row stranded by a killed process was re-queued on the next boot
      (`recovered 1 interrupted job(s): 1 re-queued, 0 failed out`) and **adopted by a process that
      never created it** (the job appeared `active` and `:lock`-ed in BullMQ under that process).
      Under the default `memory` driver the old behaviour is preserved — `0 re-queued, 1 failed out`
      → `status=error`, `"Interrupted by server restart."` Rows with no descriptor, and re-queue
      attempts while Redis is unreachable, fall back to the same error-and-finalize path.)*
- [x] R4.4 Update `REQUIREMENTS.md` §Queue to `[DONE]` once verified on sandbox.
      *(done 2026-09-30 — the tech table and §9 Non-functional requirements now read `[DONE]`, with
      the staging caveat noted there and in the [README](../README.md) queue section.)*

### R5 — Sign off the go-live checklist
**Addresses G5.** R5.1 done; R5.2 is user-led.
- [x] R5.1 Tick each line in *"Definition of ready to go live"*, or convert it into explicit
      owner-tagged work.
      *(done 2026-09-30 — checklist rewritten in `production-readiness-plan.md`: 5 ✅, 2 `[~]` with a
      named owner — "committed from `main`" → **R2 (GATED)**; "secrets rotated" → **user/ops**; and
      "smoked on sandbox" → **R1.2** for the live-Suno half.)*
- [ ] R5.2 Close `1.8`: rotate the user-controlled provider secrets (Suno cookie, Google client
      secret, 2Captcha key, Telegram token, Turnstile, B2, SMTP, VPS password) per the runbook.

### R6 — Add the missing root README
**Addresses onboarding.**
- [x] R6.1 Document the 3-process local recipe (ports, required env, migrate, start order, health
      checks) — see [`README.md`](../README.md). *(done 2026-09-30)*

### R7 — Prune the worktree sprawl  *(done 2026-10-01)*
**Addresses G3's root cause.** Destructive to local state — never run without explicit approval.
- [x] R7.1 Inventory the 43 `MusicGenerator-musicapi*` worktrees; map each to a branch and whether
      its work is already in `integration/musicapi-phase2`.
      *(done 2026-10-01 — 42 of the 43 are fully merged into `origin/main` with **zero** uncommitted
      changes and nothing `prunable`; only `-integration` itself is the live tree.)*
- [x] R7.2 Report the archive/delete candidates and their commit status **before** removing anything.
      *(done 2026-10-01 — every candidate appears in `git branch --merged origin/main`; total
      reclaim measured at **13.3 GB**; flagged that 12 worktrees held a non-canonical `musicapi/.env`
      (`COOKIE_ENCRYPTION_KEY`, G3) and that `-billing` sat at the baseline `3117ea6b`.)*
- [x] R7.3 After approval, remove merged/abandoned worktrees and delete the matching local branches.
      *(done 2026-10-01, on the user's explicit "Archive .env, then remove all 42" — 12 `.env` files
      archived to `_musicapi-env-backup-2026-10-01/` outside any repo; **42 worktrees removed** and
      **42 local branches deleted**. Two removals exited `255` on a Windows file lock after git had
      already dropped the registration and branch; the orphaned directories were deleted manually.
      Result: **56 → 14** worktrees (musicapi **43 → 1**), local branches **97 → 55**, **13.3 GB**
      reclaimed, `git worktree prune -n -v` empty. The 13 non-musicapi worktrees were left
      untouched.)*

### R8 — Fix the deploy restart footgun
**Addresses G7.**
- [x] R8.1 Change the units installer to `systemctl enable` + an unconditional `systemctl restart`
      so a redeploy always picks up the new `dist/serve.js`.
      *(done 2026-09-30 — the target is **`scripts/deploy/systemd/install_musicapi_services.sh`** at
      the **worktree root** (one level above `musicapi/`), not `camxora-musicapi-remote.sh`; a
      repo-wide search proved the latter never calls `systemctl enable --now`. Applied to the
      canonical `-integration` worktree; the script exists in 22 worktrees, so broader rollout
      belongs after R7.)*
- [x] R8.2 Add a post-deploy assertion that the deployment is actually current.
      *(done 2026-09-30 — after `restart`, every service must report `is-active`; then
      `camxora-musicapi`'s `ActiveEnterTimestamp` must be **newer** than
      `musicapi/dist/serve.js`'s mtime, failing the deploy if the process predates the build.)*

---

## 5. Suggested execution order

```
R3.1 (done)  →  R1 (verify + reconcile)  →  R6 (README)
             →  R8 (deploy fix)  →  R3.2–R3.4 (config hygiene)
             →  R5.1 (checklist)  →  R4 (Redis queue)
             →  R2 (merge, done 2026-10-01)  →  R7 (prune worktrees, done 2026-10-01)
```

Rationale: verification (R1) is cheap, unblocks trust in every other claim, and needs nothing from
the user. The two **[GATE]** items (R2, R7) were last because they touch shared history and local
state; both are now done. What remains open is only the user-led **R5.2** (provider secret rotation)
and the quota-blocked **R1.2** (live-Suno success path).

---

## 6. Progress log

| Date | Item | Result |
|---|---|---|
| 2026-09-30 | R3.1 | Local stack booted (4001/4002/4003); `.env` repaired; migrations `0007`–`0011` applied |
| 2026-09-30 | R1.1 | Full-tree sweep against the live core API: **205 routes**; T1 `{"200":6,"400":2,"401":194,"404":1,"405":1,"503":1}`; T2 62/62 `POST` on `/v1/*` + `/api/v1/*` → `400`; **0** genuine not-routed. The lone `404` (`/payments/khqr/confirm-mock/:id`) and the `405`/`503` are intentional, verified in source |
| 2026-09-30 | R1.3 | `ENDPOINT_STATUS.md` rewritten against this worktree: re-dated, path references fixed, **100 → 205** routes, axis A/B split added |
| 2026-09-30 | R1.4 | `REQUIREMENTS.md` corrected: Security + Rate limiting → `[DONE]`, Durability → `[PARTIAL]`, phasing 2/3 → `[DONE]`, ports 3001/3002 → 4001/4002, Auth row → Google-only signup |
| 2026-09-30 | R8 | Deploy footgun fixed in worktree-root `scripts/deploy/systemd/install_musicapi_services.sh`: `enable` + unconditional `restart`, `is-active` assertion, and `ActiveEnterTimestamp` ≥ `dist/serve.js` mtime assertion. **Path in the original plan was wrong** (`camxora-musicapi-remote.sh` never calls `enable --now`) |
| 2026-09-30 | R3.2–R3.4 | `.env.example` gains a canonical-dev header + a "reuse the shared `COOKIE_ENCRYPTION_KEY`" warning; `decryptCookie()` and `serve.ts` now fail with an actionable key-mismatch hint; rotation story decided (freeze in dev, rotate with the Suno cookie in prod; the script is a backfill, not a re-key tool) |
| 2026-09-30 | R5.1 | *"Definition of ready to go live"* reviewed: 5 ✅, 2 `[~]` owner-tagged (R2 / user-ops / R1.2); stale R8 caveat in the Phase 5.1 note corrected |
| 2026-09-30 | R6.1 | `README.md` added: 3-process local boot recipe + env contract + troubleshooting |
| 2026-10-01 | R2.1–R2.3 | **Landed on `main`.** 7 path-scoped commits pushed to `origin/integration/musicapi-phase2`; **PR #185** opened (#168–#170 precedent). `merge-tree` against `origin/main` was clean. One CI-only failure (`npm ci` — Windows `npm install` had pruned the Linux-only `@emnapi` shims from both frontend lockfiles) fixed in `5d7611ab`; 5/5 checks green. Merged with a **merge commit** → `5d9cdf58` |
| 2026-10-01 | R2.4 | Go-live line "committed from `main`" ticked in `production-readiness-plan.md`; G2 marked resolved |
| 2026-10-01 | R7.1–R7.2 | Reconnaissance over the 43 `MusicGenerator-musicapi*` worktrees: 42 fully merged into `origin/main`, all clean, none `prunable`; **13.3 GB** reclaimable; 12 carry a non-canonical `musicapi/.env` (G3). Reported before removing anything |
| 2026-10-01 | R7.3 | On explicit approval: 12 `.env` archived to `_musicapi-env-backup-2026-10-01/`; **42 worktrees removed**, **42 merged branches deleted**, 2 Windows-locked orphan dirs cleaned by hand. **56 → 14** worktrees (musicapi **43 → 1**), branches **97 → 55**, **13.3 GB** reclaimed. Non-musicapi worktrees left untouched by R7. G3 resolved |
| 2026-10-01 | follow-on | Separate user-approved legacy prune (not part of R7): backed up `-preflight-video-merge`'s `.env.production`/`.env.sandbox` to `_legacy-env-backup-2026-10-01/`, then removed **7** merged+clean worktrees (`admin-users-search`, `desktop-renew`, `gpaths`, `lockfix`, `mp3fix`, `preflight-video-merge`, `streaming-tg`) and their **7** merged branches. **14 → 7** worktrees, branches **55 → 47**. The 5 legacy trees holding unmerged or unique uncommitted work were kept |
| — | R1.2 | **Blocked:** needs a decision to spend real Suno quota/credits (P0/P3) |
