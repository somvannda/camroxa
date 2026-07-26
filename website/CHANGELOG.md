# Changelog — Website

Marketing site at `camxora.com` — home, features, download, blog, changelog.

**Code:** `website/`  
**Policy:** [`docs/CHANGELOG_GUIDE.md`](../docs/CHANGELOG_GUIDE.md)  
**Distribution:** [`docs/DESKTOP_DISTRIBUTION.md`](../docs/DESKTOP_DISTRIBUTION.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `/compare` conversion landing: stack vs Camxora, dual/multi-channel, AI routing, monetization-path refund, marketplace templates (one-click setup; free + premium).
- Compare link in header/footer nav and sitemap.
- Marketplace callouts on home, features, and pricing.

### Changed

- Homepage is now the conversion landing (former `/compare` pitch): stack vs Camxora, dual channels, marketplace, FAQ; `/compare` redirects to `/`.
- Home hero integrates the 100% monetization / money-back guarantee with CTAs and “What you buy.”
- Kept “Why creators switch” (10 hrs → 1 hr) and workflow step **YouTube-ready** with **Soon** badge.
- Nav “Compare” → “Why Camxora” (`/#why-switch`).
- Primary CTA: short **Create account** button; price moved under CTAs (`Plans from $X/mo`). Narrow cards use stacked CTAs + text “View plans.”
- Workflow section: open step rail / timeline instead of six bordered cards; “Auto-upload soon” as inline label on YouTube-ready.
- Marketplace / pricing honesty / final CTA: drop full-width empty frames; marketplace + pricing sit side-by-side; final CTA is copy + actions columns.
- Workflow: green = available now, amber = upcoming (YouTube auto-upload); taller rail; full-width section copy.
- Capabilities cards: unique accent colors; taller cards; full-width heading.
- Hero: full-width headline + subtitle; monetization guarantee shortened to icon chips.
- Marketing copy: product starts with **dual** faceless YouTube channels (not a single channel) across site pages and SEO meta.
- Terms § Credits System: video track-export / merge usage restore rules (technical fail vs user stop).
- Support Help Center: plan refunds vs export cancel/usage restore; FAQ for stopping an export.

## [2026-07-19]

### Added

- `/download` page loads published desktop release from `GET /api/v1/public/desktop-release` (version, download button, release notes).
- `/changelog` page listing published blog posts with category **Release notes** (admin portal only).
- Changelog link in site header/footer navigation.

### Changed

- Download page no longer a placeholder — shows loading, error, and empty (unpublished) states.

## [2026-07-17]

### Changed

- Home / features / services copy aligned to desktop product positioning.
