# Workflow Upload Performance (Workflow Blink + Lag)

## Goals
- Stop Workflow page blinking/flickering during live refresh.
- Prevent the app UI thread from being overwhelmed during the YouTube Upload step.
- Keep real-time updates, but avoid unnecessary widget rebuilds and repaint storms.

## Tasks
- [completed] Inspect Workflow live-refresh and identify UI-churn hotspots.
- [completed] Stop Workflow run selector from being fully rebuilt on every refresh when keys are unchanged.
- [completed] Stop timeline widgets from being deleted/recreated on every refresh; update in-place when the step structure is unchanged.
- [completed] Add throttling to YouTube upload progress events to reduce UI-thread pressure.
- [pending] Verify:
  - Workflow page no longer blinks during refresh.
  - Upload step still shows progress updates (percent increases smoothly but not excessively frequent).
  - No regressions in Progress page/table updates.
- [pending] Update `DEVELOPMENT_LOG.md`.

