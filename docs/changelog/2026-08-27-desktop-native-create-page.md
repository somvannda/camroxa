# 2026-08-27 — Native Create page in the desktop shell

Local desktop only. Sandbox and production were not deployed.

## Summary

The Create screen from the standalone preview now lives in `camxora_python`. Click **Create** in WORKSPACE to open the same form, Files table, and player. The live shell chrome (header, sidebar, footer) is restyled to match the same screenshot.

## Product impact

- New sidebar item: **Create** (after Music)
- Generic page header is hidden on this route (the page has its own Create header)
- Generate Music still uses a short local busy state — not wired to web-music APIs yet

## Technical impact

- Route key `create` / `/app/create` in shell navigation
- Lazy page in `AppRouter` → `features.create.views.create_view.CreateView`

## Files touched

- `camxora_python/shared/constants/navigation.py`
- `camxora_python/shared/icons/lucide_icons.py`
- `camxora_python/app/router.py`
- `camxora_python/app/application.py`
- `camxora_python/features/create/`
- `camxora_python/tests/test_navigation.py`
- `camxora_python/tests/test_create_view.py`
