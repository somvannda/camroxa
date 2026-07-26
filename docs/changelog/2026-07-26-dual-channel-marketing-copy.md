# Dual-channel marketing copy (not single channel)

**Date:** 2026-07-26  
**Status:** implemented (sandbox website + portal deploy)

## Summary

Corrected public marketing language that implied building a single faceless YouTube channel. Camxora starts creators on **dual** channels and scales from there. Updated website and user-portal chrome/meta copy accordingly.

## Product impact

- **Before:** Hero and guarantee text often said “a faceless YouTube music channel” / “your channel.”
- **After:** Copy frames dual channels as the default start (home, compare, pricing, terms, support, about, features, services, blog, download, SEO/OG).

## Technical impact

- Marketing strings only; no API or billing contract changes.
- User portal footer/meta aligned with website dual-channel framing.

## Files touched

- `website/src/app/page.tsx`, `compare/page.tsx`, `pricing/page.tsx`, `support/page.tsx`, `terms/page.tsx`, `about/page.tsx`, `features/page.tsx`, `services/page.tsx`, `blog/page.tsx`, `download/page.tsx`, `layout.tsx`
- `website/src/components/marketing/site-chrome.tsx`, `content-page-shell.tsx`
- `website/CHANGELOG.md`
- `user_portal/src/components/auth/portal-marketing-shell.tsx`, `user_portal/src/app/layout.tsx`
- `docs/changelog/2026-07-26-dual-channel-marketing-copy.md`

## Migration / deploy

1. `python scripts/deploy/deploy_website_portal_sandbox.py`

## Tests

- Manual copy review; no automated marketing tests.

## Follow-ups

- Keep plan/guarantee legal wording consistent if counsel revises monetization terms.
