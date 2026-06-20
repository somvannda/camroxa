## Pure Python: Visualizer Migration - Design

### Product Goal
Keep the project structure clean and Python-only by eliminating the root-level `visualizer/` folder and nesting the renderer inside the Python app.

### User Impact
- Developers only see Python runtime folders at the repo root (plus `archive/`).
- Python preview/export continues to work without changing UI behavior.

### UX / Behavior
- No UI changes.
- No changes in export results expected.
