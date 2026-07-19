# Changelog — Platform API

Backend REST/WebSocket API — generation, billing, streaming, image jobs, admin routes, public endpoints.

**Code:** `platform_api/`  
**Policy:** [`docs/CHANGELOG_GUIDE.md`](../docs/CHANGELOG_GUIDE.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `POST /api/v1/admin/desktop/software-update/upload` — admin installer upload (`.zip`, `.exe`, `.msi`, up to 500 MB).
- `GET /api/v1/public/desktop-release/files/{filename}` — serve uploaded packages when no CDN base URL is configured.
- Settings: `PLATFORM_DESKTOP_RELEASE_STORAGE_PATH`, `PLATFORM_DESKTOP_RELEASE_PUBLIC_BASE_URL`, `PLATFORM_DESKTOP_RELEASE_MAX_UPLOAD_MB`.

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
