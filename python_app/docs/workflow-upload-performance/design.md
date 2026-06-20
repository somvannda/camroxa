# Workflow Upload Performance (UX)

## Problem Summary
- Workflow page performs a live refresh on a timer.
- During YouTube upload, the UI can feel slow and the Workflow timeline can visually blink.

## UX Principles
- Real-time should feel stable:
  - Update values in-place.
  - Avoid layout teardown/reflow every refresh.
- Reduce “noise”:
  - Upload progress can update frequently, but the UI should not repaint on every tiny byte-change.

## Desired User Experience
- Workflow:
  - Timeline stays visually stable (no flicker).
  - Percent increases over time without the whole timeline disappearing/reappearing.
- Upload:
  - Progress updates feel responsive (at least several updates per second at most).
  - Other parts of the app remain usable while uploading.

## States
- Loading/refresh:
  - Workflow status label can update, but the timeline should not rebuild.
- Empty:
  - When no runs exist, timeline clears once and stays stable.

