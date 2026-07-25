# Calendar dropdown no longer steps the month

**Date:** 2026-07-25  
**Status:** implemented (desktop restart required)

## Summary

Shell `QDateEdit` fields used spin up/down arrows. With `MM/dd/yyyy` the first section is Month, so clicking the down arrow advanced the month instead of only opening the calendar. Shared `ShellDateEdit` hides spin buttons (calendar popup remains), ignores wheel/step nudges, and briefly blocks click-through onto the calendar’s month controls when the popup opens.

## Product impact

- **Before:** Clicking the date field arrow could change From/To by a month on Music, History, Progress, Workflow, and Image.
- **After:** The arrow/dropdown only opens the calendar; pick a day to change the value.

## Technical impact

- New `camxora_python/shared/widgets/shell_date_edit.py` used by Music settings/history, Progress, Workflow, Image queue, and `DatePickerField`.

## Files touched

- `camxora_python/shared/widgets/shell_date_edit.py`
- `camxora_python/shared/widgets/date_picker_field.py`
- `camxora_python/features/music/widgets/history_card.py`
- `camxora_python/features/music/widgets/settings_strip.py`
- `camxora_python/features/progress/views/progress_view.py`
- `camxora_python/features/workflow/views/workflow_view.py`
- `camxora_python/features/image/widgets/controls_queue_card.py`
- `camxora_python/tests/test_shell_date_edit.py`
- `CHANGELOG.md`

## Migration / deploy

- Desktop restart only.

## Tests

- `pytest camxora_python/tests/test_shell_date_edit.py`

## Follow-ups

- None.
