# Workflow Timeline (Technical)

## Existing Architecture (Code Anchors)
- Navigation entry exists already:
  - Primary nav includes `("workflow", "Workflow", "workflow")` in [core_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/core_view.py#L97-L122)
- Workflow page currently uses a placeholder:
  - `("workflow", self._build_primary_placeholder_page(...))` in [main_window.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L7671-L7680)
- The canonical pipeline model already exists (and is DB-backed):
  - [MainWindow._collect_progress_rows](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L5785-L5999)
  - This resolves per Batch × Channel (OK/ALT) metrics:
    - Songs saved/expected
    - BG/TH image job statuses
    - Output folder MP3/MP4 counts
    - Merge output presence
    - YouTube job status + live upload % (`_youtube_progress_by_job_uid`)

## Data Model
### Source
- Reuse `_collect_progress_rows(...)` to avoid duplicating pipeline logic.
- Workflow page can call it with:
  - date filters (from/to)
  - `active_only` flag
  - a higher limit (e.g., 50) to populate the selector list

### Derived “Step State”
Each selected progress row is converted into:
```text
StepState:
  key: music | image | convert | merge | youtube
  title: str
  icon: lucideName
  percent: 0..100
  state: inactive | running | done | failed | cancelled
  details: list[str] (1–2 lines)
```

### Percent Rules (v1)
- Music:
  - `saved/expected` → percent, clamp 0..100
- Image:
  - background READY contributes 50%
  - thumbnail READY contributes 50%
  - RUNNING/PENDING contributes 0% (but state is running)
- Convert:
  - MP4 `count/expected` → percent
- Merge:
  - merged present → 100% else 0%
- YouTube:
  - READY → 100%
  - RUNNING → percent from `_youtube_progress_by_job_uid` when available (else show “Uploading…” and keep percent as last known or 0)
  - PENDING → 0%
  - FAILED/BLOCKED → 0% (failed state)
  - CANCELLED → 0% (cancelled state)

## UI Implementation
### New View Mixin
- Add `python_app/views/workflow_view.py`:
  - `WorkflowViewMixin._build_workflow_workspace_page()`
  - `WorkflowViewMixin._refresh_workflow_async()` background thread fetch
  - `WorkflowViewMixin._apply_workflow_model(...)` UI render

### Timeline Widgets
- Add painted widgets into `python_app/views/components.py`:
  - `ProgressRingStep(QWidget)`:
    - draws muted ring + active arc via `QPainter.drawArc`
    - renders lucide SVG icon in center
    - renders percent text inside circle
    - label + detail labels below
  - `WorkflowTimeline(QWidget)`:
    - lays out steps horizontally with connector widgets between

### MainWindow Wiring
- Add mixin to `MainWindow(...)` inheritance list.
- Replace placeholder in `primary_pages` with real workflow page builder:
  - `("workflow", self._build_workflow_workspace_page())`

## Performance & Safety
- Avoid repeated heavy queries:
  - refresh only when Workflow page is active/visible
  - throttle refresh (e.g., 1500–2500ms)
- UI thread safety:
  - perform DB work in background thread
  - apply results via `bus.ui_invoke.emit(...)`

## Testing Strategy
- Manual:
  - Open Workflow page, confirm it auto-selects an active row.
  - Trigger music/image generation and confirm step percent + details update.
  - Start a YouTube upload and confirm the circle shows Uploading %.
- Automated:
  - `python -m compileall -q python_app`
