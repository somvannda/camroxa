# Admin API Health fetched SPA HTML instead of Platform API

**Date:** 2026-08-06
**Status:** implemented

## Summary

Production admin Dashboard showed API Status **Unknown** / Database unreachable
with a host-derived **Production** label, even though `api.camxora.com/health`
was healthy. Admin was calling same-origin `/health`, which nginx serves as
`index.html`.

## Product impact

**Before:** API Health · System Status looked down on admin while the real API was up.

**After:** Admin polls `/api/v1/health` via the existing `/api/` proxy and shows
real status, uptime, timestamp, and API `environment_label`.

## Technical impact

- Mount health router at both `/health` and `/api/v1/health`
- Admin `useHealthStatus` uses `/api/v1/health` and rejects non-JSON payloads

## Files touched

- `platform_api/main.py`
- `platform_api/tests/test_health_router.py`
- `admin_portal/src/hooks/use-dashboard.ts`
- `admin_portal/CHANGELOG.md`, `platform_api/CHANGELOG.md`

## Migration / deploy

Deploy `platform_api` + rebuild admin (sandbox then production). No DB migration.

## Tests

- `pytest platform_api/tests/test_health_router.py -q`
- Manual: `https://admin.camxora.com/api/v1/health` returns JSON

## Follow-ups

- None
