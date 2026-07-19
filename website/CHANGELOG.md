# Changelog — Website

Marketing site at `camxora.com` — home, features, download, blog, changelog.

**Code:** `website/`  
**Policy:** [`docs/CHANGELOG_GUIDE.md`](../docs/CHANGELOG_GUIDE.md)  
**Distribution:** [`docs/DESKTOP_DISTRIBUTION.md`](../docs/DESKTOP_DISTRIBUTION.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

_No unreleased changes._

## [2026-07-19]

### Added

- `/download` page loads published desktop release from `GET /api/v1/public/desktop-release` (version, download button, release notes).
- `/changelog` page listing blog posts with category **Release notes**.
- Changelog link in site header/footer navigation.

### Changed

- Download page no longer a placeholder — shows loading, error, and empty (unpublished) states.

## [2026-07-17]

### Changed

- Home / features / services copy aligned to desktop product positioning.
