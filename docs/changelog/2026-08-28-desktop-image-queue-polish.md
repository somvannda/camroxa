# 2026-08-28 — Desktop Image Job Queue polish

Local desktop only. Sandbox and production were not deployed.

## Summary

The Image Job Queue table was wrapping cell text in narrow columns (Role, BG, TH, file names). That made most rows taller than one line and drew inner scrollbars. The last checkmark-only row stayed compact because its text fit on one line.

This change locks every queue row to that compact height, paints selection with studio purple, widens Role so Primary / Secondary are readable, and turns the `Rows · Pending · Running · Failed · Ready` line into a card.

## Product impact

- Queue rows stay one line tall; long album / file names elide with a tooltip
- Selected row uses brand purple `#6335D9`
- Role column is wide enough for Primary and Secondary
- Queue counts sit in a NestedPanel card under JOB QUEUE

## Technical impact

- `QTableWidget` word wrap is off; vertical header is a fixed 32px
- Status cells use foreground color only so QSS selection can paint the whole row
- `parse_queue_status_counts()` splits the existing summary string for the card

## Files touched

- `camxora_python/features/image/widgets/controls_queue_card.py`
- `camxora_python/features/image/image_styles.py`
- `camxora_python/shared/lib/image_workspace.py`
- `camxora_python/tests/test_image_view.py`
- `camxora_python/tests/test_image_workspace.py`
- `CHANGELOG.md`
- `docs/changelog/2026-08-28-desktop-image-queue-polish.md`

## Migration/deploy

None. Desktop UI only.

## Tests

- `python -m pytest camxora_python/tests/test_image_view.py camxora_python/tests/test_image_workspace.py -q`

## Follow-ups

None.
