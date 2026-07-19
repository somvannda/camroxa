# Google Drive large ZIP URL import fix

**Date:** 2026-07-17  
**Status:** implemented (sandbox deploy pending verification)

## Summary

Fixed admin sample-pack URL import for Google Drive ZIPs larger than ~100 MB. Large GDrive files return a virus-scan HTML interstitial; the downloader now parses multiple confirm-token patterns, streams the file with the configured byte limit, and tries usercontent/confirm fallbacks. Admin portal toasts now show the API error message instead of a generic failure string.

## Product impact

- **Before:** Google Drive imports over ~100 MB often failed with a generic "URL import failed" toast, even when sandbox config allowed 1 GB.
- **After:** Large public GDrive file links import up to `PLATFORM_SAMPLE_PACK_URL_IMPORT_MAX_MB` (default 1024 MB). Errors distinguish permission issues, HTML responses, non-ZIP content, and size limits. Direct VPS upload tab remains capped at 10 MB.

## Technical impact

- **API:** `sample_pack_downloader.py` streams GDrive and direct URL downloads with `get_url_import_max_bytes()` enforcement; confirm parsing covers input fields, hrefs, and `uc-download-link`.
- **Admin:** import URL failure toast surfaces `detail` from FastAPI validation errors.
- **Deploy:** `sync_platform_api_sandbox.py` ensures `PLATFORM_SAMPLE_PACK_URL_IMPORT_MAX_MB=1024` exists in sandbox `.env`.

## Files touched

- `platform_api/services/sample_pack_downloader.py`
- `platform_api/tests/test_sample_pack_downloader.py`
- `admin_portal/src/pages/image-sample-packs/index.tsx`
- `scripts/deploy/sync_platform_api_sandbox.py`
- `docs/changelog/2026-07-17-google-drive-large-zip-import.md`

## Migration / deploy

1. Run `python scripts/deploy/sync_platform_api_sandbox.py`
2. Confirm sandbox `.env` contains `PLATFORM_SAMPLE_PACK_URL_IMPORT_MAX_MB=1024`
3. Restart `camxora-api` (included in sync script)

## Tests

- `pytest platform_api/tests/test_sample_pack_downloader.py`
- `pytest platform_api/tests/test_image_sample_pack_service.py`

## Follow-ups

- None. Folder links remain unsupported by design; users must paste a **file** link (`/file/d/...`).
