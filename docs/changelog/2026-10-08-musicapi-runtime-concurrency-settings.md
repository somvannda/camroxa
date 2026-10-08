# musicapi: tune Suno concurrency from the admin console

## Summary

The Suno job-concurrency knobs were `.env`-only, so changing them (e.g. raising
`SUNO_MAX_CONCURRENT_PER_USER` from 2 to 8) needed a redeploy. This adds them as
an admin-editable group ("Suno concurrency (jobs)") under Settings →
Integrations, applied to `config` immediately — no restart.

## Product impact

- Operators can change the concurrency caps live from
  `admin.musicapi.camxora.com/admin/settings` → **Integrations → Suno concurrency
  (jobs)**: jobs per account, global max, per-user cap, in-flight per account,
  waiting-queue depth, and the minimum-credits floor.
- Adding Suno accounts still raises the global ceiling automatically
  (`pool.size × jobs-per-account`); the field help text says so, so no manual
  bump is needed.

## Technical impact

- `src/runtimeSettings.ts`
  - New `sunoConcurrency` group in `INTEGRATION_GROUPS` (rendered automatically by
    the existing generic Integrations UI — no frontend change).
  - `applyToConfig()` now writes `config.suno.{concurrentPerAccount,
    maxConcurrent, maxConcurrentPerUser, maxConcurrentPerAccount, maxQueue,
    minCredits}`, clamped, falling back to a boot-time snapshot
    (`SUNO_CONCURRENCY_DEFAULTS`) so clearing a field restores the configured
    value rather than the last-applied one.
- `src/concurrency.ts` — `ConcurrencyGate`'s `maxQueue` accepts a getter, so the
  waiting-queue bound is re-read per admission (was fixed at construction).
- `src/server.ts` — the gate is constructed with `() => config.suno.maxQueue`.
- The gateway's global ceiling and per-job caps already read `config.suno.*`
  live, so all changes take effect on the next admission/job.

## Migration / deploy

- No DB migration. `app_settings` already stores the `integrations` blob.
- Deploy the API (`--api-only` is enough; the admin UI renders the new group).

## Tests

- `npm run typecheck` (musicapi) → clean.
- Live check after deploy: change a value in Settings → Integrations → Suno
  concurrency, then confirm `GET /admin/system` (`suno.max_concurrent_per_user`
  etc.) and the "/admin/system" "Suno concurrency" card reflect it without a
  restart.

## Follow-ups

- The 10-second per-user request window (`requests_per_window`,
  `RATE_LIMIT_USER_WINDOW_MS`) is still env-only at the global level; per-user
  overrides already exist on the Users page.
