# Image Page — Requirements Document

> **Document ID:** CAMXORA-PAGE-08-IMAGE  
> **Version:** 1.0.0  
> **Status:** Approved for implementation  
> **Phase:** 8  
> **Source of truth:** `camxora/src/renderer/src/features/image/ImageWorkspacePage.tsx`  
> **Supporting sources:** `useImageWorkspaceQuery.ts`, `ImageWorkspacePage.test.tsx`  
> **Target:** `camxora_python/features/image/`  
> **Last updated:** 2026-07-07

---

# 1. Document purpose

Complete A→Z requirements for the **Image workspace page** — date-filtered job queue, background/thumbnail previews, prompt autosave, retry/clear actions, and desktop file preview. Must match **100% functional parity** with Electron.

**UI rule (project standard):** Native PySide6 widgets + `shared/themes/deep_blue.py` QSS only. Use `account_card`, `StatCard` where cards are needed, standard `QDateEdit`, `QPushButton`, `QTextEdit` (`shell_text_edit`), `data_table` or equivalent row list, `QLabel` for previews. **No custom workflow-style panels or bespoke QSS blocks.**

**Build rule:** Do not mark Image complete until every item in **§15 Definition of Done** is checked.

---

# 2. Overview

## 2.1 What Image is

The Image page (`/app/image`) is the **image job review workspace**. Users filter music batches by date range, inspect grouped background/thumbnail jobs in a queue table, preview output images for the selected row, edit global background/thumbnail prompts (autosaved to settings), retry failed jobs, and clear queued jobs for the selected date range.

## 2.2 What Image is not

- Not the Music batch composer (**Music** phase — done)
- Not manual-image recovery/sync (**Progress** page owns sync actions)
- Not sample-pack administration or enqueue/run orchestration UI (Electron **removed** manual "Generate now" CTA; no enqueue/run buttons on this page)
- Not the video export workspace (**Video** phase)

## 2.3 Electron layout note (current)

The page uses a **two-column layout**:

- **Left (wide):** Controls + queue card — date filters, stat tiles, job queue table, dual prompt textareas, Clear Queue button
- **Right (narrow):** Two stacked preview cards — Background Preview, Thumbnail Preview

There is **no** separate "Batches" panel in current Electron UI.

---

# 3. Entry points & navigation

| Property | Value |
|----------|-------|
| Path | `/app/image` |
| Sidebar key | `image` |
| Label | Image |
| Title | Image |
| Eyebrow | Workspace |
| Description | Image workspace with date-filtered job queue, prompt editing, and output previews. |

**Router:** Replace `PlaceholderPage` for `image` in `app/router.py` with `ImageView`.

---

# 4. Data requirements

## 4.1 Workspace bootstrap (parallel fetch on page activate)

| # | Method | Path | Purpose |
|---|--------|------|---------|
| D-1 | GET | `/users/me` | Account context (loaded; optional display) |
| D-2 | GET | `/profiles` | Resolve profile names in queue rows |
| D-3 | GET | `/progress?limit=25&active_only=false` | Loaded in Electron hook (context; not rendered directly on page) |
| D-4 | GET | `/image-jobs?limit=200` | Job queue source |
| D-5 | GET | `/settings` | `imageBackgroundPrompt`, `imageThumbnailPrompt` (+ legacy `imagePrompt` fallback) |
| D-6 | GET | `/music/history?limit=25` | Batch date metadata for filtering |

**Python:** Single `ImageWorkspaceWorker` returning `ImageWorkspacePayload` dataclass. Progress fetch included for parity even if unused in UI.

**Poll interval:** 4s while page active (`refetchInterval: 4000` in Electron).

## 4.2 Mutations

| # | Method | Path | Trigger |
|---|--------|------|---------|
| M-1 | PATCH | `/settings` | Debounced prompt autosave (350ms) — `imageBackgroundPrompt`, `imageThumbnailPrompt` |
| M-2 | POST | `/image-jobs/retry` | Double-click failed job status chip — `{ job_ids: [id] }` |
| M-3 | POST | `/image-jobs/clear` | **Clear Queue** — one call per matched `batch_id` in filtered range |

## 4.3 Desktop file IO (local, not platform_api)

| # | Action | Trigger |
|---|--------|---------|
| F-1 | Read image file as bytes/base64 | Selected queue row changes — load BG/TH preview from `output_image_path` |
| F-2 | Open file in OS viewer | Double-click **success** job status chip with `output_image_path` |

**Python:** Extend `shared/services/file_service.py` with `read_file_bytes(path)` (or base64 helper). Use `open_path()` for success double-click.

---

# 5. Layout structure (standard theme)

```text
[ Error banner — workspace load/mutation failures ]

[ Loading state — "Loading image workspace..." ]

[ Main grid — ~2:1 columns on wide screens, stacked on narrow ]

  [ Left card — account_card: "Image Controls + Queue" ]
      Subtitle helper text
      Toolbar: From | To | Reload
      Stat row (3 tiles):
          Date Range | Matched Batches | Queue Status (statusLabel)
      Job Queue section:
          Header + queueStatusSummary (right)
          Table/list columns:
              Date | Channel | Role | BG | TH | BG File | TH File
          Footer detail line (errors + sample/style paths) when row selected
      Prompt row (2 columns):
          Background Prompt (textarea)
          Thumbnail Prompt (textarea)
      Actions:
          Clear Queue (destructive secondary)

  [ Right column — 2 stacked account_cards ]
      Background Preview — 260px-tall preview area (QLabel + QPixmap or placeholder text)
      Thumbnail Preview — same
```

**Hidden / not present in Electron:**

- "Generate now" button
- Enqueue / Run image jobs buttons
- Separate batches list panel

---

# 6. State model

## 6.1 Filter state

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `from_date` | `str` (yyyy-MM-dd) | today | Inclusive batch filter |
| `to_date` | `str` (yyyy-MM-dd) | today | Inclusive batch filter |

## 6.2 Prompt state (bound to settings)

| Field | Settings key | Fallback |
|-------|--------------|----------|
| Background prompt | `imageBackgroundPrompt` | legacy `imagePrompt` |
| Thumbnail prompt | `imageThumbnailPrompt` | `""` |

## 6.3 Selection + preview state

| Field | Type | Behavior |
|-------|------|----------|
| `selected_queue_key` | `str \| null` | `${batchId}-${profileId}-${role}` |
| `bg_preview` | image bytes / null | From selected row `bgJob.output_image_path` |
| `thumb_preview` | image bytes / null | From selected row `thJob.output_image_path` |
| `footer_detail` | `str` | BG/TH errors + basename of input/style paths |
| `status_label` | `str` | User-facing action feedback ("Ready", "Retry queued.", etc.) |
| `workspace_error` | `str \| null` | Banner message |

## 6.4 Queue row grouping

Group `ImageJobListItem` records by:

```text
key = f"{batch_id}-{profile_id}-{channel_role}"
```

Each row holds:

| Field | Source |
|-------|--------|
| `date_label` | Batch meta: `from_date` or `created_at[:10]`; if range spans days show `from → to` |
| `profile_name` | Profile lookup by `profile_id`, else raw id / "Unknown" |
| `role` | `ok` or `alt` |
| `bg_job` | job where `kind == "background"` |
| `th_job` | job where `kind == "thumbnail"` |

Sort: date label → role → profile name.

Auto-select first row when current selection disappears after refresh/filter.

---

# 7. Filtering logic

## 7.1 Batch date filter

Port `batchIsWithinRange(batch, fromDate, toDate)` from Electron:

- Batch span: `from = batch.from_date ?? batch.created_at[:10]`, `to = batch.to_date ?? batch.updated_at[:10]`
- Exclude if `fromDate` set and `to < fromDate`
- Exclude if `toDate` set and `from > toDate`

## 7.2 Job filter

Keep jobs whose `batch_id` is in filtered batch id set.

## 7.3 Queue summary string

When grouped rows exist:

```text
Rows {total} · Pending {n} · Running {n} · Failed {n} · Ready {n}
```

Counts from **filtered** raw jobs (not grouped rows). When no grouped rows:

- If batches matched: `"No image jobs yet for this date range."`
- Else: `"No batches found in the selected date range."`

---

# 8. Functional requirements

## FR-1 — Workspace load

| ID | Requirement |
|----|-------------|
| FR-1.1 | On `activate_page`, fetch workspace payload via worker |
| FR-1.2 | Show loading card until first successful load |
| FR-1.3 | Poll every 4s while page active |
| FR-1.4 | Stop poll on `deactivate_page` |
| FR-1.5 | Show error banner on load failure: "Unable to load the Image workspace right now." |
| FR-1.6 | Optional subtle "Refreshing…" hint while refetching (Electron secondary card) |

## FR-2 — Date filters

| ID | Requirement |
|----|-------------|
| FR-2.1 | From/To use standard `QDateEdit` + calendar popup (default today) |
| FR-2.2 | Changing dates recomputes filtered batches/jobs client-side (no extra API) |
| FR-2.3 | **Reload** button triggers immediate refetch; disabled/spinner while fetching |

## FR-3 — Stat tiles

| ID | Requirement |
|----|-------------|
| FR-3.1 | Date Range tile shows `{fromDate} → {toDate}` |
| FR-3.2 | Matched Batches tile shows filtered batch count |
| FR-3.3 | Queue Status tile shows `status_label` (default "Ready") |

## FR-4 — Job queue table

| ID | Requirement |
|----|-------------|
| FR-4.1 | Render grouped rows with 7 columns per §5 |
| FR-4.2 | BG/TH status cells show normalized status or "—" |
| FR-4.3 | Status styling: success=green tint, running=amber, failed=rose, pending=neutral |
| FR-4.4 | File columns show basename of `output_image_path` or "—" |
| FR-4.5 | Row click selects queue row + loads previews |
| FR-4.6 | Selected row highlighted (alternate background) |
| FR-4.7 | Empty state: "No jobs yet for the selected date range." (or loading message while loading) |

## FR-5 — Job interactions

| ID | Requirement |
|----|-------------|
| FR-5.1 | Double-click **failed** job chip → POST retry for that job id |
| FR-5.2 | Double-click **success** job chip with output path → `open_path(output_image_path)` |
| FR-5.3 | On retry success: clear error, set status "Retry queued.", refetch |
| FR-5.4 | On retry failure: status "Unable to retry job." + workspace error banner |

## FR-6 — Previews

| ID | Requirement |
|----|-------------|
| FR-6.1 | When selected row changes, async load BG/TH files from disk |
| FR-6.2 | Scale image to preview area (object-cover equivalent — fill keeping aspect, crop if needed) |
| FR-6.3 | Placeholder when no output: "Select a queue row to preview the … output." |
| FR-6.4 | Footer detail lists BG/TH errors and basenames for input/style paths when present |

## FR-7 — Prompt autosave

| ID | Requirement |
|----|-------------|
| FR-7.1 | Bind textareas to local prompt state initialized from settings |
| FR-7.2 | Debounce 350ms → PATCH settings |
| FR-7.3 | On PATCH failure: workspace error "Unable to save image settings right now." |
| FR-7.4 | Use `shell_text_edit` object name for both prompt fields |

## FR-8 — Clear queue

| ID | Requirement |
|----|-------------|
| FR-8.1 | Button disabled when no matched batch ids or while pending |
| FR-8.2 | Confirm dialog: "Clear Image job queue for the current date range? This cannot be undone." |
| FR-8.3 | POST clear for **each** filtered batch id; sum `deleted` counts |
| FR-8.4 | On success: status "Queue cleared for the selected date range.", refetch |
| FR-8.5 | On failure: status "Unable to clear queue." + error message |

---

# 9. API models (Python)

Add to `shared/models/platform.py`:

```python
class ImageJobListItem(BaseModel):
    id: str
    batch_id: str | None = None
    song_id: str | None = None
    profile_id: str | None = None
    kind: Literal["background", "thumbnail"]
    channel_role: Literal["ok", "alt"]
    prompt: str | None = None
    provider: str | None = None
    resolution: str = ""
    style_strength: float = 0
    input_image_path: str | None = None
    style_reference_path: str | None = None
    source_job_id: str | None = None
    status: Literal["pending", "running", "success", "failed", "cancelled"] | str
    attempt_count: int = 0
    output_image_path: str | None = None
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

class ImageJobsListResponse(BaseModel):
    items: list[ImageJobListItem] = Field(default_factory=list)

class ImageJobsRetryRequest(BaseModel):
    job_ids: list[str] | None = None
    batch_id: str | None = None

class ImageJobsRetryResponse(BaseModel):
    updated: int = 0

class ImageJobsClearRequest(BaseModel):
    batch_id: str | None = None
    statuses: list[str] | None = None

class ImageJobsClearResponse(BaseModel):
    deleted: int = 0
```

Extend `UserSettingsResponse` / settings dict parsing for image prompt keys if not already present.

---

# 10. Platform API methods

Add to `shared/services/platform_api.py`:

| Method | HTTP |
|--------|------|
| `list_image_jobs(*, batch_id=None, status=None, limit=200)` | GET `/image-jobs` |
| `retry_image_jobs(payload)` | POST `/image-jobs/retry` |
| `clear_image_jobs(payload)` | POST `/image-jobs/clear` |

(`get_settings`, `patch_settings`, `list_profiles`, `list_music_history`, `get_me`, `list_progress` already exist.)

---

# 11. Pure logic ports

Create `shared/lib/image_workspace.py`:

| Function | Purpose |
|----------|---------|
| `normalize_image_prompt_settings(settings)` | Legacy `imagePrompt` fallback |
| `batch_date_label(batch)` | Single day or range label |
| `batch_is_within_range(batch, from_date, to_date)` | Date filter |
| `build_queue_rows(jobs, batches, profiles)` | Group + sort rows |
| `format_job_status(status)` | Display normalization |
| `build_queue_status_summary(...)` | Summary string |
| `build_footer_detail(row)` | Error/path detail line |

Unit-test all of the above (mirror Electron logic exactly).

---

# 12. Workers

Extend `shared/workers/data_workers.py`:

| Worker | Purpose |
|--------|---------|
| `ImageWorkspaceWorker` | Parallel bootstrap fetch |
| `ImageRetryJobsWorker` | Retry mutation |
| `ImageClearQueueWorker` | Sequential clear per batch id |
| `ImagePreviewLoadWorker` | Optional — load preview bytes off UI thread |

Page uses `PollablePageMixin` with `poll_interval_ms = 4000`.

---

# 13. Test requirements

## Unit tests

| File | Covers |
|------|--------|
| `tests/test_image_workspace.py` | Filter, grouping, summary, footer detail, prompt normalize |

## View smoke tests

| Test | Covers |
|------|--------|
| Loading state | Loading message visible |
| Load error | Error banner visible |
| Success bind | Queue headers, prompts, preview placeholders |
| No Generate CTA | No "Generate now" button |
| Layout | "Image Controls + Queue", "Job Queue", both preview cards |
| Clear disabled | No batches → Clear Queue disabled |

Mirror assertions from `ImageWorkspacePage.test.tsx`.

---

# 14. Python module plan

```text
features/image/
  views/
    image_view.py                 # Main orchestrator + polling
  widgets/
    controls_queue_card.py        # Left card: filters, stats, queue, prompts, clear
    preview_card.py               # Reusable BG/TH preview panel
    error_banner.py               # Workspace errors (or reuse music/progress pattern)

shared/
  lib/image_workspace.py
  services/file_service.py        # + read_file_bytes
  workers/data_workers.py         # Image workers appended
```

---

# 15. Definition of Done

### Requirements & API
- [ ] I-1 Requirements doc reviewed and indexed
- [ ] I-2 Image job models + API methods in `PlatformApi`
- [ ] I-3 `image_workspace.py` lib with unit tests

### UI (standard theme)
- [ ] I-4 Two-column layout with controls/queue card + preview cards
- [ ] I-5 Date filters + Reload + stat tiles
- [ ] I-6 Job queue table with selection + status styling
- [ ] I-7 Background + thumbnail preview panels
- [ ] I-8 Dual prompt textareas with autosave

### Flows
- [ ] I-9 4s polling on active page
- [ ] I-10 Retry failed job (double-click)
- [ ] I-11 Open success output (double-click)
- [ ] I-12 Clear queue with confirm + multi-batch clear
- [ ] I-13 Preview load from local `output_image_path`

### Tests & docs
- [ ] I-14 All §13 tests passing
- [ ] I-15 `02_IMPLEMENTATION_STATUS.md` updated
- [ ] I-16 Manual verify against live `platform_api`

---

# 16. Reference — Electron test acceptance matrix

1. Renders "Image Controls + Queue", "Background Prompt", "Thumbnail Prompt"  
2. Renders "Background Preview", "Thumbnail Preview", "Job Queue"  
3. Does **not** render "Batches" section  
4. Does **not** render "Generate now" button  

---

# 17. Related docs

- [`../02_IMPLEMENTATION_STATUS.md`](../02_IMPLEMENTATION_STATUS.md)
- [`00_PAGE_BY_PAGE_STRATEGY.md`](00_PAGE_BY_PAGE_STRATEGY.md)
- [`07_MUSIC_REQUIREMENTS.md`](07_MUSIC_REQUIREMENTS.md)
- [`06_PROGRESS_REQUIREMENTS.md`](06_PROGRESS_REQUIREMENTS.md)
