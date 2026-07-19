# Public desktop release API and website download/changelog

**Date:** 2026-07-19  
**Status:** implemented

## Summary

Added a public `GET /api/v1/public/desktop-release` endpoint backed by existing admin software-update `system_settings`, wired the website `/download` page to it, added a `/changelog` page fed by blog posts in the **Release notes** category, and documented the full build→publish→download flow.

## Product impact

- **Before:** `/download` was a placeholder; no public way to discover the latest installer; changelog had no dedicated page.
- **After:** Published desktop releases show version, direct download link, and release notes on `/download`. Release-note blog posts appear on `/changelog`. User portal download links resolve to the live download page.

## Technical impact

- **API:** new `platform_api/routers/public_desktop.py`; optional `category` query param on `GET /blog-posts/public`.
- **Website:** dynamic `/download` and new `/changelog`; nav/footer link in `site-chrome.tsx`.
- **Admin / DB:** no schema changes; reuses `desktop.software_update.*` keys.
- **User portal:** existing links to `{website}/download` now land on a functional page (no portal code changes required).

## Files touched

**Platform API**

- `platform_api/services/desktop_notification_admin_service.py`
- `platform_api/routers/public_desktop.py` (new)
- `platform_api/routers/blog_posts.py`
- `platform_api/main.py`
- `platform_api/tests/test_public_desktop_router.py` (new)
- `platform_api/tests/test_desktop_notification_admin_service.py`

**Website**

- `website/src/lib/desktop-release.ts` (new)
- `website/src/lib/blog.ts`
- `website/src/app/download/page.tsx`
- `website/src/app/changelog/page.tsx` (new)
- `website/src/components/marketing/site-chrome.tsx`

**Docs**

- `docs/DESKTOP_DISTRIBUTION.md` (new)

## Migration / deploy

- Deploy platform API and website together.
- No migrations.
- Publish a software update from admin (Save + Publish) before `/download` shows an installer.
- For `/changelog`, create blog posts with category `Release notes`.

## Tests

- `pytest tests/test_public_desktop_router.py tests/test_desktop_notification_admin_service.py -q`

## Follow-ups

- Installer file upload in admin (URL paste remains the workflow).
- Optional user-portal direct download button via the same public API (portal currently links to `/download`).
