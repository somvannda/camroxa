# Marketing compare landing + marketplace positioning

**Date:** 2026-07-20  
**Status:** implemented (sandbox deploy pending)

## Summary

Added a conversion-focused `/compare` landing page that sells Camxora as the faceless music **production system** (not the cheapest raw AI stack): end-to-end pipeline vs ChatGPT/Suno/CapCut grind, dual → 10+ channels, AI routing, monetization-path refund (not cancel-anytime), and marketplace templates with **one-click download & setup** (free + premium).

## Product impact

**Before**
- Ads/cold traffic had no dedicated comparison funnel; homepage was brand-led.
- Marketplace templates were not called out on marketing pages.

**After**
- `/compare` is the paid-traffic landing: old stack vs Camxora, pipeline, capabilities, marketplace, pricing honesty, monetization guarantee, FAQ, repeated CTAs with live “from $X/mo”.
- Nav + sitemap include Compare; home/features/pricing mention marketplace (free + premium, one-click setup).

## Technical impact

- Website-only marketing copy and routing; no API/DB changes.
- Plans price for CTAs fetched from `GET /plans/public` (same pattern as pricing page).

## Files touched

### Website
- `website/src/app/compare/page.tsx` (new)
- `website/src/components/marketing/site-chrome.tsx`
- `website/src/app/sitemap.ts`
- `website/src/app/page.tsx`
- `website/src/app/features/page.tsx`
- `website/src/app/pricing/page.tsx`
- `website/CHANGELOG.md`

## Migration / deploy

1. Deploy website to sandbox: `python scripts/deploy/deploy_website_portal_sandbox.py` (or equivalent website sync).
2. Smoke: open `https://sandbox.camxora.com/compare` — hero CTA, marketplace section, FAQ, guarantee links.
3. Confirm nav shows **Compare**; homepage “Why Camxora” links to `/compare`.

## Tests

- Manual review of page structure and copy against Terms/Support monetization guarantee wording.
- No automated website tests added.

## Follow-ups

- Point Facebook/paid ads to `/compare` (not homepage).
- Optional: real product screenshots on compare hero when assets are ready.
- Optional: wire marketplace deep-link once public catalog URL exists.
