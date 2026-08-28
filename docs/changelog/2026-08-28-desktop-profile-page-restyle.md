# 2026-08-28 — Desktop Profile page restyle

Local desktop only. Sandbox and production were not deployed.

## Summary

The live `camxora_python` Profile page keeps the Profile screenshot’s information layout (account, membership, channel table, usage, activity) but now uses the **Create page as the visual design system**.

Existing dashboard overview bindings stay in place. Channel search, visibility filter, pagination, and add/edit/delete dialogs are local-first with live `/profiles` save/delete when the API succeeds.

## Product impact

- Same studio chrome as Create: `#071426` workspace, `#0D1B2E` panels, `#18304A` borders, 6px radii, 28px inputs, purple `#6335D9` / `#7C3AED` controls
- Header is the shared `CreateHeader` (white 21px title, muted subtitle) with a WORKSPACE eyebrow
- Account is a compact identity row plus a read-only 2-column info grid (not dashboard tiles)
- Membership shows plan, monthly-profile bar (Create slider purple), credits wallet, expiry, and add-on channels — no song quota
- Channel profiles stay a professional table (not cards), with Create-styled search, `StudioComboBox` filter, `TransportPrimary` add button, row menu, and compact pagination
- Usage overview is a compact 2×2 field grid; recent activity is a compact list

## Technical impact

- Profile QSS is `studio_workspace_qss("profile_workspace")` from `features/create/create_styles.py` plus a thin extras sheet
- Card frames stay visible: each section (`StudioPanel`) paints its own `#0D1B2E` fill and `#23415E` rounded border. The page canvas stays `#071426` so Account, Channel Profiles, Membership, Usage Overview, and Recent Activity read as separate cards. QScrollArea viewport stylesheets are not used — they blocked parent QSS from reaching the panels.
- Visibility delegate crash (`WARNING` NameError) is fixed; Add Profile is hidden; usage labels no longer use crushed letter-spacing; pager buttons are 22px with lucide chevrons; Verified/Active badges are 20px tall
- `profile_theme.py` was removed so Profile does not fork a second palette
- Table uses `QTableView` + `QAbstractTableModel`, with `item()` kept for existing tests
- Add/edit/delete try `SaveProfileWorker` / `DeleteProfileWorker`; network failure falls back to a local model update
- Generic shell page header is hidden for the `profile` route in `application.py`

## Files touched

- `camxora_python/features/profile/`
- `camxora_python/features/create/create_styles.py`
- `camxora_python/features/create/widgets/create_header.py`
- `camxora_python/app/application.py`
- `camxora_python/tests/test_profile_view.py`
- `camxora_python/tests/test_application.py`
- `CHANGELOG.md`
- `docs/changelog/2026-08-28-desktop-profile-page-restyle.md`

## Migration/deploy

None. Desktop UI only. Do not deploy sandbox or production for this change.

## Tests

- `python -m pytest camxora_python/tests/test_profile_view.py -q`
- `python -m pytest camxora_python/tests/test_create_view.py -q`
- `python -m pytest camxora_python/tests/test_application.py::test_profile_hides_generic_shell_page_header -q`

## Follow-ups

- Wire “View all activity” and “Set as Default” to real APIs when those endpoints exist
