# 2026-08-28 — Desktop Image queue summary cards

Local desktop only. Sandbox and production were not deployed.

## Summary

The Image queue still used one shared status bar and two extra count labels. Those labels did not help the album-first workflow: “N tracks in batch” repeated song-level detail, and the QUEUE ITEMS number duplicated the Rows card.

The status bar is now five NestedPanel cards with Lucide icons. The two labels stay wired for tests but are hidden in the UI.

Generation, filters, retry, regenerate, and queue loading are unchanged.

## Product impact

- Rows / Pending / Running / Failed / Ready each have their own card and icon
- QUEUE ITEMS heading no longer shows a count
- Footer no longer shows “N tracks in batch”
- Selected album title on the preview column uses a transparent outlined card
- BG/TH job errors and workspace errors go to the shell footer; the page banner stays hidden
- QUEUE ITEMS heading removed; status cards sit at the top, then Controls & Queue, then the table

## Technical impact

- `set_footer_detail()` drops parts containing `tracks in batch`
- `_queue_count` still updates so existing assertions keep working
- Image view tests close leftover Qt top-level widgets after each case

## Files touched

- `camxora_python/shared/lib/image_workspace.py`
- `camxora_python/features/image/widgets/controls_queue_card.py`
- `camxora_python/features/image/views/image_view.py`
- `camxora_python/tests/test_image_workspace.py`
- `camxora_python/features/image/image_styles.py`
- `camxora_python/features/create/widgets/studio_panel.py`
- `camxora_python/tests/test_image_view.py`
- `CHANGELOG.md`
- `docs/changelog/2026-08-28-desktop-image-queue-summary-cards.md`

## Migration/deploy

None. Desktop UI only.

## Tests

- `python -m pytest camxora_python/tests/test_image_view.py -q`
