# Admin user monthly song-limit top-up (restored)

**Date:** 2026-10-13  
**Surfaces:** admin_portal

## Summary

Admins can increase an individual user's **period plan quota** — most importantly the
**monthly song limit** (`monthly_song_limit`, `quota_kind: "music"`) — from the user
detail page. This restores the period quota top-up UI that was removed in the
credits-only migration (`226fee07`), so support can unblock users hitting
`MONTHLY_QUOTA_EXCEEDED` ("Monthly generation quota exceeded").

## Behavior

- The user detail page again shows a **Plan quota (this period)** card with per-kind
  rows: Used / Base / Top-up / Effective / Remaining.
- **Increase quota** opens a dialog (quota type, amount, reason) and calls the existing
  `POST /api/v3/users/{id}/quota-topups` endpoint.
- Top-ups are **period-scoped limit bumps** stored in `user_period_quota_topups`; they
  apply only to the user's current `period_start` and auto-expire when the next period
  begins. Usage counters are not rewritten: remaining = base limit + top-up − used.
- `quota_kind: "music"` raises the effective `monthly_song_limit` used by
  `usage_enforcement_service._enforce_plan_quotas`, directly clearing the block seen when
  creating batch runs.
- Quota type defaults to **Songs / Suno packages (monthly song limit)**; the other kinds
  (draft, image, video, merge) remain available.
- Reason is required; each grant is audit-logged as `quota.topup`.

## Notes

- **No backend or migration changes** — the endpoint, `QuotaTopupService`, and
  `user_period_quota_topups` table (migration `081`) are intact; only the admin UI was
  re-exposed.
- `GET /api/v3/users/{id}/details` already returns `quota_period`, so no extra fetch is
  needed to render the card.

## API

- `POST /api/v3/users/{id}/quota-topups` — `{ quota_kind, amount, reason }`
- `GET /api/v3/users/{id}/quota-status` — admin period snapshot
