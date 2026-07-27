# Changelog — Admin portal

Internal operations UI — AI routing, sample packs, streaming catalog, marketplace, software updates, blog CMS.

**Code:** `admin_portal/`  
**Policy:** [`docs/CHANGELOG_GUIDE.md`](../docs/CHANGELOG_GUIDE.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Streaming catalog: Plays column on tracks and albums (sum of track plays)
- Streaming catalog: server-side pagination (50/page) with API search + status filters

### Changed

### Fixed

- Software Updates: parse `CamxoraSetup-*.exe` (Inno) filenames so Publish no longer 400s; pass explicit version on publish.

## [2026-07-25]

### Fixed

- Credits Edit Pricing: surface API 422 validation messages (e.g. local $0 COGS) instead of a generic axios status toast.

### Added

- Prompts page: Music Moods tab (Camxora + user scope) with CRUD, visibility toggle, and usage analytics — mirrors Structures.
- Software Updates page: upload `.zip` / `.exe` / `.msi` installer packages; auto-fills download URL after upload.

## [2026-07-19]

### Added

- Suno blocklist management (Settings tab) and failure metrics for lyrics sanitization rollout.

### Changed

- AI routing section shows stored real costs per operation; Suno lyrics cost aligned to registry.

## [2026-07-18]

### Added

- Suno lyrics sanitize UX support via backend blocklist APIs (admin term registry).

## [2026-07-17]

### Added

- Streaming catalog metadata UI and genre sync for music portal.
