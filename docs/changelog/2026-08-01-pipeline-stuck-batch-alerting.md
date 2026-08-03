# Pipeline stuck-batch detection + admin alert (§8)

**Date:** 2026-08-01
**Status:** implemented locally, not deployed anywhere

## Summary

Implements §8 ("Pipeline failure detection, admin alerting, and retry/recovery") from `docs/PLATFORM_WORKERS_REQUIREMENTS.md`. Today, a batch that silently stalls mid-pipeline (a webhook that never arrives, a crashed background task, an abandoned image job) is only visible to an admin if they happen to have Pipeline Ops open and refresh — there is no proactive detection or push alert. This adds a scheduled scan that finds these batches and pushes a real, throttled WebSocket alert to every admin, following the exact fan-out pattern already used for `admin:abuse_alert`/`admin:low_balance_alert`.

**Important scoping note, discovered mid-implementation:** the "admin pipeline board" (per-channel `stage` derivation, `GET /admin/pipeline/board`, the React "Pipeline Ops" page) that `PLATFORM_WORKERS_REQUIREMENTS.md` described as already existing turned out to be **uncommitted, untracked work-in-progress** sitting in a different, unrelated branch's dirty working tree — not safely available on any committed branch, and not something this feature should depend on. This work was built **branch-isolated and self-contained** instead: detection queries `batches`/`songs`/`suno_tasks`/`image_jobs`/`batch_channel_assets` directly rather than reusing that board's per-role `stage` logic, and there is no admin-portal UI change in this pass (see Follow-ups).

## Product impact

**Before:** a stuck batch (no progress for 15+ minutes) is invisible to admins unless they manually check Pipeline Ops.

**After:** the API scans for stuck batches every 2 minutes (configurable) and pushes a WebSocket event to every admin's connected session the first time a given batch crosses the stuck threshold, then again at most once per 30 minutes (configurable) while it remains stuck. Admins can also pull the same detection on demand via `GET /admin/pipeline/stuck`, without waiting for the next scan or a push event.

**Not yet built:** an admin-portal UI to receive/display `admin:pipeline_stuck_alert` (toast, sound, badge, etc.) — this branch has no WebSocket client infrastructure in the admin portal at all today (confirmed by search; not just missing for this alert specifically). See Follow-ups.

## Technical impact

### Detection

- New `BatchRepository.list_stuck_batches(min_age_seconds, limit)` — a single SQL query, not a per-role, filesystem-aware "stage" computation:
  - Considers only non-terminal batches (`status IN ('pending', 'processing', 'partial')`).
  - "Activity" = `GREATEST()` of the batch row's own `updated_at` and the most recent `updated_at` across every `songs`/`suno_tasks`/`image_jobs`/`batch_channel_assets` row belonging to that batch.
  - A batch is excluded (not stuck) once **every** channel role it's actually configured for (`ok_profile_id`/`alt_profile_id`) has a `batch_channel_assets` row with `pipeline_complete = true`. A configured role with no such row yet is treated as "still running," not instantly "stuck" — it only surfaces once it's also past the age threshold with no activity.
  - Validated directly against the real local schema in a rolled-back transaction (this codebase's established convention for `batch_repo` SQL — no repo-level test harness exists here; confirmed via a 0-row result cross-checked against the local DB's actual batch data, which has no non-terminal batches to match).

### Alerting

- New `PipelineStuckAlertService` (`platform_api/services/pipeline_stuck_alert_service.py`) — mirrors `AbuseAlertService` exactly: a Redis `SET NX EX` cooldown key per batch_id prevents re-alerting on every scan cycle while a batch remains stuck; resolves admin user IDs via the same `role = 'admin'` provider pattern; pushes `admin:pipeline_stuck_alert` to each admin via the existing `NotificationService.push()` (in-memory WebSocket registry, falls back to the `notification_queue` table if an admin is offline). Never raises — a scan failure or a single admin's failed push can't crash the scheduling loop or block alerting the other admins.
- Payload: `{kind: "pipeline_stuck", severity, batch_id, user_id, user_email, status, age_seconds, message, ts}`.

### Scheduling

- No dedicated `platform_worker` process exists yet (per the requirements doc), so this runs as an in-process `asyncio.create_task` loop registered in `platform_api/main.py`'s lifespan, sleeping `pipeline_stuck_scan_interval_seconds` (default 120s) between scans. Cancelled cleanly on app shutdown.
- `_DbAdminProvider` (previously defined inline only for the abuse-alert block) was hoisted one scope up so both the abuse-alert and pipeline-stuck-alert wiring share the same admin-ID resolver instead of duplicating it.

### On-demand view

- New `GET /admin/pipeline/stuck` (`platform_api/routers/admin.py`), admin-only, optional `min_age_seconds`/`limit` query params, defaults to the same threshold the scheduled scan uses. This exists so "what's stuck right now" doesn't require waiting for the next scan/alert cooldown — useful today as a raw JSON endpoint, and as the eventual data source for the deferred UI widget below.

### New settings

- `pipeline_stuck_threshold_seconds` (default 900 / 15 min)
- `pipeline_stuck_scan_interval_seconds` (default 120 / 2 min)
- `pipeline_stuck_alert_cooldown_seconds` (default 1800 / 30 min)

## Files touched

- `platform_api/repositories/batch_repo.py` — new `list_stuck_batches()`.
- `platform_api/services/pipeline_stuck_alert_service.py` (new) — `PipelineStuckAlertService`.
- `platform_api/routers/admin.py` — new `GET /admin/pipeline/stuck`, `AdminStuckBatchItem`/`AdminStuckBatchesResponse`.
- `platform_api/main.py` — hoisted `_DbAdminProvider`; new scheduled `_pipeline_stuck_alert_loop()` wired into lifespan startup/shutdown.
- `platform_api/config.py` — 3 new settings (see above).
- `platform_api/tests/test_pipeline_stuck_alert_service.py` (new).
- `platform_api/CHANGELOG.md`.

## Migration / deploy

- No database migration — reads existing `batches`/`songs`/`suno_tasks`/`image_jobs`/`batch_channel_assets` columns only (including `batch_channel_assets.pipeline_complete`, added by migration `075_batch_channel_pipeline_complete`, already present on this branch's base commit).
- No new environment variables required — all 3 new settings have safe defaults; override via the standard `PLATFORM_*` env var naming if tuning is needed later.
- Built on branch `feature/pipeline-stuck-alerts`, in a **new dedicated worktree**, based on `fix/album2-progress-filters`'s latest commit (`7eec7d0`) rather than `main` — that commit was the most recent stable point with `AbuseAlertService`/`NotificationService`/`batch_channel_assets.pipeline_complete` already committed, all of which this feature depends on. Not merged anywhere; not deployed to sandbox or production.

## Tests

- `pytest platform_api/tests/test_pipeline_stuck_alert_service.py -v` → 6 passed (admin fan-out, per-batch cooldown, independent-batch cooldowns, repo-failure resilience, no-op without alert wiring configured, survives a single admin's push failure).
- New `list_stuck_batches()` SQL validated directly against the real local schema in a rolled-back transaction (same technique used for prior `batch_repo` SQL changes in this codebase, since there's no repo-level test harness) — 0 rows returned, cross-checked against the local DB's actual batch table (1 row total, already `completed`), confirming the 0-row result is correct rather than a silent query bug.
- `python -m py_compile` on every changed file — clean.
- **Blocked (pre-existing, unrelated):** `platform_api/tests/test_admin_router.py` (and every other router-collecting test file) fails to even import on this branch — `platform_api/routers/blog_posts.py` uses `status_code=204` with a response model, which the installed FastAPI version now asserts is invalid ("Status code 204 must not have a response body"). This is a pre-existing, already-documented issue (seen identically on other unrelated branches this same day) that predates and is unrelated to this work — it blocks router-level testing of the new `GET /admin/pipeline/stuck` endpoint specifically, but not the service/repo-level logic, which is fully covered above.
- No linter errors on any changed file.

## Follow-ups

- **Admin-portal UI not built this pass.** This branch's admin portal has zero WebSocket client infrastructure today (no `abuse-alert-listener.tsx` or equivalent, confirmed by search) — building a toast/notification listener for `admin:pipeline_stuck_alert` without a "Pipeline Ops" board to deep-link into (also not committed anywhere yet) would have limited standalone value. Recommend building the WS listener + board UI together once the (apparently in-progress elsewhere) pipeline board page is committed to a stable branch, using `GET /admin/pipeline/stuck` as the data source and `admin:pipeline_stuck_alert` as the live-update trigger.
- Fix the pre-existing `blog_posts.py` / FastAPI 204-with-response-model collection error so router-level tests (including one for the new endpoint) can actually run — unrelated to this feature, flagged for separate cleanup (third time this exact issue has blocked router testing this session, across three different branches).
- "Stuck" here is batch-level, not per-channel-role — a batch with one finished role (OK) and one genuinely stuck role (ALT) is still flagged, which is correct/conservative, but the alert payload doesn't yet say *which* role is the problem. Splitting this per-role would need the same kind of per-role activity join the (uncommitted) admin pipeline board does — deferred since that logic isn't stably available yet.
- §8 also calls for folding the existing Suno-reconcile sweep and orphan-video-charge-reconcile sweep into the same "housekeeping" scheduled lane once `platform_worker` exists — not done here since neither of those exists as committed, schedulable code on this branch's base either (the orphan-video loop found in an earlier session's exploration was also uncommitted WIP elsewhere). Left as a `platform_worker`-era consolidation, not a blocker for shipping stuck-batch alerting on its own.
- No cross-branch merge plan yet — this was intentionally built branch-isolated per this session's branch-isolation rules; whoever owns the admin-pipeline-board WIP and this alerting feature will need to reconcile the two "stuck" detection approaches (this one is DB-only and coarse-grained/batch-level; that one is stage-aware and per-role) when both eventually merge.
