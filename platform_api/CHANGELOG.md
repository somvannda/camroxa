# Changelog — Platform API

Backend REST/WebSocket API — generation, billing, streaming, image jobs, admin routes, public endpoints.

**Code:** `platform_api/`  
**Policy:** [`docs/CHANGELOG_GUIDE.md`](../docs/CHANGELOG_GUIDE.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- Dashboard weekly `usage_by_day` window now includes **today** (`today-6..today`); previously ended at yesterday and hid same-day Manual exports.

### Added

- `video_manual` local consume/refund (same price/quota pool as `video`, separate usage key).
- Dashboard stats: `studio_exports`, `manual_exports`, `youtube_uploads`; daily usage breakdown fields.
- Quota status already exposed `daily_videos_*` / `daily_merges_*` (now surfaced in portal UI).

### Changed

- `videos_generated` alias = studio + manual track exports; `videos_uploaded` remains YouTube successes.

## [2026-07-19]

### Added

- `GET /api/v1/public/desktop-release` — public published desktop release (version, download URL, release notes) for website download page.
- Suno blocklist follow-ups: per-channel scope, sanitize metadata on songs, failure metrics admin endpoint, guarded auto-retry on callback.
- Migration `067_song_suno_sanitize_metadata`.

### Changed

- Public blog list supports optional `category` query param (case-insensitive) for website `/changelog`.

## [2026-07-18]

### Added

- Suno lyrics sanitization service, `POST /generation/lyrics-suno-check`, blocklist CRUD admin APIs, migration `066_suno_blocklist_terms`.
- AI routing real stored costs in provider list API.

## [2026-07-17]

### Added

- Daily quota bank and credit-bypass billing controls.
- Streaming genre browse public API and catalog metadata sync.
