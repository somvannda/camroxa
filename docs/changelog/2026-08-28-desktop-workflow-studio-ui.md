# 2026-08-28 — Desktop Workflow studio restyle

Local desktop only. Sandbox and production were not deployed.

## Summary

The live `camxora_python` Workflow page keeps the operational layout (filters, run stats, run lanes, selected-run stage board, notes / assets / upload) but now uses the **Create page as the visual design system**.

Lane selection, progress aggregate loading, runtime overlay, and local date/active-only prefs stay in place.

## Product impact

- Same studio chrome as Create / Profile / Dashboard: `#071426` canvas, `#0D1B2E` panels, 6px radii, 28px dates and Refresh
- Shared `CreateHeader` (WORKSPACE eyebrow) with From / To, Active only, and compact Refresh — no separate Filters card and no bright-blue CTA
- Generic shell page header is hidden on the `workflow` route
- Stats, lanes, and the selected-run board use Create cards, purple selection (`#6335D9`), and 16px status badges
- Stage progress bars use Create track/chunk styling (purple in-progress, green done)

## Technical impact

- Workflow QSS is `studio_workspace_qss("workflow_workspace")` plus a thin extras sheet
- `StudioDateEdit` / `StudioCheckBox` replace shell date edits and the stock checkbox
- Existing worker / store / step bindings and test hooks (`_runs_card._value`, `_lane_list._list`, `_selected_panel._channel`) are unchanged

## Files touched

- `camxora_python/features/workflow/`
- `camxora_python/features/create/widgets/studio_panel.py`
- `camxora_python/app/application.py`
- `camxora_python/tests/test_workflow_view.py`
- `camxora_python/tests/test_application.py`
- `CHANGELOG.md`
- `docs/changelog/2026-08-28-desktop-workflow-studio-ui.md`

## Migration/deploy

None. Desktop UI only.

## Tests

- `python -m pytest camxora_python/tests/test_workflow_view.py -q`
- `python -m pytest camxora_python/tests/test_application.py::test_profile_hides_generic_shell_page_header -q`
