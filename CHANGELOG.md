# Changelog — Desktop app (`camxora_python`)

All notable changes to the **Camxora desktop app** (PySide6 client) are documented here.

This is **not** the changelog for user portal, music portal, admin portal, platform API, or website — see [`docs/CHANGELOG_GUIDE.md`](docs/CHANGELOG_GUIDE.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.2] - 2026-07-19

### Added

- Suno sanitize metadata on history, learned-term cache, and online lyrics scan merge
- Desktop distribution: public release API, website `/download` + `/changelog`, admin installer upload

### Fixed

- Progress page Stage / Progress % / Export / Merge alignment when merged MP4s exist on disk (incl. long-only beattok runs) and when export workspace state is stale
- Stuck `suno_pending` reconciliation and one-pass auto-sanitize / auto-retry on sensitive Suno failures

### Changed

- Progress pipeline vocabulary standardized to Not started, Pending, In Progress, Completed; stage label **Converter → Export**, **Merger → Merge**
- Video pipeline automation / channel asset path handling improvements

## [0.2.1] - 2026-07-19

### Added

- Daily quota bank and credit-bypass billing controls (API + admin)
- Suno lyrics blocklist registry with admin UI and client highlighting
- Music genre catalog support for descriptions / streaming metadata
- Desktop single-instance guard (second launch focuses the existing window)
- Diagnostics opt-in sync from Settings (Log page hidden by default)
- First-launch install date for setup notifications
- Website home / features / services copy aligned to the desktop product

### Fixed

- Video template preview background now persists across save/reload
- Music preview duration shows correctly on first play
- Progress page no longer shows the Desktop Download Queue card
- Workflow / Progress polling quieter by default (manual refresh still logs)
- SpinBox up/down arrows visible again in the deep-blue theme
- Sample-pack URL import and streaming metadata sync for admin catalog
- SLAI gpt-5.6 text models and sandbox lyric probing

### Changed

- Channel pricing / plan-tier cost estimates and pricing keys
- Desktop packaging still ships FFmpeg + VC++ via Inno Setup

## [0.2.0] - 2026-07-16

### Added

- Initial sandbox desktop installer pipeline (PyInstaller + Inno Setup)
- Bundled FFmpeg and Visual C++ redistributable bootstrap
