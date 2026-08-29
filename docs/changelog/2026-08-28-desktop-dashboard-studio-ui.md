# 2026-08-28 — Desktop Dashboard studio restyle

Local desktop only. Sandbox and production were not deployed.

## Summary

The live `camxora_python` Dashboard keeps the operational information architecture (KPIs, weekly usage, monthly meters, daily channel limits, recent activity) but now uses the **Create page as the visual design system**.

Existing `DashboardOverview` / worker / workspace-cache bindings stay in place. Date range filters already-loaded stats on the UI thread; Refresh still reloads through `DashboardOverviewWorker`.

## Product impact

- Same studio chrome as Create and Profile: `#071426` workspace, `#0D1B2E` panels, `#18304A` borders, 6px radii, 28px date/refresh controls
- Header is the shared `CreateHeader` (WORKSPACE eyebrow, 21px title) with From/To `StudioDateEdit` plus Refresh
- Six compact KPI panels show credits used/limit plus generation and export counts, with green/red/muted deltas
- Weekly usage keeps the QPainter chart; YouTube series is pink; X-axis dates are labeled
- Usage This Month restores credits, drafts, song packages, images, track exports, and merges meters, plus today/account balance lines
- Daily Channel Limits is a compact table (combined row + per-channel rows) with status badges; selected rows use brand purple `#6335D9`
- Recent Activity adds a Status column and Create table chrome
- Generic shell page header is hidden on the `home` route so the studio header is the only title
- Plan slugs render as human names (`starter_monthly` → Starter (Monthly))
- Generation KPIs and the weekly chart follow the selected date range; an all-zero range shows “No usage in this date range” instead of a 0–1 axis
- Daily limits use Create-sized status badges and right-aligned counts; unmetered monthly rows say “Daily cap only” or hide instead of repeating “Not on plan”

## Technical impact

- Dashboard QSS is `studio_workspace_qss("dashboard_workspace")` plus a thin extras sheet
- Card frames paint themselves (`StudioPanel` / `NestedPanel`) so QScrollArea stylesheets cannot hide them
- Refresh disables the button while the worker runs and never blocks the UI thread
- Date range is client-side: chart, activity, and generation KPIs filter `usage_by_day` / `recent_activity`; credits stay API period totals until Refresh
- `CreateHeader` accepts an optional trailing widget for page-specific controls without forking a second header

## Files touched

- `camxora_python/features/dashboard/`
- `camxora_python/features/create/widgets/create_header.py`
- `camxora_python/shared/widgets/usage_chart.py`
- `camxora_python/app/application.py`
- `camxora_python/tests/test_dashboard_view.py`
- `camxora_python/tests/test_application.py`
- `CHANGELOG.md`
- `docs/changelog/2026-08-28-desktop-dashboard-studio-ui.md`

## Migration/deploy

None. Desktop UI only. Do not deploy sandbox or production for this change.

## Tests

- `python -m pytest camxora_python/tests/test_dashboard_view.py -q`
- `python -m pytest camxora_python/tests/test_profile_view.py -q`
- `python -m pytest camxora_python/tests/test_create_view.py -q`
- `python -m pytest camxora_python/tests/test_application.py::test_profile_hides_generic_shell_page_header -q`

## Follow-ups

- Server-side date-range query params when the dashboard stats API supports them
- Activity Stage / Batch / Channel columns when the stats payload includes those fields
