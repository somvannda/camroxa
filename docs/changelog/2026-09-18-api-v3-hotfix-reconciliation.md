# API v3 cutover — production hotfix reconciliation

**Date:** 2026-09-18
**Branch:** `release/api-v3-cutover`
**Surfaces:** platform_api (tests)
**Status:** implemented; sandbox rehearsal pending

## Summary

Reconciled production-only hotfixes into `main` so the `/api/v3` cutover deploy does not revert live fixes. Production had drifted from `main` in **both** directions (147 hotfix backups; 65 divergent API files, ~4,600 lines).

Strategy: **reconcile-then-deploy** — merge the unmerged hotfix branches, port prod-only operational hotfixes onto `main`, and drop prod-only features that were never merged or were intentionally reverted.

## What was done

### Branches merged
- `fix/streaming-capture-telegram` (contained `fix/suno-audio-recovery-b2`, `feat/admin-retry-all-streaming`).
- Adds Alembic **120_suno_download_unavailable**, **121_upload_job_permanent_failed** (new head = 121) and B2 capture / auto-retry / Suno recovery code.

### Prod-only hotfixes ported onto `main`
- `streaming_upload_service.py`: web-music WAV upload scheduling, B2 idempotency, non-retryable permanent-failed marking.
- `repositories/batch_repo.py`: `list_reconcilable_suno_tasks` uses the `NOT EXISTS stream_tracks` predicate.
- `services/batch_service.py`: fail-fast `preflight_quotas_and_balance` on Suno retry.
- `clients/suno_client.py`: HTTP 409 WAV handling.
- `services/v2/credit_service.py` + `models/products.py` + `services/billing_calendar.py`: monthly free-reset cadence.
- `services/v2/subscription_service.py`: tz-aware `datetime.now(timezone.utc)` in `reset_quota_if_needed` (fixes naive/aware compare against `TIMESTAMPTZ`).
- `services/telegram_ops_alert_service.py`: `download` alerts + `send_html(reply_markup=...)`.
- `services/content_license_service.py`: `select_play_lane` (play-lane key mismatch).
- `routers/web_music.py`: accept `vocal_gender="both"`; request logging.
- `services/web_music_service.py`: free users may download their own tracks; generate step logs.
- `routers/callbacks.py`: schedule web-music WAV + LRC(ok/alt) uploads on SUCCESS.
- `services/web_music_suno_guard.py`: `_WEB_MUSIC_TITLE_MAX` 120 → **80** (Suno hard limit).
- `services/forensic_watermark.py`: WAV-only LSB embedding (never mutate MP3).
- `wire_dependencies.py`: pass `redis=` to `StreamingCatalogService`.

### Intentionally dropped (kept `main`)
- Quota-plan renewal (user portal) — reverted in #134; credits-only.
- DistroKid distribution — reverted on `main`.
- Signup email-domain guard, streaming progress/publish gate, waive-billing context, public subscription terms, music genre catalog — never merged.
- All prod-only code that was older/v3-divergent (`/api/v1` paths, pre-v3 mounts, old admin/plan/license code).

## Tests

- Full `platform_api` suite: **2,858 passed**. Remaining failures verified **pre-existing on `main`** (ran the same files on a clean `main` worktree and diffed).
- 3 new failures caused by the ports were resolved: callback test fake updated for the new scheduler methods; tz-aware subscription fixture; kept `main`'s generic text-assist 502 message (reverted the provider-message port).
- 3 collection errors (`test_encrypted_package_cache`, `test_music_genre_catalog_service`, `test_stream_playback_guard`) are pre-existing on `main` (renamed/missing symbols), unrelated.

## Migration/deploy

```
python scripts/deploy/run_alembic_upgrade_sandbox.py   # to 121
python scripts/deploy/sync_platform_api_sandbox.py
```

Production: only after explicit ask, from this branch merged to `main`.

## Files touched

See the reconciliation tracker `docs/API_V3_HOTFIX_RECONCILIATION.md` and the branch commits.

## Follow-ups

- Sandbox dress rehearsal (migrations 120/121, leftover conversion, flag On, E2E matrix).
- Decide whether `main`'s generic text-assist 502 message stays (currently kept).
- Production cutover per `docs/API_V3_PRODUCTION_CUTOVER_PLAN.md`.
