# Admin desktop installer upload

**Date:** 2026-07-19  
**Status:** implemented

## Summary

Admins can upload desktop installer packages (`.zip`, `.exe`, `.msi`) from **Software Updates** instead of pasting an external URL manually. Files are stored on VPS disk; the API returns a public download URL used by the existing software-update, website `/download`, and in-app update flows.

## Product impact

- **Before:** Build installer → manually upload to CDN → paste URL in admin.
- **After:** Build installer → upload in admin (or still paste external URL) → Save → Publish.

`camxora_python` behavior is unchanged — it still downloads from `download_url` in settings.

## Technical impact

- New `DesktopReleaseUploadService` writes to `PLATFORM_DESKTOP_RELEASE_STORAGE_PATH`.
- Admin upload: `POST /api/v1/admin/desktop/software-update/upload`.
- Public file serve fallback: `GET /api/v1/public/desktop-release/files/{filename}`.
- Production should set `PLATFORM_DESKTOP_RELEASE_PUBLIC_BASE_URL=https://downloads.camxora.com/desktop` and point nginx at the same storage path.

## Files touched

- `platform_api/services/desktop_release_upload_service.py`
- `platform_api/routers/admin.py`, `public_desktop.py`
- `platform_api/config.py`, `dependencies.py`
- `platform_api/tests/test_desktop_release_upload.py`
- `admin_portal/src/pages/software-updates/index.tsx`
- `admin_portal/src/hooks/use-desktop-notifications.ts`
- `docs/DESKTOP_DISTRIBUTION.md`

## Migration / deploy

No DB migration. Set env on VPS:

```bash
PLATFORM_DESKTOP_RELEASE_STORAGE_PATH=/var/www/downloads/desktop
PLATFORM_DESKTOP_RELEASE_PUBLIC_BASE_URL=https://downloads.camxora.com/desktop
```

Redeploy `platform_api` and rebuild `admin_portal`.

## Tests

```powershell
cd platform_api
pytest tests/test_desktop_release_upload.py tests/test_public_desktop_router.py -q
# 8 passed
```

## Follow-ups

- Optional B2 upload path for multi-region CDN.
- Version mismatch warning when filename version ≠ version field.
