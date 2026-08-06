# Admin API Health shows Sandbox vs Production

**Date:** 2026-08-06
**Status:** implemented (sandbox deployed; production not deployed)

## Summary

Admin Dashboard **API Health · System Status** (and the top-bar badge) now
label the connected Platform API environment as **Sandbox** or **Production**,
so operators can tell which backend they are looking at.

## Product impact

**Before:** System Health only showed healthy/degraded/unhealthy with no
environment name — easy to confuse sandbox and production admin tabs.

**After:**
- Sandbox admin shows **Sandbox**
- Production admin shows **Production**
- Dashboard has a dedicated API Health · System Status card with environment,
  status, uptime, and last check time
- Top bar shows a compact environment badge on every page

## Technical impact

- `GET /health` now returns `environment` (raw `PLATFORM_ENVIRONMENT`) and
  `environment_label` (ops-facing: staging→Sandbox, production→Production)
- Admin resolves label from the health payload first, then falls back to the
  admin hostname (`admin.sandbox…` / `admin.camxora.com`) for mixed deploys

## Files touched

- `platform_api/config.py` — `environment_display_label()`
- `platform_api/routers/health.py` — include environment fields
- `platform_api/tests/test_health_router.py`, `test_production_settings.py`
- `admin_portal/src/lib/deployment-environment.ts` (+ tests)
- `admin_portal/src/pages/dashboard.tsx`
- `admin_portal/src/components/layout/top-bar.tsx`
- `admin_portal/src/types/models.ts`
- `admin_portal/CHANGELOG.md`, `platform_api/CHANGELOG.md`

## Migration / deploy

1. Deploy `platform_api` (sandbox first) so `/health` returns the new fields
2. Rebuild/sync admin portal
3. Production only when explicitly requested

No database migration.

## Tests

- `pytest platform_api/tests/test_health_router.py platform_api/tests/test_production_settings.py -q`
- `npm test -- deployment-environment` in `admin_portal`

## Follow-ups

- Production admin rebuild when user asks for production deploy
