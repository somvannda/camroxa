# Workflow Upload Performance (Technical)

## Existing Architecture (Verified)
- Workflow live refresh:
  - `WorkflowViewMixin._ensure_workflow_timers()` uses a `QTimer(interval=2000)` to call `_refresh_workflow_async(force=False)` on a loop.
  - `_refresh_workflow_async()` collects rows in a background thread, then applies UI changes on the UI thread.
- Timeline rendering:
  - `WorkflowTimeline.set_steps()` previously deleted and recreated all widgets (steps + connectors) on every refresh.
- YouTube upload progress:
  - Upload thread emits `youtube_upload_progress` events for every uploader callback.
  - UI handler updates labels/table/terminal output per event.

## Root Causes (Verified)
1) Workflow blinking
- `WorkflowTimeline.set_steps()` performed full widget teardown + rebuild on each refresh, causing layout reflow and visible flicker.
2) UI-thread saturation during upload
- `youtube_upload_progress` can emit at high frequency, triggering repeated UI updates.

## Implemented Fixes
### 1) Diff-update timeline instead of rebuild
- `WorkflowTimeline.set_steps()` now:
  - Rebuilds only if the step “structure” changes (same step keys => update in-place).
  - Updates existing `ProgressRingStep` instances via `set_data()` and only updates connector colors.
  - Caches rendered icons per `(lucide, icon_color)` to avoid repeated SVG rendering work.

### 2) Avoid rebuilding the Workflow run combo every refresh
- `WorkflowViewMixin._apply_workflow_rows()` now:
  - Tracks the previous key list.
  - Only clears/recreates the combo model when keys change.
  - Otherwise updates item text in-place and preserves selection without forcing downstream rebuilds.

### 3) Throttle YouTube upload progress events
- The `on_progress` callback passed into `upload_video(...)` now emits at most:
  - every ~250ms, or
  - when integer percent increases by >= 1, or
  - always at 100%.

## Affected Files
- `python_app/views/components.py`
- `python_app/views/workflow_view.py`
- `python_app/app/main_window.py`

## Verification Strategy
- Open Workflow page with live refresh enabled.
- Start a YouTube upload and observe:
  - No visual blinking in the timeline.
  - App remains responsive (no obvious UI freezes).
  - Progress still updates regularly (but not excessively spammy).

