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
the existing 1.7.1 publication/manual flow: a completed merged row has an explicit
**Upload to YouTube** action, and Auto-Upload stays disabled. Progress consumes
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
| Channel + quota | `GET /youtube/connections`, `GET /youtube/quota`, `GET /youtube/profiles/{id}/playlists` | Upload readiness, channel name, playlist list |
| Manual upload | `POST /youtube/profiles/{id}/access-token`, `POST /publish/jobs`, YouTube resumable `videos.insert`, `POST /youtube/uploads/report`, `POST /publish/jobs/{uid}/complete`, `/retry`, `/cancel` | The explicit Upload to YouTube action |

The upload runs in the **main process** (`electron/services/youtube-upload.ts`). The renderer
only sends the row (`batch`, `profile`, `role`, run folder) and receives byte progress, phases
and readable reasons; the access token never crosses IPC.

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
[ Row detail: fields · timeline · paths · manual recovery · YouTube upload ]
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

### 4.8 Manual YouTube upload

Ported from 1.7.1 `PublishUploadWorker` + `YouTubeDirectUploadWorker` and
`shared/lib/youtube_direct.py`. It is **never automatic**: nothing is requested or sent until
the user confirms the dialog.

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| PG-51 | Upload action | A completed merged row shows **Upload to YouTube** in the row's YouTube cell and in the row detail; disabled states name the exact reason | P0 |
| PG-52 | Confirmation | Before anything is sent, the dialog shows the connected channel, rendered title, visibility/schedule, file, playlist and AI disclosure | P0 |
| PG-53 | Publication settings | Title/description templates, tags (sanitised), category, visibility, `publish_at`, made-for-kids, AI disclosure and playlist come from the profile `youtube_config` | P0 |
| PG-54 | Publish job | `POST /publish/jobs` is created first; a server-side `existing` job is reused, never duplicated | P0 |
| PG-55 | Resumable transfer | Direct upload via the resumable protocol: `Content-Length`, 256 KiB-aligned chunks, `Content-Range`, 308 `Range` resume, retry with backoff; byte progress in the panel | P0 |
| PG-56 | Playlist | Profile playlist by default; **With playlist…** can pick another playlist or none (only playlists the channel really has) | P0 |
| PG-57 | Completion | `POST /youtube/uploads/report` then `POST /publish/jobs/{uid}/complete`; the panel links to the video and the YouTube cell can show the URL from the API | P0 |
| PG-58 | Cancel | Cancel aborts the request, keeps the local file byte-identical and releases the reserved publish job; the row returns to its previous state | P0 |
| PG-59 | Failure + retry | A readable reason (quota, token, metadata, network); the local file is kept; **Retry upload** reuses the failed publish job via `/publish/jobs/{uid}/retry` | P0 |
| PG-60 | Disable reasons | No merged file, no connected channel, missing token, quota/plan error, legacy Camxora template, already uploaded, or another upload running | P0 |
| PG-61 | Auto-Upload | Stays disabled exactly as 1.7.1; the Music toggle remains disabled and unchecked and E2E pins both the control and the absence of automatic requests | P0 |
| PG-62 | Secrets | The access token, refresh token, channel email and cookies never reach the DOM, logs or diagnostics | P0 |

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
| PG-T12 | Manual upload (E2E) | Completed merged row → confirm → publish job → 3 chunked PUTs resuming at the 308 offset → report → complete → video link; nothing sent before the click |
| PG-T13 | Cancel (E2E) | Cancel aborts mid-transfer, keeps the local file byte-identical, releases the publish job, never completes it |
| PG-T14 | Failure + retry (E2E) | Provider 403 quota surfaces a readable reason, keeps the file, reports the failure, then `/retry` reuses the job and completes on a fresh session |
| PG-T15 | Auto-Upload pin | The Music Auto-Upload toggle stays disabled and unchecked; no token/job/session request happens without a click |
| PG-T16 | Secrets | The access token and account email are absent from the page body and the JSONL logs |

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

- [ ] PG-01 … PG-62 implemented; all `P0` verified against sandbox.
- [x] PG-39 … PG-43 verified: real MP3 files under the configured root, no partial file after
  cancel/failure/quit, dedupe, retry and live progress (`downloads` E2E + coordinator unit tests).
- [ ] Table renders 200 rows without layout jank.
- [ ] Polling stops when the page is hidden.
- [ ] Manual recovery end-to-end verified with a real run folder.
- [ ] PG-T1 … PG-T16 pass.
- [ ] Render/merge/reel stages are live and retryable; the manual upload is explicit and Auto-Upload stays off.
- [ ] Visual baseline approved.

### 8.1 Manual upload — current evidence (2026-11-19)

- `node tests/e2e/youtube-upload.mjs` **PASS**: fixture API + local fake Google endpoint; a
  1 MiB merged file uploaded in 3 × 256 KiB chunks resuming at byte 262 144, one publish job,
  one report, one completion and a `youtube.com/watch?v=…` link.
- Cancel left the local file byte-identical and sent no completion; the publish job was
  cancelled server-side.
- A provider 403 quota refusal surfaced a readable reason, kept the file, reported the failure,
  and **Retry upload** reused the job via `/publish/jobs/{uid}/retry` and completed.
- The Music Auto-Upload toggle is disabled and unchecked; the panel states Auto-Upload stays
  off; the token and account email appear in neither the page body nor the logs.
- Real Google credentials and live quota were **not** exercised in CI — see the remaining risk
  in [`../08-RELEASE-2.0.0.md`](../08-RELEASE-2.0.0.md).
