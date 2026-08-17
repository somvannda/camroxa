# 2026-08-17 — Fix subscription purchase 500 (pending status)

## Root cause

`POST /v2/subscriptions/purchase` inserted `web_subscriptions.status = 'pending'`, but migration `089` only allowed `active|cancelled|expired|past_due`. PostgreSQL rejected the insert → HTTP 500 "An unexpected error occurred."

## Fix

- Migration `097_web_subscriptions_pending_status`: add `pending` to status check.
- Reuse/update existing pending row on checkout retry (respects `UNIQUE(user_id)`).
- Skip quota reset for non-active subscriptions; default empty `expires_at` in API response.

## Deploy

- `platform_api` + migration `097`
- `music_web` (horizontal tick sliders, plan name formatting)
