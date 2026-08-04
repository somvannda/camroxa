# Admin user plan quota + credit top-up

**Date:** 2026-08-04  
**Surfaces:** platform_api, admin_portal

## Summary

Admins can top up a user's **period plan quotas** (draft, Suno packages, images, export, merge) and **wallet credits** from the user detail page.

## Behavior

- Quota top-ups are **period limit bumps** stored in `user_period_quota_topups`.
- They apply only for the user's **current billing `period_start`** and auto-expire when the next period starts (rows for old periods are ignored).
- Usage counters are not rewritten; remaining = base plan limit + top-up − used.
- Draft remains a **single shared pool** (album / title / lyrics).
- Credit top-up reuses `POST /api/v1/credits/adjust`.
- Dual-control for credit adjusts is **off by default** (`PLATFORM_ADMIN_ADJUST_DUAL_CONTROL_CREDITS=0`) so a single admin can apply immediately. Set a positive threshold only if multiple admins should co-approve large wallets.

## Security

- Both credit adjust and quota top-up require an authenticated **admin** JWT (`require_admin` → 403 for non-admins).
- Regular users cannot call these endpoints even if they know the URL.
- Every successful credit adjust and quota top-up is **audit-logged** (`credit.adjust` / `quota.topup`) with actor, amount/kind, reason, and target user.
- Reason is required on both actions.

## API

- `GET /api/v1/users/{id}/quota-status` — admin period snapshot
- `POST /api/v1/users/{id}/quota-topups` — `{ quota_kind, amount, reason }`
- `GET /api/v1/users/{id}/details` now includes `quota_period`

## Migration

- `081_user_period_quota_topups`
