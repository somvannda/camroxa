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
| Music trigger | `src/features/music/music-pipeline.ts` + `components/automation-card.tsx` | “Render videos” resolves the profile's `video_template_id`/`reel_template_id`, queues one job per ready song/branch, and starts the batch without leaving Music |
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

### 2.5 Music trigger

1. The newest history batch with ready songs is used (`downloaded_ok` or a recorded run
   folder). History stays history — older batches are not mass-rendered.
2. For each channel side (`ok`/`alt`) the profile's `video_template_id` is resolved; a missing
   template skips that job and reports “Choose one in Settings” with a Settings link.
3. The main process resolves the audio file inside the run folder; a missing/ambiguous file
   reports the song by name and leaves the queue empty.
4. `autoMergeAfterVideo` → `merge: true`; `autoReelAfterVideo` → an extra reel job.
5. `autostart` starts the runner immediately; the user stays on Music and follows the rows on
   Progress.
6. **Auto-Upload stays disabled.** No upload is attempted anywhere in this flow.

- **Restart.** The queue and batches are in SQLite. On startup any row caught in
  `rendering`/`encoding`/`merging` is marked `failed` with “The app closed before this render
  finished. Retry it.” and its batch is flagged, so nothing spins forever and retry is explicit.

### 2.6 Progress UI

A compact “Video pipeline” card on `/progress`:

- status badge + stage, template name (kind), song + audio file, progress bar, row error;
- Reveal for a validated output, Cancel for a running row, Retry for failed/cancelled rows;
- per-batch footer: id, batch status, counts, merged file with Reveal, merge error;
- empty state: “No video renders yet. Turn on Auto-Video in Music and use ‘Render videos’.”
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

`tests/e2e/pipeline-batch.mjs` runs the whole flow with **no `/vizzy` route open**
(`vizzy.state().attached === false` throughout) and writes
`artifacts/vizzy/batch-progress.png` and `batch-complete.png`.

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
