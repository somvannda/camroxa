# 2026-08-28 — Desktop Music studio restyle

Local desktop only. Sandbox and production were not deployed.

## Summary

The live `camxora_python` Music page keeps the existing information architecture (settings strip, song editor, channel cards, automation, history) and the same widget positions. Visual chrome matches the Create studio design system, and a follow-up polish pass fixes credit formatting, empty-state actions, combo tooltips, and History labels.

Composer bindings, history filters, generate, and recovery actions stay in place.

## Product impact

- Same studio look as Create / Progress: `#071426` canvas, `#0D1B2E` panels, 6px radii, 28px dates and combos
- In-page `CreateHeader` replaces the generic shell page header
- Compact Secondary buttons and purple Generate CTA
- Generate/plan credits show as `99.4 credits` (no raw float noise); lowercase `credits`
- Copy title/lyrics/both and Rewrite stay disabled when those fields are empty
- Settings Plan from/to vs History from/to are labeled separately, with tooltips
- Channel chips title-case ALL CAPS names (`BASSNOVA` → `Bassnova`) and keep the raw name as a tooltip
- Song column is ~50px narrower; each channel column is 245px; automation is 50px narrower
- Settings strip has no leading gear; Creativity sits above its slider; Unique opening / content pools / planned days are centered
- Automation keeps the purple Generate button and uses a two-row credit calculation card (batches/songs/image/video + totals). Credit amounts sit under the text labels (not the icons) and columns are separated by vertical rules
- History table headers are `Album 1` / `Album 2`; empty table explains Show all / date filters
- Combo items that clip get tooltips; Strict / History / Count / Creativity have field explanations
- Settings calendars, language dropdowns, Strict, History, and Count put the label above the control; Creativity and checkboxes stay inline
- Section titles (Song, channels, Automation, History) sit on the panel fill with no darker header bar

## Technical impact

- Music QSS is `studio_workspace_qss("music_workspace")` plus a thin extras sheet
- `StudioDateEdit` / `StudioCheckBox` / `StudioComboBox` replace shell controls in the same slots
- `StudioComboBox.sync_item_tooltips()` fills item tooltips; an explicit `setToolTip()` is not overwritten
- `format_plan_credits` / `format_button_credit_label` round float noise to two decimals
- Existing test hooks (`_loading_card`, `_automation_card`, history filter values) are unchanged

## Files touched

- `camxora_python/features/music/`
- `camxora_python/shared/lib/music_costs.py`
- `camxora_python/features/create/widgets/studio_controls.py`
- `camxora_python/app/application.py`
- `camxora_python/tests/test_music_view.py`
- `camxora_python/tests/test_music_history_card.py`
- `camxora_python/tests/test_music_costs.py`
- `camxora_python/tests/test_application.py`
- `CHANGELOG.md`
- `docs/changelog/2026-08-28-desktop-music-studio-ui.md`

## Migration/deploy

None. Desktop UI only.

## Tests

- `python -m pytest camxora_python/tests/test_music_view.py camxora_python/tests/test_music_history_card.py camxora_python/tests/test_music_costs.py camxora_python/tests/test_automation_card.py camxora_python/tests/test_application.py::test_profile_hides_generic_shell_page_header -q`
