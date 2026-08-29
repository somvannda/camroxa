# 2026-08-28 — Desktop Progress row selection and detail polish

Local desktop only. Sandbox and production were not deployed.

## Summary

Progress operational rows used colored Stage pills and a 16px PageTitle on Row Detail. The pills hid the selected-row color, cramped the Stage column, and made some rows taller than others. Row Detail wrapped a long title across several lines and stacked three tall cards.

## Product impact

- Progress uses Create chrome: header Refresh, studio table selection wash, compact 28px rows
- Summary cards keep navy panels with a thin semantic accent (purple / cyan / orange / red)
- Warning banner is an orange panel with View Details; load errors include Retry
- Stage uses compact Create badges; Progress shows percent plus a 3px bar; Export/Merge/YouTube use semantic text color
- Row Detail is a 380–500px inspector: title + purple stage, PIPELINE STATUS rows, WAITING/FAILED/COMPLETED/STATUS callout (wrapping export-not-ready issues live here, not in the page banner), BATCH, and wrapping RUN FOLDER. The operational table stretches to the panel; Channel stays compact and Album fills leftover width.

## Technical impact

- Stage cell widgets and `resizeRowsToContents()` are removed
- Progress QSS sets Create selection wash `rgba(99, 53, 217, 0.28)`
- Detail panel uses `ProgressDetailTitle` (13px), Batch + elided path, `tone=active` cyan for Downloading/Running, warning amber for Pending (no longer a green EXPORT dot)

## Files touched

- `camxora_python/features/progress/progress_styles.py`
- `camxora_python/features/progress/widgets/operational_rows_card.py`
- `camxora_python/features/progress/widgets/progress_detail_card.py`
- `camxora_python/tests/test_progress_view.py`
- `CHANGELOG.md`
- `docs/changelog/2026-08-28-desktop-progress-row-detail-polish.md`

## Migration/deploy

None. Desktop UI only.

## Tests

- `python -m pytest camxora_python/tests/test_progress_view.py -q`

## Follow-ups

None.
