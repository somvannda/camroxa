# 2026-08-28 — Desktop Progress studio restyle

Local desktop only. Sandbox and production were not deployed.

## Summary

The live `camxora_python` Progress page keeps the operational layout (date/stage/limit filters, run stats, operational table, row detail, recovery actions) but now uses the **Create page as the visual design system**.

Progress aggregate loading, desktop runtime overlays, and right-click recovery stay in place.

## Product impact

- Same studio chrome as Create / Profile / Dashboard / Workflow: `#071426` canvas, `#0D1B2E` panels, 6px radii, 28px dates and Refresh
- Shared `CreateHeader` (WORKSPACE eyebrow) for the page title
- Date / Active only / Limit / Stage / Refresh sit in a compact strip directly above the operational rows table — no header trailing and no bright-blue CTA
- Generic shell page header is hidden on the `progress` route
- Stats, operational table, and row detail use Create cards, 16px stage badges, and compact Secondary buttons
- Lucide icons on KPI cards, filter Refresh, Start Export, folder/pipeline actions, and banners

## Technical impact

- Progress QSS is `studio_workspace_qss("progress_workspace")` plus a thin extras sheet
- `StudioDateEdit` / `StudioCheckBox` / `StudioComboBox` replace shell date edits and stock filter controls
- Existing worker / recovery / table bindings and test hooks (`_active_card._value`, `_rows_card._table`, `_detail_card._batch_id`) are unchanged

## Files touched

- `camxora_python/features/progress/`
- `camxora_python/app/application.py`
- `camxora_python/tests/test_progress_view.py`
- `camxora_python/tests/test_application.py`
- `CHANGELOG.md`
- `docs/changelog/2026-08-28-desktop-progress-studio-ui.md`

## Migration/deploy

None. Desktop UI only.

## Tests

- `python -m pytest camxora_python/tests/test_progress_view.py -q`
- `python -m pytest camxora_python/tests/test_application.py::test_profile_hides_generic_shell_page_header -q`
