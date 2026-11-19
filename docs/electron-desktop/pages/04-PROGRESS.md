# 4. Progress

> **Feature prefix:** `PG-`
> **Route:** `/app/progress`
> **Phase:** P3
> **Sources of truth:**
> - `camxora_python/features/progress/views/progress_view.py`
> - `camxora_python/.docs/pages/06_PROGRESS_REQUIREMENTS.md`
> - `camxora_python/shared/lib/video_runtime_inspection.py`
> - `camxora_python/shared/lib/manual_asset_paths.py`
> - `camxora_python/shared/services/music_download_coordinator.py`

---

## 1. Purpose

The operational view of the pipeline. It answers: what is running, what is stuck, what
failed, and what needs a human. It is not the lane board (Workflow) and does not replace the
Music/Image/Vizzy pages.

**2.0.0 scope:** converter, merge and reel are **live pipeline stages**. YouTube upload keeps
the existing 1.7.1 publication/manual flow; Auto-Upload stays disabled. Progress consumes
render/encode/merge events from the pipeline service and allows a retry of only the failed
stage. Historical runs with stored values still render correctly.

---

## 2. Data

| Source | Endpoint / module | Use |
|---|---|---|
| Progress rows | `GET /progress` | Main table |
| Settings | `GET /settings` | `imageSourceMode` for manual recovery UI |
| Pending downloads | `GET /music/downloads/pending?limit=24` | Main-process coordinator (download queue card reads its snapshot) |
| Download completion | `POST /music/downloads/sync` | Acknowledge finished targets (1.7.1 parity) |
| Manual sync | `POST /image-jobs/sync-manual` | Continue pipeline after manual images |
| Local overlay | `video_runtime_inspection` | Converter/merge truth from local files |

---

## 3. Layout

```
[ Toolbar: From | To | Active only | Limit | Stage | Refresh ]
[ Helper subtitle ]
[ Summary line: API summary + desktop runtime suffix ]
[ Manual mode notice — only when imageSourceMode = manual ]
[ 4 × StatCard: Active runs | Converter/Merger | Waiting on user | Failed/Blocked ]
[ Meta line: visible rows · pending downloads · stage filter ]
[ Error banner — with stale-data retention ]
[ Operational table (card) ]
[ Download queue (card, hidden when empty) ]
```

The toolbar sits on the page background, not inside a card.

---

## 4. Features

### 4.1 Loading and filters

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| PG-01 | Bootstrap | Loads rows, settings and pending downloads in parallel | P0 |
| PG-02 | Dates | From/To date pickers; default is today; changing filters refetches | P0 |
| PG-03 | Active only | Checkbox filters to non-terminal stages | P0 |
| PG-04 | Limit | Selectable row cap (25/50/100/200); default 50 | P0 |
| PG-05 | Stage filter | All, music, image, converter, merger, YouTube, done, error | P0 |
| PG-06 | Refresh | Immediate refetch; disabled while fetching; shows last updated | P0 |
| PG-07 | Invalid range | To < From shows an inline error and does not fetch | P0 |
| PG-08 | Summary line | API summary + local runtime suffix (e.g. "3 local renders") | P1 |

### 4.2 Stat cards

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| PG-09 | Active runs | Rows whose effective stage is not done/error | P0 |
| PG-10 | Converter / Merger | Effective stage is converter or merger | P0 |
| PG-11 | Waiting on user | Manual image mode + image stage + inspection not ready | P0 |
| PG-12 | Failed / blocked | Effective stage = error or effective status = failed | P0 |
| PG-13 | Card anatomy | Label + figure; no decorative icon | P0 |

### 4.3 Operational table

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| PG-14 | Columns | Batch, Run Date, Channel, Status, Music, Image, Converter, Merge, YouTube, Stage, Notes, Updated | P0 |
| PG-15 | Row identity | Batch id + date are stable; duplicate rows are not shown | P0 |
| PG-16 | Music cell | Status plus download pending/ready sub-line | P0 |
| PG-17 | Image cell | Status plus manual/auto indicator | P0 |
| PG-18 | Converter cell | Local runtime truth when available, else API stage | P0 |
| PG-19 | Merge cell | Same local/API precedence | P0 |
| PG-20 | YouTube cell | Upload state and link when present | P0 |
| PG-21 | Stage column | Single effective stage, pill with semantic tint | P0 |
| PG-22 | Notes column | Short reason; expand for detail | P0 |
| PG-23 | Updated | Relative + absolute time on hover | P0 |
| PG-24 | Row click | Opens the row detail panel | P0 |
| PG-25 | Sort | Default newest first; stable sort on refresh | P1 |
| PG-26 | Empty | "No runs match these filters." with a clear-filters action | P0 |
| PG-27 | Loading | Skeleton rows, not an empty table | P0 |

### 4.4 Row detail

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| PG-28 | Detail panel | Batch, channel, dates, stage timeline, notes | P0 |
| PG-29 | File paths | Music/image/video paths with Open folder / Reveal | P0 |
| PG-30 | Stage timeline | Music → Image → Converter → Merge → YouTube with current stage | P0 |
| PG-31 | Retry | Retry the failed stage only; confirms scope | P1 |
| PG-32 | Copy run id | Copies the batch id | P1 |

### 4.5 Manual asset recovery

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| PG-33 | Manual notice | When `imageSourceMode=manual`, a notice explains the hand-off | P0 |
| PG-34 | Inspection | Lists run-directory images and whether expected files exist | P0 |
| PG-35 | Open folder | Opens the OK/ALT run directory in the OS | P0 |
| PG-36 | Continue pipeline | Calls sync-manual, then refreshes; disabled until files are ready | P0 |
| PG-37 | Missing files | Explains which file is missing and where it must go | P0 |
| PG-38 | Permission error | Surfaces a readable error, not a raw OS exception | P1 |

### 4.6 Download queue

**Status: implemented in the main process (P4).** The shell no longer just displays
pending rows: `electron/services/download-coordinator.ts` polls the endpoint, writes the
files and reports completion. The renderer reads snapshots over IPC.

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| PG-39 | Visibility | Card hidden when the coordinator tracks nothing | P0 |
| PG-40 | Rows | Song, channel, target path, state, progress (live bytes) | P0 |
| PG-41 | Live progress | `downloads:list` snapshots at 5 s + `downloads:changed`; state machine `queued → downloading → done/failed/cancelled` | P0 |
| PG-42 | Retry failed | Re-queues one failed/cancelled row; disabled with a reason when the row has no URL; a gone URL fails with `DOWNLOAD_URL_GONE` | P1 |
| PG-43 | Open folder | Reveals a finished file inside the output root, or opens the target folder | P1 |

#### 4.6.1 Shell coordinator

| Concern | Rule |
|---|---|
| Poll | `GET /music/downloads/pending?limit=24` through the authenticated API client. 12 s idle, 4 s while work is queued or running (1.7.1 parity). The shell asks for an early poll when the card is visible (1.5 s minimum gap), coalesced single-flight. |
| Output root | The device **Suno output dir** from Settings; the managed `<userData>/downloads` folder when it is unset. Nothing is ever written outside that root. |
| Target resolution | Absolute `target_path` must already be inside the root; a relative target is joined to it; otherwise `output_dir` (inside the root) + a sanitised `<track> <title>.mp3`. `..` segments, absolute escapes and folder targets are rejected with specific errors. Parent folders are created. |
| Download | `fetch` the URL, stream chunks to `<name>.camxora-part-<uuid>` in the target folder, then rename over the real name. A cancel, failure or quit deletes the partial file. |
| Concurrency | 2 by default (`CAMXORA_DOWNLOAD_CONCURRENCY`, clamped 1–3). |
| Retry | 3 attempts for retryable failures (HTTP 429/5xx/network/truncated body) with 0.75 s then 2 s backoff. 404/410, 401/403, unsupported URLs and containment failures are permanent and never retried automatically. |
| Dedupe | Key is `task_id::primary|secondary`. A repeated pending item is never fetched twice, a finished row is not re-downloaded, and an existing non-empty file is accepted as done without a request. |
| Report | Finished rows are acknowledged once through `POST /music/downloads/sync` (`downloaded_primary/secondary` + output dirs) so the server stops listing them as pending. Failures keep the file and retry the acknowledgement on the next cycle. |
| URLs | Only `http(s)`. `http` on loopback is accepted only when `CAMXORA_E2E=1`. URLs never reach the renderer, and the session bearer token is never attached to a download request. |
| Lifecycle | Runs in the main process, so route changes and focus changes do not stop it. `before-quit` aborts streams and deletes partial files. Pause/resume is a real shell control. |

Deliberate deviations from 1.7.1: the poll cadence is unchanged, but polling is never paused
for a preview/modal (it is network I/O in the main process, not the UI thread); an existing
file is accepted instead of re-downloaded; and a missing/invalid/gone URL surfaces as a failed
row with a specific message instead of a silent skip.

### 4.7 Polling and lifecycle

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| PG-44 | Default poll | 12 s while the page is active | P0 |
| PG-45 | Active-only poll | 4 s when "Active only" is on | P0 |
| PG-46 | Downloads poll | 5 s while visible (`use-download-queue`), stopped when hidden; the coordinator keeps its own 12 s/4 s cadence in the main process | P0 |
| PG-47 | Hidden page | All timers stop; a single refresh on return | P0 |
| PG-48 | Single-flight | Overlapping polls never stack requests | P0 |
| PG-49 | Error/stale | On poll failure, keep rows and mark "Stale · last updated …" | P0 |
| PG-50 | Live pipeline stages | Converter, merge and reel are live; each shows progress and can retry only the failed stage; upload stays the existing flow; historical values still render; a legacy Camxora template blocks with the 2.0.0 policy | P0 |

---

## 5. States

| State | Toolbar | Stats | Table | Downloads |
|---|---|---|---|---|
| Loading | enabled | `--` | skeleton | hidden |
| Success | enabled | numbers | rows | visible while the coordinator tracks items |
| Empty | enabled | 0s | empty message | hidden |
| Error | enabled | last values | stale rows or empty + banner | last values |
| Manual mode | enabled | waiting count | manual actions | visible |

---

## 6. Tests

| ID | Scenario | Assert |
|---|---|---|
| PG-T1 | Filters | Date/stage/active/limit produce the expected query |
| PG-T2 | Stat counts | Counts match the filtered set |
| PG-T3 | Runtime overlay | Local converter/merge truth wins over API stage |
| PG-T4 | Manual recovery | Missing file disables Continue; present file enables it |
| PG-T5 | Poll cadence | 12 s / 4 s / 5 s; stopped when hidden |
| PG-T6 | Error retention | Rows remain and stale label appears |
| PG-T7 | Empty | Empty message + clear filters |
| PG-T8 | Download queue | Appears/disappears with pending items; live bytes and states; pause/resume, retry, cancel and reveal are real actions |
| PG-T9 | Live pipeline | Render/merge/reel stages update; retry only the failed stage; upload uses the existing flow; historical values still render |
| PG-T10 | Coordinator unit | Target resolution/containment, URL guard, dedupe, retry/backoff, cancel, pause/resume, write atomicity (fake fetcher/IO) |
| PG-T11 | Downloads E2E | Real files with real bytes, live progress, dedupe of a repeated item, 500 auto-retry, manual retry, cancel without a partial file, traversal rejection, completion sync |

---

## 7. Dependencies

- Music downloads coordinator (shell service): `electron/services/download-coordinator.ts`,
  `download-targets.ts`, `download-io.ts`, `electron/ipc/downloads.ts`; renderer
  `use-download-queue.ts` + `download-queue.tsx`.
- Settings `imageSourceMode` and the device Suno output folder.
- Vizzy automation pipeline — **2.0.0**, see
  [`../09-PIPELINE-AUTOMATION.md`](../09-PIPELINE-AUTOMATION.md).
- Local file access for inspection and open-folder.

---

## 8. Definition of Done

- [ ] PG-01 … PG-49 implemented; all `P0` verified against sandbox.
- [x] PG-39 … PG-43 verified: real MP3 files under the configured root, no partial file after
  cancel/failure/quit, dedupe, retry and live progress (`downloads` E2E + coordinator unit tests).
- [ ] Table renders 200 rows without layout jank.
- [ ] Polling stops when the page is hidden.
- [ ] Manual recovery end-to-end verified with a real run folder.
- [ ] PG-T1 … PG-T11 pass.
- [ ] Render/merge/reel stages are live and retryable; upload uses the existing flow.
- [ ] Visual baseline approved.
