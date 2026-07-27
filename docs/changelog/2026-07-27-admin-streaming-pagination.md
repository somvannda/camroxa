# Admin streaming catalog server-side pagination

**Date:** 2026-07-27  
**Status:** implemented (sandbox deploy)

## Summary

Admin Music Streaming catalog (`/streaming`) no longer loads up to 500 tracks/albums and filters in the browser. Catalog list APIs return `{ items, total, limit, offset }` with optional `q` and `publish_status`, and the admin UI paginates at 50 rows per page with server search/status filters.

## Product impact

**Before:** Catalog appeared to show “all” items from a 500-row client fetch; search/status filtered only that slice; no page controls.  
**After:** Tracks and albums load page-by-page (50); search and status hit the API; pagination shows total count and next/prev.

## Technical impact

- `GET /api/v1/admin/streaming/catalog` and `.../catalog/albums` accept `limit` (1–200, default 50), `offset`, `q`, `publish_status` (`published`|`unpublished`).
- Responses include `total`, `limit`, `offset`.
- Repo: `list_admin_catalog` / `list_admin_albums` + matching `count_*` with ILIKE filters.
- Admin hooks pass page params; catalog page uses shared `Pagination` and 300ms debounce on search.

## Files touched

- `platform_api/repositories/streaming_repo.py`
- `platform_api/routers/streaming_admin.py`
- `admin_portal/src/hooks/use-streaming.ts`
- `admin_portal/src/pages/streaming/catalog.tsx`
- `platform_api/CHANGELOG.md`
- `admin_portal/CHANGELOG.md`

## Migration / deploy

- No DB migration.
- Sandbox: `python scripts/deploy/sync_platform_api_sandbox.py` then `python scripts/deploy/sync_admin_portal_sandbox.py`.
- Smoke: admin catalog endpoints return `total`/`offset`; UI page controls advance lists.

## Tests

- Sandbox deploy: API restart active; admin portal build succeeded (`catalog-C72oY8Iz.js` includes `pageSize` / `totalCount` / `publish_status`).
- Repo smoke on sandbox DB: `tracks_total=707`, `albums_total=79`; `limit=2`/`offset=0` vs `offset=2` returns different track IDs; `publish_status=published` and `q` filters return counts.
- Unauthenticated `GET /admin/streaming/catalog` → 401 (expected).

## Follow-ups

- Optional: page-size selector; sort columns; upload-jobs pagination if that list grows.
