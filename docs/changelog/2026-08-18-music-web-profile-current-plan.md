# Music web profile shows current plan instead of subscribe pitch

**Date:** 2026-08-18

## Summary

The billing date is stored on the subscription (`2026-09-16` for this sandbox user) but the profile card only read `GET /v2/subscriptions/my-subscription`. When that payload is missing, the UI showed a dash. Credit balance now includes `current_period_end` so the profile can show next billing even if the subscription endpoint does not.

Profile now treats an active credit subscription as paid, shows the current plan, and lists the other public plans with the current one marked.

## Surfaces

- `platform_api` — `subscription_service.get_user_subscription`, `v2_subscriptions`, `credit_service`, `v2_credits`
- `music_web` — `subscription-section`, `available-plans-grid`, `subscription-api`
