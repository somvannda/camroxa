# Daily quota bank + credit bypass after included daily cap

**Date:** 2026-07-17  
**Status:** implemented (sandbox pending deploy)

## Summary

Billing-day boundaries now follow `Asia/Phnom_Penh` midnight instead of UTC. Unused per-channel daily plan allowance accrues into a `daily_quota_bank` when users return, and consumption draws today's allowance before banked units. Active subscribers who exhaust daily plan capacity (including bank) may continue at wallet list price when balance is sufficient, with ledger metadata flag `wallet_daily_overage`. Monthly/yearly subscribers with an expired license can no longer spend wallet credits; wallet-only users without a subscription plan are unchanged. Phase-1 renewal reminders expose `renewal_alert` on `GET /credits/quota-status`.

## Product impact

| Area | Before | After |
|------|--------|-------|
| Billing day | UTC midnight | Cambodia (`Asia/Phnom_Penh`) midnight |
| Missed days | Unused daily allowance lost | Accrues into bank up to yesterday |
| Daily cap hit (subscriber + wallet) | Hard `DAILY_QUOTA_EXCEEDED` | Wallet list-price bypass when balance sufficient |
| Expired subscription + wallet | Could spend credits | Blocked (`LicenseExpiredError`) |
| Renewal UX | None in API | `renewal_alert`: none / warn / urgent / expired |

Monthly hard block for lifetime plans and subscription monthly soft overage behavior are unchanged.

## Technical impact

- **API:** `GET /credits/quota-status` adds `renewal_alert`. Quota enforcement uses billing calendar; daily quota errors include `banked_units` and `effective_daily_limit`.
- **DB:** Migration `064_daily_quota_bank` creates `daily_quota_bank` with unique `(user_id, channel_profile_id, operation_type)`.
- **Services:** `billing_calendar`, `daily_quota_bank_service`, `subscription_renewal_alert_service`; `usage_enforcement_service` accrues/consumes bank, wallet daily bypass, subscription wallet gate.
- **Desktop:** No UI changes in this phase; desktop can read `renewal_alert` later.

## Files touched

- `platform_api/services/billing_calendar.py` (new)
- `platform_api/services/daily_quota_bank_service.py` (new)
- `platform_api/services/subscription_renewal_alert_service.py` (new)
- `platform_api/repositories/daily_quota_bank_repo.py` (new)
- `platform_api/migrations/versions/064_daily_quota_bank.py` (new)
- `platform_api/services/usage_enforcement_service.py`
- `platform_api/services/batch_service.py`
- `platform_api/repositories/license_repo.py`
- `platform_api/dependencies.py`
- `platform_api/routers/credits.py`
- `platform_api/models/schemas.py`
- `platform_api/tests/test_billing_calendar.py` (new)
- `platform_api/tests/test_daily_quota_bank.py` (new)
- `platform_api/tests/test_daily_quota_bypass.py` (new)
- `platform_api/tests/test_subscription_renewal_alert.py` (new)

## Migration / deploy

1. Run Alembic migration `064_daily_quota_bank` on `platform_db`.
2. Deploy platform API; no new env vars required.
3. Verify `GET /credits/quota-status` returns `renewal_alert` for subscribed users.

## Tests

Added and run:

- `test_billing_calendar.py` — timezone date mapping and next midnight
- `test_daily_quota_bank.py` — accrual math and bank consumption
- `test_daily_quota_bypass.py` — wallet bypass after bank exhausted, subscription wallet gate
- `test_subscription_renewal_alert.py` — 7d / 3d / 1d thresholds

Also run existing `test_usage_enforcement_service.py` for regressions.

## Follow-ups

- Surface `renewal_alert` on desktop settings/billing UI
- Include banked units in channel daily quota display (`quota_display_service`)
- Email/push renewal reminders (phase 2)
- Admin reporting for `wallet_daily_overage` ledger volume

---

## Suno callback 403 + thumbnail server cache (same deploy)

**Status:** implemented (sandbox pending deploy)

### Summary

Suno provider callbacks do not include HMAC signatures; sandbox was returning 403 whenever `PLATFORM_SUNO_CALLBACK_HMAC_SECRET` was set. Callback and reconcile paths now refresh MP3 URLs from Suno record-info when completion arrives without valid download links, and defer terminal `success` until at least one http(s) URL is stored. Thumbnail composite jobs on Linux read background images from the server output cache (`PLATFORM_IMAGE_OUTPUT_CACHE_DIR/{job_id}.png`) instead of unreachable Windows client paths.

### Product impact

| Area | Before | After |
|------|--------|-------|
| Suno callback on sandbox | 403 Forbidden (unsigned provider POST) | Accepted; invalid forged signatures still rejected |
| Suno task with success but no URLs | Could mark success with empty URLs | Stays pending; reconcile/callback refresh from record-info |
| Thumbnail after server-side BG gen | Failed when `output_image_path` was a Windows path | Uses server cache / `read_job_output_bytes` |

### Technical impact

- **API:** `POST /callbacks/suno` accepts unsigned Suno POSTs; uses `X-Forwarded-For` for optional IP allowlist; refreshes URLs via record-info before persisting success.
- **Services:** `batch_service.reconcile_pending_suno_tasks` includes success-without-URL tasks; `image_job_service` resolves thumbnail backgrounds from server cache.
- **Ops:** `scripts/deploy/backfill_batch_272e846d_sandbox.py` backfills batch `272e846d-2f0a-4598-b9f4-b2a8150b67f7`.

### Files touched

- `platform_api/routers/callbacks.py`
- `platform_api/services/batch_service.py`
- `platform_api/repositories/batch_repo.py`
- `platform_api/services/suno_audio_resolver.py`
- `platform_api/services/image_job_service.py`
- `platform_api/tests/test_callback_auth_and_refund_guard.py`
- `platform_api/tests/test_suno_audio_resolver.py`
- `platform_api/tests/test_image_job_server_cache.py` (new)
- `scripts/deploy/backfill_batch_272e846d_sandbox.py` (new)

### Migration / deploy

1. Deploy platform API to sandbox (`python scripts/deploy/deploy.py`).
2. Ensure `PLATFORM_IMAGE_OUTPUT_CACHE_DIR=/opt/camxora/data/image-output-cache` in `platform_api/.env` (see `sync_download_image_fixes_sandbox.py`).
3. Run backfill after deploy: `python scripts/deploy/backfill_batch_272e846d_sandbox.py`.
4. Optional: set `PLATFORM_SUNO_CALLBACK_ALLOWED_IPS` if tightening callback auth later.

### Tests

- `test_callback_auth_and_refund_guard.py` — unsigned Suno accepted; invalid HMAC rejected
- `test_suno_audio_resolver.py` — URL normalization
- `test_image_job_server_cache.py` — thumbnail background from cache when client path is foreign

### Follow-ups (Suno/image)

- Confirm Suno provider outbound IPs if moving to strict IP allowlist instead of unsigned accept
- Monitor batch `272e846d` streaming uploads after backfill

---

## Suno rejection handling + sample pack URL import limit

**Date:** 2026-07-17  
**Status:** implemented (sandbox pending deploy)

### Summary

Suno tasks that reach provider failure statuses (e.g. `REJECTED`, `SENSITIVE_WORD_ERROR`) no longer stay stuck in `pending` during reconcile. User-facing messages are mapped centrally, persisted on `suno_tasks.error_message`, and surfaced in draft progress logs. Sample pack URL imports now honor `PLATFORM_SAMPLE_PACK_URL_IMPORT_MAX_MB` (default 1024 MB) and reject Google Drive folder links with a clear validation error.

### Product impact

| Area | Before | After |
|------|--------|-------|
| Suno REJECTED / policy failures | Task stuck pending forever | Task fails, song marked failed, credit refund path runs |
| Failure reason in logs | Generic "Suno failed" | Mapped message (content policy, credits, maintenance, etc.) |
| Sample pack URL import size | Hard 100 MB cap | Configurable up to 1 GB (default) |
| Google Drive folder URL | Opaque parse/download error | Clear "use ZIP file link or upload" validation error |

### Technical impact

- **DB:** Migration `065_suno_task_error_message` adds `suno_tasks.error_message`.
- **Services:** `suno_status_messages.py`; `parse_suno_generate_poll` / `parse_suno_lyrics_poll` fail on documented failure statuses; reconcile + callbacks + `handle_suno_task_update` pass `error_message`.
- **Config:** `PLATFORM_SAMPLE_PACK_URL_IMPORT_MAX_MB` → `sample_pack_url_import_max_mb`.
- **Admin:** Image sample packs page copy updated to "up to 1 GB".

### Files touched

- `platform_api/services/suno_status_messages.py` (new)
- `platform_api/clients/suno_client.py`
- `platform_api/migrations/versions/065_suno_task_error_message.py` (new)
- `platform_api/repositories/batch_repo.py`
- `platform_api/services/batch_service.py`
- `platform_api/routers/callbacks.py`
- `platform_api/config.py`
- `platform_api/services/sample_pack_downloader.py`
- `platform_api/services/image_sample_pack_service.py`
- `admin_portal/src/pages/image-sample-packs/index.tsx`
- `platform_api/tests/test_suno_status_messages.py` (new)
- `platform_api/tests/test_image_sample_pack_service.py`

### Migration / deploy

1. Run migration `065_suno_task_error_message` on deploy.
2. Optional: set `PLATFORM_SAMPLE_PACK_URL_IMPORT_MAX_MB=1024` (default) or lower for constrained VPS disk.

### Tests

- `test_suno_status_messages.py` — REJECTED, SENSITIVE_WORD_ERROR, pending vs failed, API code mapping
- `test_image_sample_pack_service.py` — Google Drive folder rejection, configurable max bytes
- `test_suno_lyrics_client.py` — existing poll/submit tests (unchanged expectations for success/pending)

---

## Suno failure reason in history + lyrics polish re-enabled

**Date:** 2026-07-17  
**Status:** implemented (sandbox pending deploy)

### Summary

Music history now exposes `suno_error_message` from the latest `suno_tasks` row so desktop can show `Failed (Reason: …)` in the Suno column and flash the full provider message when a failed song is selected. Lyrics polish is re-enabled on `POST /generation/polish-lyrics` and in the desktop song editor; each polish consumes one draft/lyric quota unit (same meter as a lyric slot).

### Product impact

| Area | Before | After |
|------|--------|-------|
| History Suno column | Raw status (`suno_failed`, `REJECTED`) | Readable label with short failure reason |
| Select failed song | No failure context in workspace | Status flash shows full Suno error when available |
| Polish button | Hidden/disabled; API returned 403 | Visible; polishes lyrics via LLM (1 draft quota) |

### Technical impact

- **API:** `MusicHistorySongResponse.suno_error_message`; `GET /music/history` selects `st.error_message`; `POST /generation/polish-lyrics` bills `lyric` op, calls `GenerationService.polish_lyrics_text`, refunds on failure.
- **Desktop:** `music_status.format_song_pipeline_status` for history table; `_polish_lyrics` restored; polish button unhidden.
- **Tests:** `test_music_status.py`, `TestPolishLyrics` in `test_generation_router.py`.

### Files touched

- `platform_api/models/schemas.py`
- `platform_api/routers/music_history.py`
- `platform_api/routers/generation.py`
- `platform_api/services/generation_service.py`
- `camxora_python/shared/models/platform.py`
- `camxora_python/shared/lib/music_status.py` (new)
- `camxora_python/features/music/widgets/history_card.py`
- `camxora_python/features/music/widgets/song_editor_card.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/tests/test_music_status.py` (new)
- `platform_api/tests/test_generation_router.py`

### Migration / deploy

Requires migration `065_suno_task_error_message` (already in prior section). Deploy platform API + desktop bundle together so history shows reasons.

### Tests

- `camxora_python/tests/test_music_status.py`
- `platform_api/tests/test_generation_router.py::TestPolishLyrics`

### Follow-ups

- Show polish strength slider in song editor UI when product wants explicit control
- Surface `suno_error_message` in admin batch detail if not already present
