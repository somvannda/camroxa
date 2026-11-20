# Batch Orchestration — Wiring the Queue to Music and Progress

> **Document ID:** CAMXORA-ED-VZ-BATCH
> **Status:** Merged — offscreen render host, queue runner, Progress UI and Music trigger
> **Implements:** `09-PIPELINE-AUTOMATION.md` §2, §6, §7, §11.3–§11.4
> **Updated:** 2026-11-19

---

## 1. What works

| Piece | File | Behaviour |
|---|---|---|
| Offscreen render host | `electron/vizzy-host/render-window.ts` | Hidden `BrowserWindow` (`show:false`, sandboxed, dedicated `vizzy-render` partition, `backgroundThrottling:false`) loads `camxora-vizzy://vizzy/index.html`, waits for `__vizzyTest.ready`, applies a project JSON, streams the run audio over `camxora-media://`, and runs the editor's own exporter |
| Shared export session | `electron/vizzy-host/export-session.ts` | One implementation for the visible editor and the batch renderer: settings, `renders/` file, progress, cancel, 5 s grace, 60 min ceiling, ffprobe, cleanup |
| Orchestrator | `electron/services/pipeline-orchestrator.ts` | template → `buildPipelineRenderPlan` → audio duration → project JSON → export → ffprobe, per-row stage/progress, batch merge, cancel |
| Queue | `electron/services/pipeline-queue.ts` | SQLite `pipeline_jobs`; dedupe, retry, cancel-queued, per-batch listing, `output_path` |
| Batches | `electron/services/database.ts` (migration 3) | `pipeline_batches`: output dir, merge intent, merged output, status/error |
| Runner | `electron/services/pipeline-batch.ts` | Sequential, failure isolation, cancel-aware (`PipelineCancelledError`), per-batch merge hook |
| Merge | `electron/services/pipeline-merge.ts` | `-c copy` first, `-reencode` fallback, ffprobe-validated |
| Audio resolution | `electron/services/pipeline-sources.ts` | Song title → audio file inside the run folder (`1. Title.mp3`, `1. Title_Alt.mp3`); refuses to guess between candidates |
| Music trigger | `src/features/music/views/music-page.tsx` + `music-settings.ts` | The Video (16:9) / Video (9:16) checkboxes persist `autoVideoAfterSuno` / `autoReelAfterVideo`; `Merge Video` persists `autoMergeAfterVideo`. No render starts unless a Video box is checked |
| Auto-video coordinator | `electron/services/auto-video.ts` + `auto-video-coordinator.ts` | Polls `/progress` + `/music/history` every 12 s, picks the next ready branch, resolves the generated 16:9/9:16 background, and enqueues one job per song. Long and reel use separate pipeline batch ids so merges never mix |
| Progress UI | `src/features/progress/video-pipeline-table.tsx` + `use-video-pipeline.ts` | Durable queue table: status, template, song, progress, error, Cancel/Retry/Reveal, merged file per batch, honest empty state |
| IPC | `electron/ipc/pipeline.ts` | `pipeline:list/enqueue/start/cancel/retry/clear/reveal` + `pipeline:changed` |

Measured on this machine (320×180 / 30 fps / 2 s runs, ffprobe-verified):
two songs rendered **4.7–4.9 s** total, merged file 4.01 s / 120 frames, cancel left
`renders/` unchanged, retry produced exactly one new file.

---

## 2. Mechanism

### 2.1 Why an offscreen window

A queued job must render whether or not the user is on `/vizzy`. The visible editor is a
`WebContentsView` that only exists while the route is mounted, so the pipeline gets its own
hidden `BrowserWindow`:

- same bundle (`camxora-vizzy://vizzy/index.html`) and the same sandboxed `vizzy-preload.cjs`;
- **dedicated session partition** (`vizzy-render`), so localStorage / IndexedDB autosave and
  the editor's own state cannot collide with the visible editor;
- `show:false`, `backgroundThrottling:false`, no Node, context isolation, navigation limited
  to the editor origin;
- both custom schemes (`camxora-vizzy://`, `camxora-media://`) are installed on that partition
  as well — Electron keeps protocol handlers per session;
- the window is created on demand and disposed when the queue drains. Disposing deletes no
  user file; the export session deletes only its own partial render.

The render page is a **second legitimate view sender**: `VizzyHost.isViewSender()` accepts
either surface, `vizzy:export:chunk` routes by job id, and `vizzy:bridge` routes by sender.

### 2.2 Render port

```ts
const template = readVideoTemplate(templatesDir, job.templateId);
const durationSec = await probeDuration(job.audioPath);
const plan = buildPipelineRenderPlan(template, {
  audioDurationSec: durationSec,
  inputs: { title, artist, album, backgroundUrl, logoUrl },
  expectedKind: job.branch,
});
await host.renderTemplateOffscreen({
  projectJson: plan.projectJson,
  name: template.name,
  audioPath: job.audioPath,
  settings: plan.settings,
  outputName: job.title || basename(job.audioPath),
  onStarted: (jobId) => registerCancel(() => host.cancelExport(jobId)),
  shouldAbort: () => cancelled,
});
```

- Audio is streamed, never base64: the editor fetches the `camxora-media://` URL itself.
- One render at a time. `renders/<song-slug>-<timestamp>.mp4`, ffprobe-validated before the
  row is marked `done`.
- A cancelled render deletes its partial file; a cancel during window load never starts an
  export.

### 2.3 Queue stages

| Row stage | Source |
|---|---|
| `queued` | enqueue |
| `rendering` | `vizzy:export:progress` while the exporter renders frames (0–85 %) |
| `encoding` | exporter `encoding/muxing/joining` stages (85–99 %) |
| `done` | ffprobe accepted the file (100 %) |
| `failed` | renderer or validation error, stored on the row |
| `cancelled` | user cancel; no output path |

Progress writes are throttled to ≤ 1 per 500 ms per job. `pipeline:changed` is coalesced to
~150 ms; the queue itself is durable, so Progress re-reads it on mount and while it is open.

### 2.4 Cancel, retry, merge

- **Cancel** sets the runner's stop flag, cancels the in-flight export (existing
  `session.cancel`), marks the row `cancelled`, and cancels every queued row. Queued rows
  never start after a cancel.
- **Retry** re-enqueues `failed` and `cancelled` rows only, then starts. Completed rows and
  their files are untouched. `enqueuePipelineJobs` dedupes on
  `(batch, branch, template, audio)`.
- **Merge** runs only for batches enqueued with `merge: true` and ≥ 2 validated long outputs.
  Output: `<run folder>/<batch>-merged.mp4` (never overwrites; `-2` suffix). `-c copy` first,
  re-encode on failure, ffprobe-validated. Rows stay `done`; the merge is batch-level
  (`pipeline_batches.merged_output`) because it has no single song row.
- **Reel** is a separate render of the reel template (`branch: "reel"`), not a crop. If the
  profile has no reel template the Music card says so and does not queue the reel.

### 2.5 Automation

The coordinator runs in the main process while the app is signed in, so a batch finishes
without the user staying on Music or Progress. Every **12 s** it:

1. reads `/settings`; both Video checkboxes off means no render is attempted;
2. reads `/progress` and `/music/history` (profiles and local templates are cached for 15 s);
3. picks the next ready row:
   - run folder exists, expected MP3s downloaded, no pending download;
   - the branch background exists on this machine (`background-16x9.*` / `background-9x16.*`,
     or the API `background_*_path`);
   - the profile has the branch template and the template exists locally;
   - the branch is not already done, running, failed or merged;
4. enqueues **one job per song** with `title`, `album`, channel name as `artist`, and the
   generated `backgroundPath`;
5. starts the queue runner. Long renders first when both branches are checked; reel can render
   on its own when only 9:16 is checked. Merge applies per branch because each branch has its own
   pipeline batch id (`<batch>:long` / `<batch>:reel`).

A failed/cancelled branch is never restarted automatically — Retry in Progress is explicit.
The hidden renderer applies the background and text bindings, loads the run MP3, and the
template's own spectrum/analyzers/effects/automations run exactly as saved. **Auto-Upload stays
disabled.**

- **Restart.** The queue and batches are in SQLite. On startup any row caught in
  `rendering`/`encoding`/`merging` is marked `failed` with “The app closed before this render
  finished. Retry it.” and its batch is flagged, so nothing spins forever and retry is explicit.

### 2.6 Progress UI

A compact “Video pipeline” card on `/progress`:

- status badge + stage, template name (kind), song + audio file, progress bar, row error;
- Reveal for a validated output, Cancel for a running row, Retry for failed/cancelled rows;
- per-batch footer: id, batch status, counts, merged file with Reveal, merge error;
- empty state: “No video renders yet. Turn on Video (16:9) or Video (9:16) in Music and generate a batch.”
- Cancel batch / Retry failed / Clear finished in the header. Every control calls real IPC.

---

## 3. Acceptance evidence

| ID | Scenario | Result |
|---|---|---|
| BATCH-1 | Two songs, one template | PASS — two 320×180 h264/aac MP4s, 60 frames each, rows `done` |
| BATCH-2 | One row fails | PASS (unit) — failed row keeps its error, the next row renders |
| BATCH-3 | Cancel | PASS — row `cancelled`, `renders/` unchanged, no partial file |
| BATCH-4 | Retry | PASS — only the cancelled row ran, one new file |
| BATCH-5 | Merge | PASS — one 4.01 s / 120-frame MP4 in the run folder |
| BATCH-6 | Reel | PASS (unit) — separate reel template job; missing template reported |
| BATCH-7 | Missing template | PASS — explicit per-row/settings message, no render |
| BATCH-8 | Auto-Upload | PASS — toggle disabled, no upload code path |
| BATCH-9 | Preview parity | N/A here — unchanged from the template milestone (`vizzy-templates`) |
| BATCH-10 | Restart | PASS (unit) — the queue and batches live in SQLite; interrupted rows are reconciled to `failed` on startup and become retryable |
| BATCH-11 | Background auto-video | PASS — `auto-video` E2E: no page click; the coordinator reads Progress/History/Settings, enqueues two long jobs with the generated `background-16x9.png`, renders and merges the branch |

`tests/e2e/pipeline-batch.mjs` runs the whole flow with **no `/vizzy` route open**
(`vizzy.state().attached === false` throughout) and writes
`artifacts/vizzy/batch-progress.png` and `batch-complete.png`.

`tests/e2e/auto-video.mjs` starts with `CAMXORA_AUTO_VIDEO=1`, seeds a ready Progress row and a
real background file, and proves the main-process coordinator starts the render without any
Music/Progress action. `artifacts/vizzy/auto-video-progress.png` shows the auto-video status and
the finished long branch.

---

## 4. Non-goals (2.0.0) and remaining limitations

- **Upload / publish**: Auto-Upload stays disabled exactly as 1.7.1. The pipeline stops at a
  validated file; the manual publication flow is the only upload path. A future upload stage
  must retry independently of the render job.
- **Multiple concurrent renders**: one render at a time. A second `pipeline:start` is refused
  while a batch runs; `retry` requires the runner to be idle.
- **Workers**: the queue runs in the main process; there is no worker thread or Redis-like
  queue for desktop. CPU-heavy encoding happens in the editor renderer process.
- **Licensed assets**: templates whose library assets are missing fail with the editor's
  message on the row; there is no per-asset preflight.
- **Reuse of the visible editor**: the pipeline always uses the hidden window. Reusing an
  attached editor was considered but would make correctness depend on `/vizzy` being open.
- **Merge progress**: ffmpeg concat reports no per-percent progress; the batch shows
  `merging` and then `done`.
- **Output location**: renders are managed by the app in `<userData>/renders/`; only the
  merged long-form file is written into the profile's run folder.
