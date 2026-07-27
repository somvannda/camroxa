# Admin plan form: separate period caps vs daily limits

**Date:** 2026-07-27  
**Status:** implemented (sandbox + production deployed)

## Summary

Admin Edit/Create Plan dialogs mixed period quotas with daily limits. Fields are regrouped under **Period caps (billing cycle)** and **Daily limits**, with short hints for 6‑mo/annual multiplication and add-on scaling.

## Product impact

Admins can set monthly-style period totals and daily rates without hunting mixed fields. Same values; clearer layout only.

## Technical impact

- New shared `PlanLimitsFields` used by Edit and Create dialogs
- No API/schema change

## Files touched

- `admin_portal/src/pages/plans/plan-limits-fields.tsx`
- `admin_portal/src/pages/plans/index.tsx`
- `admin_portal/CHANGELOG.md`
- `docs/changelog/2026-07-27-admin-plan-form-period-daily-sections.md`

## Migration / deploy

Rebuild/sync admin portal (sandbox).

## Tests

- Manual: open Edit Plan → sections Period / Daily visible; save still works

## Follow-ups

- Optional: auto-scale period fields when switching Monthly → 6 mo / Annual buttons
