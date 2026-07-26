# Homepage replaces compare landing

**Date:** 2026-07-26  
**Status:** implemented (sandbox website deploy)

## Summary

The marketing homepage is now the conversion landing formerly at `/compare`. The 100% monetization money-back guarantee is integrated into the top hero (with CTAs and “What you buy”). Kept the original home “Why creators switch” time section and the workflow **YouTube-ready (Soon)** step. `/compare` redirects to `/`.

## Product impact

- **Before:** Soft product home + separate `/compare` pitch; guarantee sat lower on compare.
- **After:** `/` carries the full conversion story; guarantee sits in the first viewport; creators-switch and YouTube-ready Soon remain; old `/compare` links redirect home.

## Technical impact

- `website/src/app/page.tsx` rebuilt from compare content + retained home sections.
- `website/src/app/compare/page.tsx` → `redirect("/")`.
- Nav/sitemap updated; no API changes.

## Files touched

- `website/src/app/page.tsx`
- `website/src/app/compare/page.tsx`
- `website/src/components/marketing/site-chrome.tsx`
- `website/src/app/sitemap.ts`
- `website/CHANGELOG.md`
- `docs/changelog/2026-07-26-homepage-compare-merge.md`

## Migration / deploy

1. `python scripts/deploy/deploy_website_portal_sandbox.py`

## Tests

- Manual layout review; no automated marketing tests.

## Follow-ups

- Optional permanent redirect in CDN/nginx for `/compare` in addition to Next redirect.
