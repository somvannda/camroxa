# 2026-08-29 — Desktop Marketplace studio restyle

Local desktop only. Sandbox and production were not deployed.

## Summary

Marketplace still used the old slate / sky-blue card look. It now matches the Create studio design system used by Dashboard, Music, Image, Progress, and Workflow.

Catalog fetch, filters, search debounce, pagination, preview loading, and install / reinstall are unchanged.

## Product impact

- In-page CreateHeader replaces the generic shell page header
- Template cards, search, All / Video / Reel chips, and pagination use studio navy and purple
- Install / Installed buttons use compact SecondaryButton chrome with icons

## Technical impact

- `MarketplaceView` applies `build_marketplace_page_qss()`
- Cards are `NestedPanel`; the catalog host is `StudioPanel`

## Files touched

- `camxora_python/features/marketplace/views/marketplace_view.py`
- `camxora_python/features/marketplace/marketplace_styles.py`
- `camxora_python/app/application.py`
- `camxora_python/tests/test_application.py`
- `camxora_python/tests/test_marketplace_installed_ui.py`
- `CHANGELOG.md`
- `docs/changelog/2026-08-29-desktop-marketplace-studio-ui.md`

## Migration/deploy

None. Desktop UI only.

## Tests

- `python -m pytest camxora_python/tests/test_marketplace_installed_ui.py camxora_python/tests/test_application.py -q`
