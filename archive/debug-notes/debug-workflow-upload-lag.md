[OPEN] Debug Session: workflow-upload-lag

## Summary
- Symptom: App becomes very slow and the Workflow page appears to blink during the YouTube Upload pipeline step / while refreshing.
- Goal: Identify root cause with runtime evidence and implement a minimal fix without regressions.

## Environment
- OS: Windows
- App: python_app (PyQt6 desktop)

## Hypotheses (Falsifiable)
- H1: Workflow refresh rebuilds the entire timeline UI every tick (destroy/recreate widgets), causing visible blinking and heavy layout work.
- H2: Upload progress emits events too frequently (high-frequency UI updates), saturating the Qt event loop and making the UI lag.
- H3: Workflow refresh performs slow DB scans / filesystem scans on the UI thread, blocking repaint/input.
- H4: Upload step triggers repeated expensive directory scans (glob/stat) across many files, multiplied by the refresh timer.
- H5: Logging/terminal output during upload is too chatty and blocks (stdout flush or QTextEdit append), affecting responsiveness.

## Instrumentation Plan
- Measure per-refresh duration (start/end timestamps) and whether the UI is being rebuilt.
- Measure upload progress event frequency (events/sec) and UI update cost.
- Measure time spent in DB queries and filesystem scans during refresh.

## Repro Steps (to be filled)
- [ ] Open Workflow page
- [ ] Start/Resume a YouTube upload job
- [ ] Observe lag/blink and capture logs

## Evidence Log Pointers
- Debug Server logs: `.dbg/trae-debug-log-workflow-upload-lag.ndjson`

## Status
- Next: Start debug server, add instrumentation, reproduce, analyze logs, then implement minimal fix.

