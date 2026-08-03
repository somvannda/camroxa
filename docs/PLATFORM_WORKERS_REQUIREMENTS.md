# Platform Workers & Queue System — Requirements

**Date:** 2026-08-01
**Status:** requirements gathering (no implementation yet)
**Related docs:** [`PRODUCTION_INFRASTRUCTURE_PLAN.md`](./PRODUCTION_INFRASTRUCTURE_PLAN.md) (§7–13 already propose a `job_queue` table + `platform_worker` process — this doc extends that plan to cover the full set of worker types requested, calls out what's already built vs. missing, and adds areas the infra plan doesn't cover), [`PLATFORM_GAPS_AND_RECOMMENDATIONS.md`](./PLATFORM_GAPS_AND_RECOMMENDATIONS.md) (confirms "Background job queue / worker split" is still **Phase C — not started** as of 2026-07-15), `docs/changelog/2026-08-01-production-api-single-worker-bottleneck.md` (the immediate symptom that triggered this — production API timeouts traced to a single uvicorn worker doing everything).

## 0. Why this document exists

You asked for a "designed worker system" covering 12 areas (drafting, Suno download, image gen, video export, video merge, credit ops, streaming upload, failure/alerting, key pools & rate limits, status/progress, cross-worker coordination, and a `platform_worker` queue process). Rather than assume, four research passes were run against the actual codebase to establish **what already exists today** for each area before proposing anything new. The findings below separate:

- ✅ **Already built** — don't rebuild it, just wire it into the queue.
- ⚠️ **Partially built** — works, but has a specific gap.
- ❌ **Not built** — genuinely new work.

**Headline finding:** there is currently **no job queue and no separate worker process anywhere in `platform_api`.** Every "worker" today is either an in-process `asyncio.create_task()` / FastAPI `BackgroundTasks` call running inside the single uvicorn process, or (for image/YouTube) an in-process `asyncio.Semaphore`-bounded pool — still inside that same process. This is exactly why a busy batch can starve unrelated simple requests (the timeout issue fixed by bumping to 2 uvicorn workers). Bumping worker count is a stopgap; it does not change the fact that heavy work and HTTP serving share the same process(es).

The desktop app is a separate, better story: local export/merge already run as a genuine thread-orchestrated worker pool with configurable concurrency.

---

## 1. Draft workers (song title / album / lyrics)

**Your ask:** multiple workers for drafting.

**Today:**
- Runs via `BatchService.orchestrate_drafts` inside a FastAPI `BackgroundTask` on the single uvicorn process.
- Songs in a batch are drafted **strictly sequentially** — `for song in songs: await self._generate_song_draft(...)` (`platform_api/services/batch_service.py:1532`). There is no parallelism at all today, not even in-process.
- Standalone `/generation/draft` runs synchronously in the request.
- Per-song: album → title → lyrics, each with its own retry budget (album ×2, title ×2, lyrics ×3) and a provider fallback chain (key pool already handles multi-key failover for DeepSeek/SLAI).
- Billing: charged per slot before the LLM call, refunded on failure — already correct and atomic.

**Gap:** a 20-song batch drafts one song at a time. This is a real user-facing latency problem, separate from the HTTP-timeout issue — nothing to do with worker starvation, purely serial work.

**Requirement:** `job_type=draft`, one job per song, claimed by N worker lanes (infra plan suggests 4–6, I/O-bound). Must preserve the existing per-slot billing charge/refund exactly as-is — draft billing is correct today and should not be re-architected, only re-hosted into a job handler.

---

## 2. Suno submit + MP3/WAV download workers

**Your ask:** multiple workers for downloading Suno MP3 (WAV later).

**Today, and this needs to be split into two different things people conflate:**

**(a) Suno *submission*** (server → Suno API): sequential per batch today, same as drafts (`_submit_song_to_suno`, one at a time). Completion is via **Suno's webhook callback** to `/callbacks/suno`, not polling — good, keep this. A reconcile poll exists as a *fallback* for when callbacks are missed (`reconcile_pending_suno_tasks`), triggered reactively when the client reads pending downloads or history — not a scheduled sweep.

**(b) MP3 *download*** — this actually happens **client-side on the desktop app**, not on the server. The server never downloads the MP3; it stores the Suno CDN URL, and the desktop's `MusicDownloadSyncWorker` (already hardened this week for disk-space and 0-byte integrity) pulls it directly from Suno's URL to the user's local run folder. "Multiple workers for downloading" on the desktop side is governed by `perfMusicWorkers` (1–5) — already exists.

**Gap:** Suno *submission* has no parallelism (same issue as drafts), and the reconcile-poll fallback only runs reactively, not on a schedule — a task whose webhook silently never arrives can sit stuck until the user happens to open Progress or Downloads.

**Requirement:**
- `job_type=suno_submit`, one per song, claimed by 3–4 lanes, gated by the outbound rate limiter (already designed in infra plan §9: 20 req/10s per Suno key).
- A scheduled reconcile job (e.g. every 2–5 min) sweeping `suno_pending` tasks older than N minutes, instead of only reconciling on-read.
- WAV: same submit/callback/reconcile pattern once Suno's WAV endpoint is production-ready; no new mechanism needed, just extend the same job type.

---

## 3. Image generation workers (background + thumbnail)

**Your ask:** multiple workers for images.

**Today — this is the most mature piece of the whole system:**
- Real `asyncio.Semaphore`-bounded worker pool per run (`perfImageWorkers`, clamped 1–8, default 4).
- Job claiming via `FOR UPDATE SKIP LOCKED` on `image_jobs` — this is already a lightweight queue, just missing the "process" boundary (it drains in-process via `asyncio.create_task`, capped at 80 iterations).
- Proper job-level auto-retry (up to `image_job_max_attempts`, default 3) with non-retryable-error detection (quota/credit failures don't get retried).
- Dependency ordering already handled (thumbnails wait on background image via `DependencyPendingError`, doesn't burn a retry attempt).
- SLAI has its own process-wide rate limiter (max_concurrent=1, min_interval=5s) since SLAI is stricter than Fal.

**Gap:** it's a fully-formed job system already, just living inside the API process instead of `platform_worker`. Moving it out is close to a lift-and-shift, not a redesign.

**Requirement:** migrate `image_jobs` claim loop as-is into `platform_worker` (infra plan §13 Phase 5 already scopes this). Keep `perfImageWorkers` as the lane concurrency knob. No behavior change needed beyond hosting.

---

## 4 & 5. Video export + merge workers (local/desktop)

**Your ask:** confirm these are done right.

**Confirmed — yes, mostly right, with one real gap:**
- Export: thread-orchestrated pool of `subprocess.Popen` jobs, `videoExportWorkers` (1–10), FIFO queue per batch, GPU contention managed by a global `ExportGate` (Auto-Video path) + spawn throttle (1.2s stagger). Video-page path counts active jobs directly rather than using the gate — works today because Auto-Video refuses to start while a Video-page batch is active, but it's two different enforcement mechanisms for the same resource, worth unifying later.
- Merge: threaded, `perfMergeWorkers` (1–2), correctly **does not** use NVENC (stream-copy first, libx264 fallback) — right call, since merge is a different bottleneck than export.

**Real gap:** no automatic retry on a single failed item.
  - Video-page batch: continues past a failed track (good), but never retries that track — user has to notice and manually re-run just that item.
  - Auto-Video: **fails the entire channel** on the first track's exception — one bad file can waste an otherwise-successful batch of 9 other tracks.

**Requirement:** add per-item retry (e.g. 1 automatic retry with backoff before marking failed) to both paths, and change Auto-Video from fail-fast-the-whole-channel to skip-and-continue (matching the Video-page behavior, which is the correct model — this directly relates to your Feature 4 recovery-flow request from the previous session: resume without re-drafting).

---

## 6. Credit / wallet / plan-quota workers

**Your ask:** multiple workers for credit operations and plan quota.

**This is the one area where "add more workers" is the wrong instinct — flagging this explicitly before we design anything.**

**Today:**
- Credit deduct/refund/quota-increment are **synchronous, in-request, DB-atomic** operations (conditional `UPDATE ... WHERE balance >= $2 RETURNING`, and `SELECT ... FOR UPDATE` for refunds/quota rows). They gate *before* the paid work starts.
- This is intentionally not a queue: you cannot let a batch start doing paid work before knowing the charge succeeded, and a queued/eventual-consistency credit system would open a double-spend or overdraft window.
- Async operations (Suno success/failure arriving later via webhook) already use a stash-and-pop pattern (`stash_operation_charge` / `pop_operation_charge`) so the eventual refund is correctly tied to the original charge — this is the right pattern for "charge now, reconcile later," already implemented.

**Requirement:** do **not** turn credit ops into queued jobs. Keep them synchronous and DB-atomic exactly as today. What *can* move to a worker: the **periodic reconciliation sweep** that already exists for orphaned local-video/merge charges (runs every 900s in-process today) should become one of the scheduled jobs in `platform_worker` alongside the new stuck-Suno sweep from §2, not a "credit worker pool." If quota/credit checks ever become a measured bottleneck under real concurrency, the fix is read-replica/connection-pool tuning, not parallelizing the deduction itself.

---

## 7. Streaming (B2) upload workers

**Your ask:** multiple workers for uploading streaming jobs.

**Today — the weakest link found in this whole review:**
- Fire-and-forget `asyncio.create_task()` per completed song/cover, no semaphore, no concurrency cap at all (unlike image jobs, which do have one).
- **No automatic retry.** A failed upload just sits at `status=failed`; only a manual admin retry endpoint exists, and only for `mp3_*` job kinds — cover-image uploads have no retry path at all.
- The Suno-URL-refresh-for-upload path uses a simplified single-key Suno poll (`ORDER BY priority DESC LIMIT 1`) that bypasses the full key-pool failover wrapper used everywhere else — inconsistent with the rest of the system and a real gap if that one key gets rate-limited.

**Requirement:** `job_type=storage_upload`, proper lane concurrency (infra plan suggests 3–4), job-level auto-retry matching the image-job pattern (attempt counter, backoff, non-retryable classification), and route the Suno URL refresh through the standard key-pool wrapper instead of the single-key shortcut.

---

## 8. Pipeline failure detection, admin alerting, and retry/recovery

**Your ask:** multiple workers to check for failures across users' pipelines and alert/enable recovery.

**Today:**
- "Stuck" (age ≥ 15 min, non-terminal stage) and "Failed" are computed **on read** when the admin board endpoint is called — there is no background scanner producing this proactively.
- Admin alerting is a hybrid: a Redis-debounced WebSocket "board changed" ping fires after specific events (batch status refresh, streaming success), which tells the admin portal to re-fetch; plus a 60s safety poll as backup. There is **no alert specifically for "batch X has been stuck ≥15m"** — admins only see it if they have Pipeline Ops open or happen to refresh.
- Suno-specific reconcile exists but is reactive (triggered by user reads), not scheduled.
- Retry/waive endpoints are solid (dual-control for platform-paid waives, retry-cost estimation) — the *recovery* mechanics are good, the *detection* is the gap.

**Requirement:**
- A scheduled `platform_worker` job (e.g. every 1–5 min) that scans for batches crossing the stuck threshold and **pushes** a real alert (not just a debounced "something changed" ping) — reuse the existing `admin:low_balance_alert` / `admin:abuse_alert` pattern, which already does real push-with-payload alerting, as the template for a new `admin:pipeline_stuck_alert`.
- Same scheduled job should also run the Suno-reconcile and orphan-charge sweeps from §2 and §6 — one "housekeeping" lane in the worker, not three separate schedulers.
- This directly extends the resume-pipeline design from the previous session (re-download-only recovery without re-drafting) — the alert should link straight to the specific stuck batch/song so admins (or eventually users) can trigger that recovery flow immediately.

---

## 9. API key pool assignment + rate limiting under concurrent users

**Your ask:** multiple workers for assigning key pools and rate limits when multiple users hit at once.

**Best news in this whole review: this already exists and is production-grade.**
- Real DB+Redis-backed `KeyPoolService` covering Suno, Fal, SLAI, OpenAI, DeepSeek, CALA — round-robin or priority selection, automatic failover on HTTP 429 (rate-limited → cooldown → try next key) and 402/403 (exhausted → try next key), up to 3 keys tried per call.
- This is exactly the "assign a key from the pool per concurrent user" mechanism you're asking for — it's not a single shared key, and it's not something that needs new workers, it needs to be **called consistently everywhere** (see the two exceptions below).

**Gaps (small, not "not built"):**
- The Suno-URL-refresh-for-streaming-upload path and its LRC-fetch sibling bypass the pool's failover and just grab one active key directly.
- CALA gateway uses `get_key()` without `execute_with_failover()`.
- There is genuinely no **outbound** rate limiter yet (the ingress per-user HTTP rate limiter is separate and already exists) — i.e. nothing today stops the platform itself from bursting 50 Suno submits in one second and getting the whole key 429'd. This is exactly what infra plan §9 already designs (`OutboundRateGate`, Redis token bucket per provider key, 20 req/10s for Suno, etc.) — not started yet, but fully specified.

**Requirement:** (1) fix the two bypass paths to use the standard key-pool wrapper, (2) implement the already-designed `OutboundRateGate` from the infra plan, (3) no new "key pool worker" needed — the pool itself is a shared service called from whichever worker lane is making the outbound call, not a worker of its own.

---

## 10. Status / progress checking and updates

**Your ask:** multiple workers for status checking and progress updates.

**Today:**
- `GET /progress` and `GET /admin/pipeline/board` compute progress **live from the DB** on every call — correct source of truth, no caching bugs, but means "progress checking" is not a worker at all today, it's a read path. That's actually fine — it doesn't need to become a worker.
- Real-time push exists only for discrete events (`suno_task_completed` to the song's owner, `admin:pipeline.board.changed` invalidation ping to admins) — not a continuous progress-percentage stream.
- **The desktop Progress page does not use the API's `/progress` at all** — it builds rows from the local SQLite/DB, separately from whatever the server thinks. This is worth being aware of: server-side and desktop-side "progress" can theoretically disagree (e.g. after the resume-pipeline / change-run-folder recovery flow from the previous session, since that's a desktop-local operation the server doesn't know about).

**Requirement:** no new worker type needed for polling/computing progress — it's correctly on-read today. What *is* worth adding: push a WebSocket event when a job (§1–§7 above) transitions state in the new job queue, so the admin board's "changed" ping becomes accurate/immediate instead of relying on the 60s safety poll, and so a future desktop WS listener (not wired up today) could get live updates instead of only local-DB-based progress.

---

## 11. Coordination — how do all these workers avoid stepping on each other?

**Your ask:** what mechanism ensures workers don't overlap/conflict.

**Today's actual mechanisms (good foundation, no need to invent something new):**
- `SELECT ... FOR UPDATE SKIP LOCKED` already used correctly for image-job claims, YouTube upload-job claims, content-pool reservation — this is the right, standard Postgres pattern for "many workers, one queue, no double-claim," and it's already proven in this codebase for 2+ job types.
- Credit/wallet rows use `FOR UPDATE` for the balance-add/refund path and a conditional `UPDATE` for deduct — both already race-safe.
- **No** Postgres advisory locks and **no** Redis distributed locks (Redlock) exist anywhere — the two SETNX usages found are debounce/cooldown timers, not mutual exclusion.
- Idempotency is currently narrow: Suno submissions dedupe via a request-content hash (good, prevents accidental double-submit-and-double-charge for identical requests), but there's **no general `Idempotency-Key` mechanism** for batch create or admin retry endpoints — a network retry of a `POST /batches` today can theoretically create a duplicate batch.

**Requirement for the new `job_queue`:**
1. **Claiming:** extend the existing `FOR UPDATE SKIP LOCKED` pattern to the new `job_queue` table exactly as the infra plan already specifies (§7.3 schema, §7.5 fair scheduling) — no new locking primitive needed, just apply the pattern that already works for `image_jobs`.
2. **Per-user fairness:** infra plan already proposes a per-user active-job cap (max 2 concurrent running jobs per user) so one power user's 50-song batch can't starve everyone else — this is the "no overlap between users" half of your question, and it's already designed, just not built.
3. **Worker-instance safety:** with `platform_worker` running 1–2 processes, each claim must be tagged with a worker identity (`PLATFORM_WORKER_ID`, already in the infra plan's env var list) and a heartbeat/lease timeout, so a crashed worker's claimed-but-abandoned jobs get reclaimed automatically (this specific piece — stale-claim reclaim — is not yet in the infra plan's schema and should be added: a `claimed_at` + `lease_seconds` column, with a periodic "reclaim jobs where `claimed_at < now() - lease_seconds` and `status='running'`" query, run by the same housekeeping lane as §8).
4. **Idempotency:** add a general `Idempotency-Key` header support on `POST /batches` (and other job-creating endpoints) so client retries can't double-create work — currently missing.
5. **Cross-job-type coordination:** the infra plan's per-song job chain (draft → suno_submit → storage_upload → image) is already ordered correctly by having each job's completion handler enqueue the next job type — this "job chaining" is itself the coordination mechanism between different worker *types*, no separate broker needed.

---

## 12. `platform_worker` — the process everything above should live in

**Your ask:** confirmed you want this.

The infra plan already fully specifies this (§7–9, §13 phases): a PostgreSQL `job_queue` table, a separate `platform_worker` process claiming jobs via `SKIP LOCKED`, per-lane concurrency (draft/suno/image/storage), and an outbound rate gate. **Nothing in this document changes that design** — it adds:

- Two new job/lane types the infra plan didn't originally scope: `pipeline_housekeeping` (stuck-batch alerting, Suno reconcile sweep, orphan-charge sweep — §2, §6, §8 above) and confirms `storage_upload` needs the same auto-retry treatment as `image` (§7).
- The stale-claim/lease-reclaim mechanism (§11.3) as a schema addition to the proposed `job_queue` table.
- Two key-pool bypass fixes and the (already-designed-but-unbuilt) `OutboundRateGate` should ship together with the worker migration, not after — otherwise the worker will immediately reproduce the "burst and get rate-limited" problem the gate exists to prevent.
- Confirmation that credit ops (§6) and progress reads (§10) deliberately **stay out** of the job queue — they're either safety-critical synchronous operations or on-read computed views, not queueable work.

---

## Summary table

| # | Area | State today | What's needed |
|---|------|-------------|----------------|
| 1 | Draft workers | ❌ sequential, in-process | New `draft` job type, parallel lanes |
| 2 | Suno submit + MP3 download | ⚠️ submit sequential; download already parallel (desktop, `perfMusicWorkers`) | New `suno_submit` job type; scheduled reconcile sweep |
| 3 | Image generation | ✅ real semaphore pool + retry, just in-process | Lift-and-shift into `platform_worker`, keep as-is otherwise |
| 4 | Video export (local) | ✅ thread pool + GPU gate | Add per-item retry |
| 5 | Video merge (local) | ✅ thread pool, correct CPU-only encode | Add per-item retry; stop Auto-Video fail-fast-whole-channel |
| 6 | Credit / quota ops | ✅ synchronous DB-atomic — correct as-is | **Do not** queue; only the periodic orphan-reconcile sweep moves to the worker |
| 7 | Streaming (B2) upload | ❌ unbounded, no retry, bypasses key pool | New `storage_upload` job type with concurrency cap + retry + proper key pool use |
| 8 | Failure detection / admin alerting | ⚠️ on-read only, no proactive alert | Scheduled stuck-batch scan + real push alert (reuse abuse-alert pattern) |
| 9 | Key pool + rate limiting | ✅ pool exists and is solid; ❌ outbound rate gate not built | Fix 2 bypass paths; build `OutboundRateGate` (infra plan §9, unbuilt) |
| 10 | Status/progress | ✅ correct on-read design | No new worker; add WS push on job-state transitions |
| 11 | Coordination | ✅ `FOR UPDATE SKIP LOCKED` proven; ❌ no lease/reclaim, no general idempotency key | Apply existing pattern to `job_queue`; add lease/reclaim + `Idempotency-Key` |
| 12 | `platform_worker` process | ❌ does not exist | Build per infra plan §7–13, plus the additions above |

---

## Open decisions before design/implementation starts

1. **Scope/sequencing:** the infra plan's own phases (§13) bundle the job queue work together with a much larger B2/CDN storage migration. Do we want to decouple them — build `job_queue` + `platform_worker` first (fixes the timeout/stability problem directly) and treat storage-to-B2 as a separate, later initiative? (Recommended: yes, decouple — the storage migration is unrelated to why the API is unstable.)
2. **First job types to migrate:** given the housekeeping/alerting gap (§8) is the most operationally painful one right now (silent stuck batches), should that be first, ahead of the infra plan's original Phase 2 (draft jobs)? Or follow the infra plan's original order?
3. **Worker process count:** infra plan suggests 1–2 `platform_worker` processes. Given the box currently sits at ~1 of 6 cores used even with uvicorn at 2 workers, is there any reason not to start with 2 worker processes immediately rather than 1?
4. **Lease/reclaim timeout values:** need per-job-type numbers (a stuck `draft` job vs a stuck `storage_upload` job have very different reasonable timeouts).
5. **Alerting channel for §8:** reuse the existing WS `admin:*_alert` pattern only, or also want email/Slack for stuck-pipeline alerts given these are revenue/support-impacting?

Once these are answered, the next step is a proper phased implementation plan (schema migration, `platform_worker` skeleton, first job type end-to-end, then the rest) — this document intentionally stops at requirements, not implementation, per your request.
