# 6. Image

> **Feature prefix:** `IM-`
> **Route:** `/app/image`
> **Phase:** P5
> **Sources of truth:**
> - `camxora_python/features/image/views/image_view.py`
> - `camxora_python/features/image/widgets/*`
> - `camxora_python/.docs/pages/08_IMAGE_REQUIREMENTS.md`
> - `platform_api/routers/{image_jobs,image_prompts,profiles,settings_router,music_history,progress}.py`

---

## 1. Purpose

The image job review workspace: filter batches by date, inspect grouped background and
thumbnail jobs, preview outputs, edit global prompts with autosave, retry failed jobs, and
clear queued jobs.

Not the Music composer, not manual recovery (Progress), not video.

---

## 2. Data

### 2.1 Bootstrap (parallel)

| # | Method | Path | Purpose |
|---|---|---|---|
| 1 | GET | `/users/me` | Account context |
| 2 | GET | `/profiles` | Resolve profile names |
| 3 | GET | `/progress?limit=25&active_only=false` | Context parity (not rendered) |
| 4 | GET | `/image-jobs?limit=200` | Job queue |
| 5 | GET | `/settings` | `imageBackgroundPrompt`, `imageThumbnailPrompt`, legacy `imagePrompt` |
| 6 | GET | `/music/history?limit=25` | Batch date metadata |

### 2.2 Mutations

| # | Method | Path | Trigger |
|---|---|---|---|
| M-1 | PATCH | `/settings` | Prompt autosave (350 ms) |
| M-2 | POST | `/image-jobs/retry` | Double-click failed status |
| M-3 | POST | `/image-jobs/clear` | Clear Queue (one per matched batch id) |

### 2.3 Local file I/O

| # | Action | Trigger |
|---|---|---|
| F-1 | Read image bytes from `output_image_path` | Selected row changes |
| F-2 | Open the output in the OS viewer | Double-click a success status |

---

## 3. Layout

```
[ error banner ]
[ loading "Loading image workspace..." ]

┌──────────────────────────────────────────────┬──────────────────────┐
│ Image Controls + Queue (~2fr)                │ Background Preview   │
│ subtitle                                     │ 260 px               │
│ [From] [To] [Reload]                         ├──────────────────────┤
│ [Date Range] [Matched Batches] [Queue Status]│ Thumbnail Preview    │
│ Job Queue + summary                          │ 260 px               │
│ table: Date | Channel | Role | BG | TH | BG File | TH File          │
│ footer detail (errors/paths)                 │                      │
│ [Background Prompt] [Thumbnail Prompt]       │                      │
│ [Clear Queue]                                │                      │
└──────────────────────────────────────────────┴──────────────────────┘
```

No "Generate now", no enqueue/run buttons, no separate Batches panel.

---

## 4. Features

### 4.1 Load and refresh

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| IM-01 | Bootstrap | Six calls in parallel; partial failures degrade gracefully | P0 |
| IM-02 | Loading | Loading card until the first success | P0 |
| IM-03 | Poll | Refetch every 4 s while active | P0 |
| IM-04 | Stop poll | Stop on page deactivate | P0 |
| IM-05 | Error banner | "Unable to load the Image workspace right now." | P0 |
| IM-06 | Refreshing hint | Quiet "Refreshing…" while a refetch is in flight | P1 |
| IM-07 | Stale data | Keep rows on a later failure and mark stale | P1 |

### 4.2 Filters and stats

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| IM-08 | From/To | Date pickers default today; client-side filter | P0 |
| IM-09 | Range filter | Excludes batches outside the inclusive range | P0 |
| IM-10 | Reload | Immediate refetch; disabled/spinner while fetching | P0 |
| IM-11 | Date Range tile | `{from} → {to}` | P0 |
| IM-12 | Matched Batches tile | Count of filtered batches | P0 |
| IM-13 | Queue Status tile | `status_label`, default "Ready" | P0 |

### 4.3 Queue

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| IM-14 | Grouping | Key `{batch_id}-{profile_id}-{role}`; BG and TH in one row | P0 |
| IM-15 | Sort | Date label → role → profile name | P0 |
| IM-16 | Columns | Date, Channel, Role, BG, TH, BG File, TH File | P0 |
| IM-17 | Status cells | Normalised status or "—" | P0 |
| IM-18 | Status styling | Success green, running amber, failed rose, pending neutral | P0 |
| IM-19 | File cells | Basename of output path or "—" | P0 |
| IM-20 | Selection | Row click selects and loads previews | P0 |
| IM-21 | Auto-select | First row when the current selection disappears | P0 |
| IM-22 | Summary | `Rows {n} · Pending {n} · Running {n} · Failed {n} · Ready {n}` | P0 |
| IM-23 | Empty states | Jobs empty vs batches empty have distinct copy | P0 |
| IM-24 | Dense layout | ≥ 8 rows visible at 900 px height | P0 |

### 4.4 Interactions

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| IM-25 | Retry failed | Double-click a failed chip → retry that job id | P0 |
| IM-26 | Retry success | Status "Retry queued."; clear error; refetch | P0 |
| IM-27 | Retry failure | "Unable to retry job." + banner | P0 |
| IM-28 | Open success | Double-click a success chip with a path → OS viewer | P0 |
| IM-29 | Open missing path | Explain the file is missing; do not crash | P1 |
| IM-30 | Keyboard retry | Enter on a focused failed chip performs the retry | P1 |
| IM-31 | Multi-select | Select several failed jobs and retry together | P2 |

### 4.5 Previews

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| IM-32 | Load on select | Read BG/TH files off the UI thread | P0 |
| IM-33 | Fit | Fill the preview area preserving aspect, crop if needed | P0 |
| IM-34 | Placeholder | "Select a queue row to preview the background/thumbnail output." | P0 |
| IM-35 | Error | Missing/corrupt file shows a readable placeholder | P0 |
| IM-36 | Zoom | Click to open a lightbox at native size | P2 |
| IM-37 | Footer detail | BG/TH errors + basenames of input/style paths | P0 |
| IM-38 | File size | Shows dimensions and size in the preview header | P2 |

### 4.6 Prompt autosave

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| IM-39 | Fields | Background and Thumbnail prompts, multiline | P0 |
| IM-40 | Init | Loaded from settings; legacy `imagePrompt` fallback | P0 |
| IM-41 | Debounce | 350 ms → PATCH settings | P0 |
| IM-42 | Saved state | Quiet "Saved" indicator, resets after 1.8 s | P0 |
| IM-43 | Error | "Unable to save image settings right now." | P0 |
| IM-44 | Guard | No PATCH until initial settings are applied | P0 |
| IM-45 | Reset | Restore the last server value without saving | P1 |

### 4.7 Clear queue

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| IM-46 | Enablement | Disabled when no matched batch ids or while pending | P0 |
| IM-47 | Confirmation | "Clear Image job queue for the current date range? This cannot be undone." | P0 |
| IM-48 | Scope | One POST per matched batch id; sum `deleted` | P0 |
| IM-49 | Success | "Queue cleared for the selected date range."; refetch | P0 |
| IM-50 | Failure | "Unable to clear queue." + error detail | P0 |
| IM-51 | Safety | Generated files on disk are not deleted; copy says so | P1 |

---

## 5. States

| State | Tiles | Table | Previews | Prompts |
|---|---|---|---|---|
| Loading | `--` | skeleton | placeholders | disabled |
| Success | values | rows | selected image | enabled |
| Empty | values | message | placeholders | enabled |
| Error | last values | stale rows or empty | last image | enabled |
| Retrying | values | row busy | unchanged | enabled |
| Clearing | values | busy | unchanged | enabled |

---

## 6. Tests

| ID | Scenario | Assert |
|---|---|---|
| IM-T1 | Grouping | BG and TH for the same batch/profile/role form one row |
| IM-T2 | Date filter | Inclusive boundaries; out-of-range excluded |
| IM-T3 | Summary | Counts match the filtered raw jobs |
| IM-T4 | Retry | Double-click sends the correct job id and refreshes |
| IM-T5 | Open success | Calls open-path with the output path |
| IM-T6 | Clear | One call per batch; deleted total shown |
| IM-T7 | Prompt autosave | 350 ms debounce; no loop; error state |
| IM-T8 | Preview | Correct BG/TH files loaded for the selected row |
| IM-T9 | No generate CTA | The page contains no "Generate now" button |
| IM-T10 | Poll lifecycle | 4 s while visible; stopped when hidden |

---

## 7. Definition of Done

- [ ] IM-01 … IM-51 implemented; all `P0` verified against sandbox.
- [ ] Grouping and filtering parity verified with a fixture of 20 jobs.
- [ ] Preview load does not block the UI thread.
- [ ] Clear queue and retry verified against sandbox.
- [ ] IM-T1 … IM-T10 pass.
- [ ] Visual baseline approved.
