# Batch Orchestration — Wiring the Queue to Music and Progress

> **Document ID:** CAMXORA-ED-VZ-BATCH
> **Status:** Backend groundwork merged; wiring is the next milestone
> **Implements:** `09-PIPELINE-AUTOMATION.md` §2, §6, §7, §11.3–§11.4
> **Updated:** 2026-11-19

---

## 1. What already exists

| Piece | File | Behaviour |
|---|---|---|
| Template contract | `electron/services/pipeline-templates.ts` | `pipeline.json` validation, binding detection, run-input application |
| Render plan | `electron/services/pipeline-run.ts` | Exact project JSON + export settings for one run |
| Template store | `electron/services/video-templates.ts` | Atomic `template.json` + `pipeline.json` + PNG thumbnail |
| Queue | `electron/services/pipeline-queue.ts` | SQLite `pipeline_jobs`: enqueue, dedupe, retry, next queued, clear finished |
| Runner | `electron/services/pipeline-batch.ts` | Sequential render, failure isolation, stop between items, optional merge hook |
| Merge | `electron/services/pipeline-merge.ts` | FFmpeg concat list, copy/re-encode, timeout/cleanup, output naming |
| Export | `electron/vizzy-host/host.ts` | The editor's exporter streams to `renders/` with progress/cancel |
| Renders UI | `src/features/vizzy/**` | Inline playback, reveal, confirmed delete |

The runner takes its renderer as a dependency, so the next milestone only has to supply
`render(job)` — the existing single-template render IPC.

---

## 2. Required wiring

### 2.1 Render port

```ts
const render = async (job: PipelineQueueItem) => {
  const template = readVideoTemplate(templatesDir, job.templateId);
  const plan = buildPipelineRenderPlan({ id: job.templateId, ...template }, {
    audioDurationSec: await probeDuration(job.audioPath),
    inputs: {
      title: job.title,
      artist: job.artist,
      album: job.album,
      backgroundUrl: job.backgroundPath ? createMediaUrl(job.backgroundPath) : undefined,
      logoUrl: job.logoPath ? createMediaUrl(job.logoPath) : undefined,
    },
    expectedKind: job.branch,
  });
  return host.renderPlan(plan, job.audioPath); // the template milestone's render path
};
```

- One render at a time (the editor view is single).
- Load the plan's project JSON into the editor, load the audio bytes, export with
  `plan.settings`, validate with `ffprobe`.
- Map stages to the queue: `rendering` → `encoding` → `done`; errors are user-readable.

### 2.2 Music trigger

The Music automation card already persists `autoVideoAfterMusic`, `autoMergeAfterVideo`,
`autoReelAfterVideo`, and keeps `autoUploadYouTube` disabled. Wire:

1. After a batch's songs and images are ready, resolve the profile's
   `video_template_id` / `reel_template_id`.
2. Build one queue item per song and branch.
3. Call `enqueuePipelineJobs()`; if nothing is new, the toggle is a no-op (dedupe).
4. Run `runPipelineQueue()` with `shouldStop` bound to the cancel action.
5. Merge per §3; publish results to Progress.

Missing/deleted template → explicit error on the job and a link to Settings, never a silent
fallback.

### 2.3 Progress stages

| Stage | Source |
|---|---|
| `queued` | enqueue |
| `rendering` | editor `vizzy:export:progress` |
| `encoding` | late export progress |
| `merging` | `mergeVideos()` start/end |
| `done` / `failed` / `cancelled` | runner |

Progress events must be throttled to ≤ 1 per 500 ms and survive a route change (the queue is
durable; the UI re-reads it).

### 2.4 Cancel and retry

- Cancel sets `shouldStop`; the current render uses the existing export cancel, then its row is
  marked `cancelled`. Queued rows stay `queued` or are cancelled per the user's choice.
- Retry re-enqueues failed rows only. `enqueuePipelineJobs()` already allows that; completed
  outputs are not re-rendered unless the user forces it.

### 2.5 Upload

- **Auto-Upload stays disabled exactly as 1.7.1.** The pipeline stops at a validated file.
- The existing publication/manual flow remains the only upload path.
- A future upload stage must not reuse the render job; it retries independently.

---

## 3. Merge and reel

- Merge long-form outputs only when there is more than one file and the profile asks for it.
- Use `-c copy` when all outputs came from the same template/settings; otherwise re-encode.
- A merged file is valid only after `probe()` confirms duration and streams.
- Reel is a separate render using the reel template (vertical output), not a crop of the long
  file. If the profile has no reel template, report “no reel template selected”.
- Output names follow `outputName(stem, branch)`.

---

## 4. Acceptance

| ID | Scenario | Assert |
|---|---|---|
| BATCH-1 | Two songs, one template | Two validated MP4s; queue rows `done` |
| BATCH-2 | One song fails | That row `failed` with a reason; the other completes |
| BATCH-3 | Cancel mid-render | Partial file removed; current row `cancelled`; rest queued/cancelled |
| BATCH-4 | Retry failed row | Only the failed row runs; completed output kept |
| BATCH-5 | Merge | One valid merged MP4 with the expected duration |
| BATCH-6 | Reel | 1080×1920 output from the reel template |
| BATCH-7 | Missing template | Explicit error + Settings link; no render |
| BATCH-8 | Auto-Upload | Toggle remains disabled; no upload is attempted |
| BATCH-9 | Preview parity | Render uses the saved `template.json` unchanged except bindings |
| BATCH-10 | Restart | Queued rows are found after relaunch and can resume |

---

## 5. Non-goals (2.0.0)

- Multiple concurrent renders (the editor view is single).
- Auto-upload / auto-publish.
- Migrating old Camxora video templates.
- Rendering templates whose licensed assets are missing; report the missing asset.
