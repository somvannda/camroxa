# 2026-08-28 — Desktop Image selected-album inspector

Local desktop only. Sandbox and production were not deployed.

## Summary

The Image page already used Create chrome. Queue rows, prompts, and previews still felt disconnected. Selecting an album now becomes the page context: the same title appears above the queue and in the preview inspector, previews show Ready/Generating/Failed, and Open/Copy use the existing file actions.

Generation, filters, retry, regenerate, and queue loading are unchanged.

## Product impact

- SELECTED ALBUM strip on the left and matching title on the right
- QUEUE ITEMS count, Clear Filters, and compact status captions
- Preview status badges plus Open / Copy path when a file exists
- Left/right QSplitter so the inspector stays visible

## Technical impact

- `QTableWidget` queue is unchanged (Create table helper)
- Preview cards emit `open_requested` into the existing ImageOpenWorker path

## Files touched

- `camxora_python/features/image/views/image_view.py`
- `camxora_python/features/image/widgets/controls_queue_card.py`
- `camxora_python/features/image/widgets/preview_card.py`
- `camxora_python/features/image/image_styles.py`
- `camxora_python/tests/test_image_view.py`
- `CHANGELOG.md`
- `docs/changelog/2026-08-28-desktop-image-album-inspector.md`

## Migration/deploy

None. Desktop UI only.

## Tests

- `python -m pytest camxora_python/tests/test_image_view.py camxora_python/tests/test_image_workspace.py -q`
