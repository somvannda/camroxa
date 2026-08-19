# Changelog — User portal

Customer account, billing, channel management, and onboarding at `app.camxora.com`.

**Code:** `user_portal/`  
**Policy:** [`docs/CHANGELOG_GUIDE.md`](../docs/CHANGELOG_GUIDE.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- Email confirmation is a locked screen (no marketing nav, footer, or dashboard
  sidebar). Unconfirmed users cannot open the control panel. See
  `docs/changelog/2026-08-17-email-confirm-gate.md`.
- Studio register sends `product: studio` / `X-Signup-Product` so music-web
  signups stay a separate product tag on the same email. Completing channel
  onboarding still adds `studio`. See
  `docs/changelog/2026-08-15-music-web-suno-create.md`.

### Added

- **Guides** presentation (`/dashboard/guides`): full walkthrough (intro → monetization → onboarding → YouTube → using CAMXORA → growth → coming soon → thank you); nav pinned above Sign out separator; slide footer callouts. See `docs/changelog/2026-08-03-user-portal-guides-deck.md`.
- Dashboard Overview **Your limits** panel: monthly and daily remaining as `X / Y` for Suno, images, drafts, track exports, and merges; per-channel daily preview.
- 7-day trend chart series for studio exports, manual exports, and YouTube uploads.

### Changed

- Credits panel labels distinguish month vs today for track exports and merges.
- Marketing chrome/meta: dual faceless YouTube channels (not a single channel) as the default start.
- Header/footer nav synced with website: **Why Camxora** (`/#why-switch`) plus Features, Pricing, Download, About.

## [2026-07-19]

### Changed

- Download experience delegated to website `/download` as the single canonical installer page.
