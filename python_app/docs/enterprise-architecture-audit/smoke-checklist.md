# Smoke Validation Checklist

## Purpose
A practical, repeatable checklist to run after every extraction slice. Ensures no user-facing behavior was broken by structural changes.

---

## How to Use

1. After completing an extraction slice, run the **universal checks** every time
2. Then run the **feature-specific checks** for the area you touched
3. Mark all applicable items as `[x]` before starting the next slice

---

## Universal Checks (run after every slice)

### Compile & Import
- [ ] `python -m py_compile python_app/app/main_window.py` — no errors
- [ ] `python -m py_compile` on all changed files — no errors
- [ ] VS Code diagnostics — no new import errors or unresolved references

### App Launch
- [ ] App starts without crash or console traceback
- [ ] Main window renders all page tabs/sections
- [ ] No missing widget warnings or layout errors in console

### Navigation
- [ ] Click each page tab: Dashboard, Music, Image, Video, Progress, YouTube, Settings, Workflow
- [ ] Each page loads without error
- [ ] Sidebar navigation works correctly

### Bootstrap & Persistence
- [ ] App settings load on startup
- [ ] Profile dropdown shows saved profiles
- [ ] Template dropdown shows saved templates
- [ ] Database connection succeeds (no migration error popup)

### UI Bus / Signals
- [ ] No "unconnected signal" warnings in console
- [ ] No "method not found" tracebacks when clicking page actions

---

## Feature-Specific Checks

### Music Page
- [ ] Music page loads without error
- [ ] Profile settings panel renders
- [ ] Profile save/load works
- [ ] Sample count / role selection works
- [ ] Generate button is functional
- [ ] Music history / recent tracks display

### Image Page
- [ ] Image page loads without error
- [ ] Prompt input works
- [ ] Generate button is functional
- [ ] Image history / samples display
- [ ] Sample selection works

### Video Page
- [ ] Video page loads without error
- [ ] Workspace renders preview area
- [ ] Template selection works
- [ ] Resolution settings work
- [ ] Background image picker works
- [ ] Spectrum visualizer preview works
- [ ] Export button initiates correctly
- [ ] Merge functionality works (if triggered)

### Progress Page
- [ ] Progress page loads without error
- [ ] Job table renders rows
- [ ] Refresh button works
- [ ] Context menu actions work (retry, cancel, restart)
- [ ] Status text updates correctly (Pending, Running, Done, Failed, Queued)
- [ ] Terminal progress rendering works

### YouTube Page
- [ ] YouTube page loads without error
- [ ] Jobs table renders
- [ ] OAuth connect/disconnect flow works
- [ ] Profile-channel connection works
- [ ] Playlist dropdown loads
- [ ] Upload queue status displays
- [ ] Retry / Cancel actions work on jobs
- [ ] Upload progress updates in real time
- [ ] Merged-output scan works

### Settings Page
- [ ] Settings page loads without error
- [ ] All settings sections render
- [ ] Settings save/load works
- [ ] Database migration button works
- [ ] Data reset actions work

### Auto-Video / Export
- [ ] Auto-video channel starts after music generation
- [ ] FFmpeg path resolution works
- [ ] MP4 files are found and queued
- [ ] Merge completes successfully
- [ ] Export progress messages display

---

## Performance & Stability Checks

### Console Health
- [ ] No repeated traceback spam in console
- [ ] No "QTimer: timers cannot be started from another thread" errors
- [ ] No "AttributeError" or "NameError" during normal interaction

### Memory & Responsiveness
- [ ] App does not freeze during page navigation
- [ ] App does not freeze during job operations
- [ ] Preview area does not cause sustained high CPU

### Background Workers
- [ ] Timers fire at expected intervals (not racing, not stalled)
- [ ] Thread cleanup works on app close
- [ ] No orphan threads left after operations complete

---

## Post-Slice Review Questions

- [ ] Did any behavior feel different from before the slice?
- [ ] Did any status text or error message change wording?
- [ ] Did any page take longer to load?
- [ ] Did any button click produce an unexpected result?
- [ ] Are there any new console warnings that were not there before?

If any answer is "yes", investigate before proceeding.

---

## Quick Smoke (1-Minute Version)

When time is tight, run this minimum set:

- [ ] `py_compile` on changed files — passes
- [ ] App launches — no crash
- [ ] All page tabs load — no error
- [ ] Feature-specific action for the extracted area — works
- [ ] Console — no new tracebacks

This quick check catches ~90% of extraction regressions.
