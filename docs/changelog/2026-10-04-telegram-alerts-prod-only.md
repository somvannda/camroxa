# Ops Telegram: production-only, deduped, and self-diagnosing

## Summary

Operators were paged by a burst of alerts that were partly noise:

- **Four `failure_rate` pages in ~20 minutes** for one ongoing incident. The
  musicapi alert dedupe fingerprinted on `severity|message`, and the message
  embeds live numbers (`304/403`, the dropping rate, balances), so every
  5-minute evaluation looked like a *new* alert.
- **Four identical `B2 backfill sweep` messages in one minute.** The
  platform-api startup loop runs in every uvicorn worker (`API_WORKERS=4`), so
  the 15-minute sweep (and its alert) ran 4x. The alert also had no cooldown, so
  a chronic 2-WAV failure would page every pass.
- **Sandbox posted to the live channel.** Sandbox and production share the same
  Telegram bot token / chat id, and the musicapi runtime had no way to tell the
  two apart (`NODE_ENV=production` is written on both hosts).

This change makes Telegram delivery **production-only**, pages **once per
incident**, runs the B2 sweep **once per interval**, and puts the **top failure
causes** in the failure-rate alert.

## Product impact

- Sandbox/staging no longer post the ops activity feed (signups, payments,
  spends), the streaming health report, B2 sweep alerts, musicapi `[ALERT]`/
  `[RESOLVED]` pages, or the standalone musicapi healthcheck page.
- A sustained failure-rate spike pages **once**, and again only if its severity
  changes (warning ↔ critical) or it clears (a single `[RESOLVED]`).
- Deploy-induced job interruptions no longer count toward the failure rate, so a
  routine redeploy cannot page ops (the jobs are still logged for users/admins).
- The failure-rate page now names the dominant reasons, e.g.
  `Top causes: captcha_required (9); No healthy account available. (4).`
- The B2 sweep alert is rate-limited (default 6 h) so a persistent transient
  companion-WAV failure cannot page every 15 minutes.

## Technical impact

- `platform_api/services/telegram_ops_alert_service.py`
  - New `_telegram_delivery_allowed()` → `is_production()`, with a raw
    `PLATFORM_ENVIRONMENT` fallback that fails closed.
  - `get_telegram_ops_service()` returns `None` when not production; every caller
    (activity feed, health report, sweep alert, `/stats` poller) already treats
    `None` as unconfigured, so they all no-op.
- `platform_api/services/streaming_upload_service.py`
  - `run_backfill_sweep_periodic(interval_s)` claims a single winner via
    `claim_periodic_report(...)`; `main.py`'s loop calls it instead of
    `run_backfill_sweep()`.
  - The sweep alert claims `B2_BACKFILL_ALERT_*` first, limited to
    `B2_BACKFILL_ALERT_COOLDOWN_S` (default `21600`, env-overridable).
- `platform_api/repositories/streaming_repo.py`: new sweep/alert setting keys and
  advisory-lock ids (`730000005`/`730000006`).
- `musicapi/src/config.ts`: new `environment` (from `MUSICAPI_ENV`, falling back
  to `NODE_ENV`) and exported `isProduction()`.
- `musicapi/src/server.ts`:
  - `sendTelegram()` returns early outside production.
  - `syncAlertState()` dedupes on `type|severity`, not `severity|message`; the
    alert text names the environment.
  - The failure-rate alert groups the window's `jobs.error` values and appends
    the top 3 (`details.top_reasons`).
  - The failure-rate count excludes jobs failed out by a restart
    (`RESTART_INTERRUPT_ERROR`), matching the exclusions in `recoverJobs()` and
    the top-causes query.
- `scripts/deploy/camxora-musicapi-remote.sh`: writes `MUSICAPI_ENV=${MUSICAPI_ENV}`
  into `musicapi/.env`.
- `scripts/deploy/musicapi-healthcheck.sh`: resolves `MUSICAPI_ENV` (falling
  back to `PLATFORM_ENVIRONMENT`) and skips Telegram outside production.
- `musicapi/.env.example`: documents `MUSICAPI_ENV`.
- `scripts/deploy/configure_telegram_ops_sandbox.py`: no longer pings the shared
  channel; the test message is opt-in via `SANDBOX_TELEGRAM_PING=1`.

No schema change. The sweep/alert claims use the existing `system_settings` KV
table.

## Failure spike — investigation

The `failure_rate` pages tracked a burst that started shortly after the
20:00-ish deploy and drained out of the 60-minute window over the next ~30
minutes (failed counts 304 → 269 → 242 → 211 while totals stayed ~400), i.e. a
one-off burst, not a sustained generation outage.

The most likely cause is the deploy itself: musicapi runs the **in-memory**
queue (`QUEUE_DRIVER` is unset), so on restart `recoverJobs()` marks every still
`pending`/`running`/`streaming` job as `error` — `"Interrupted by server
restart."` — and finalizes each into `usage_logs`, which the failure-rate alert
then counted. A deploy with a deep pending backlog produces exactly this burst.
These rows are now excluded from the failure-rate alert (and from its
top-causes), so a routine deploy stays quiet.

Follow-up (not in this change, needs an explicit decision): set
`QUEUE_DRIVER=redis` for musicapi so descriptor-backed jobs are re-queued on
restart instead of failed out (Redis is already installed on the host), and/or
drain in-flight jobs before restart.

## Migration / deploy

- No migration. Sandbox-first deploy.
- After deploying, `musicapi/.env` gains `MUSICAPI_ENV=sandbox|production`;
  `platform_api/main.py`'s sweep loop will run single-winner on the next restart.
- The musicapi host alerts stay quiet until the new `.env` is written — a
  sandbox redeploy is enough to set `MUSICAPI_ENV=sandbox`.

## Tests

- `python -m pytest platform_api/tests/test_telegram_ops_alert_service.py
  platform_api/tests/test_streaming_upload_service.py
  platform_api/tests/test_streaming_health_report.py` → 26 passed.
- `bash -n scripts/deploy/musicapi-healthcheck.sh` and
  `bash -n scripts/deploy/camxora-musicapi-remote.sh` → clean.
- `npm run typecheck` (musicapi) → clean.

## Follow-ups

- Decide on `QUEUE_DRIVER=redis` for musicapi (see above).
- Optionally mirror the top-causes idea onto the admin alerts panel.
