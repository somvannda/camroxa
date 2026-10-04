# musicapi: alert when the Suno concurrency backlog gets deep

## Summary

The concurrency gate introduced in #237 (and bounded in #242) can still have many
jobs waiting for a slot when demand outstrips the account pool. Nothing surfaced
that to operators. This adds a fourth alert condition — **queue backlog depth** —
alongside low credits, the captcha alerts, and failure rate.

## Product impact

- When `suno.waiting` reaches the configured `queue_backlog_depth` (default 50),
  the admin panel raises a **queue_backlog** alert and the ops Telegram channel
  gets a `[ALERT]` (with a `[RESOLVED]` when it drains), using the same
  dedupe-on-change behavior as the other alerts.
- Severity is `warning` at the threshold and `critical` at 2× the threshold.
- Directly relevant to the planned 2-Premier-account switch: a growing backlog is
  the earliest signal that the pool is saturated.

## Technical impact

- `src/server.ts`:
  - `AlertSettings` gains `queue_backlog_depth` (default 50, `0` disables);
    `coerceAlerts`/`mergeAlerts` validate and persist it like the other numeric
    thresholds.
  - `AlertType` gains `"queue_backlog"`; `evaluateAlerts()` reads
    `sunoSlots.stats()` and emits the alert plus a `summary.queue_backlog` count.
  - Existing `low_credits` already covers Suno credit depletion (live per-account
    balance), so no separate burn-rate alert was added.
- `web-admin/app/admin/settings/page.tsx`: the Alerts tab gains a
  **Queue backlog depth** field and a **Queue backlog** status stat.

No schema change. The settings live in the existing `app_settings.alerts` JSON.
Rebased onto the post-#241 alert system (`captcha_no_solver`/`captcha_balance`).

## Files touched

- `musicapi/src/server.ts`
- `musicapi/web-admin/app/admin/settings/page.tsx`
- `docs/changelog/2026-10-04-musicapi-alert-queue-backlog.md` (this file)

## Migration / deploy

- No migration. Deploy via the normal sandbox-first chain.

## Tests

- `npm run typecheck` (musicapi) → clean.
- `npm run build` (web-admin) → TypeScript clean, all pages generated.
- Live verification (sandbox) pending the next deploy: raise the backlog with a
  burst and confirm the alert fires in `/admin/alerts`.

## Follow-ups

- Optional: per-account monthly Suno-credit burn projection (the low-credit alert
  is the current proxy).
