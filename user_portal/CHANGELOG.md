# Changelog — User portal

Customer account, billing, channel management, and onboarding at `app.camxora.com`.

**Code:** `user_portal/`  
**Policy:** [`docs/CHANGELOG_GUIDE.md`](../docs/CHANGELOG_GUIDE.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- DistroKid $5/mo add-on checkout panel on Billing (WAV + DistroKid delivery entitlement). See `docs/changelog/2026-07-27-distrokid-addon-scaffold.md`.
- DistroKid billing copy updated: desktop DistroKid upload is available (no longer “coming next”). See `docs/changelog/2026-07-27-distrokid-automation-phases.md`.
- Login `?return_to=` / `?next=` redirects back to allowlisted Music Streaming hosts after sign-in
- Dashboard Overview **Your limits** panel: monthly and daily remaining as `X / Y` for Suno, images, drafts, track exports, and merges; per-channel daily preview.
- 7-day trend chart series for studio exports, manual exports, and YouTube uploads.

### Changed

- Credits panel labels distinguish month vs today for track exports and merges.
- Marketing chrome/meta: dual faceless YouTube channels (not a single channel) as the default start.
- Header/footer nav synced with website: **Why Camxora** (`/#why-switch`) plus Features, Pricing, Download, About.

## [2026-07-19]

### Changed

- Download experience delegated to website `/download` as the single canonical installer page.
