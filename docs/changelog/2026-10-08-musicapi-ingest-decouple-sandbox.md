# musicapi: release the Suno slot before durable media ingest — **SANDBOX ONLY**

**Status (important):** deployed to the **sandbox** VPS only. **NOT on `main`, NOT in
production.** This exists so the change can be observed in sandbox before a
deliberate production promotion.

- Branch: `feat/musicapi-decouple-ingest`
- Commit: `a140cd97` (base: `9e0aeac3` — the 429-cooldown commit already on `main`)
- Deployed to sandbox: 2026-10-08
- Production: **unchanged** (still runs the inline finalize behavior)

## What changed

`withSunoSlot()` used to wrap the entire retry implementation including
`finalizeJob()`. For a completed audio job `finalizeJob()` runs
`ensureDurableAudio()` — the download-from-Suno + copy-to-B2 step — so the job
held a **Suno concurrency slot for the whole media upload**, blocking other jobs.

Now:

- `withSunoSlot<T>()` returns `boolean` — `true` when `fn` ran, `false` when the
  backlog was full (that path already finalizes internally).
- The `runClipJobWithRetry` / `runResultJobWithRetry` wrappers call
  `finalizeJob(job)` **after** the slot is released:
  ```ts
  const ran = await withSunoSlot(job, () => runXJobWithRetryImpl(...));
  if (ran) await finalizeJob(job);
  ```
- The `*Impl` functions no longer call `finalizeJob` themselves.

Finalize still runs **exactly once** per job, and billing/refund/callback
semantics are unchanged.

**Effect:** the Suno slot is released as soon as generation finishes; the B2 copy
runs afterwards, so more jobs can be in flight at once (higher throughput, shorter
queue waits).

## Risk / what to watch

- This changes **when** `finalizeJob` runs relative to slot release. If a job
  terminates via an unexpected throw, finalize behaves as before (skipped) — no
  regression, but worth watching.
- Watch on sandbox: jobs still reach `complete`/`error` with correct credits and
  callbacks; the `/admin/jobs` and Incidents pages show normal job flow; no
  double-refund or missing callbacks.

## How to trace this later

- `git branch -r | grep decouple` → `feat/musicapi-decouple-ingest`
- This file: `docs/changelog/2026-10-08-musicapi-ingest-decouple-sandbox.md`
- Sandbox host `46.250.235.83`, service `camxora-musicapi` — check
  `/opt/camxora/repo/musicapi/src/server.ts` for the `if (ran) await finalizeJob(job);`
  wrappers.

## Promote to production later

1. Confirm sandbox looks good (jobs complete, credits/callbacks correct).
2. `git checkout main && git merge --ff-only feat/musicapi-decouple-ingest && git push origin main`
3. `python scripts/deploy/deploy_musicapi_production.py --yes --api-only`
4. Verify production `{"ok":true,...}` and a generation end-to-end, then delete
   this sandbox note.
