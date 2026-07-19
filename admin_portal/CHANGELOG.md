# Changelog — Admin portal

Internal operations UI — AI routing, sample packs, streaming catalog, marketplace, software updates, blog CMS.

**Code:** `admin_portal/`  
**Policy:** [`docs/CHANGELOG_GUIDE.md`](../docs/CHANGELOG_GUIDE.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

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
