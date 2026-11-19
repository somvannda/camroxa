# Pipeline Automation — Vizzy as the 2.0.0 Video Engine

> **Document ID:** CAMXORA-ED-09
> **Version:** 1.0.0
> **Status:** Draft for approval
> **Release:** Camxora Desktop **2.0.0**
> **Feature prefix:** `PL-`
> **Owner:** Pipeline engineering + Product
> **Last updated:** 2026-11-19

---

## 1. Decision

2.0.0 ships **Vizzy as the only video engine**. The old Video page is removed. In its place:

1. the **Vizzy editor** authors and previews compositions;
2. the user previews any of the **91 templates**, adjusts it, and clicks **“Save as video
   template”**; that saved state becomes their pipeline template;
3. a **headless render service** binds a run (song, profile, artwork, text) to the saved
   template and renders the video automatically;
4. **FFmpeg** merges long-form videos and renders reel variants;
5. the **platform API** keeps the existing YouTube publication flow; Auto-Upload remains
   exactly as 1.7.1 (toggle disabled);
6. **Music**, **Progress**, **Settings**, **Marketplace** and **Vizzy** expose the controls.

This is the full replacement of the Video page, not a sidecar and not a second renderer.
**All 91 templates are available to users**; the pipeline works with any of them once saved as
a video template.

**Non-negotiable:** the old Python visualizer is **not** shipped in 2.0.0. **Old Camxora
video templates are not migrated in 2.0.0**; the pipeline uses Vizzy-native pipeline templates
only. See §9.

### 1.1 Implementation status (2026-11-19)

| Area | State |
|---|---|
| Editor host | Merged — real Rea editor in a sandboxed `WebContentsView` |
| 91-template library | Merged — all 91 browsable and previewable in the editor's Creations browser |
| `pipeline.json` + template store | Merged — validated schema, atomic store, thumbnails |
| Binding detection + run application | Merged — conservative auto-detect, explicit overrides, loud missing-node errors |
| Native export | Merged — the editor's own exporter streams chunks to `renders/`; progress/cancel; ffprobe validation |
| Renders panel | Merged — inline playback, reveal, confirmed delete |
| Save as video template | In progress (template milestone) |
| Single-template render | In progress (template milestone) |
| Batch render / merge / reel / upload | Not built |

**Renderer note:** the current implementation renders through the **attached editor's own
exporter** (`runExport`), so preview parity is structural: same project, same renderer, same
analyser settings. §5.1 describes a separate offscreen worker as the scale-out target; 2.0.0
does not need it for correctness, and adding it must keep the same project/analyser path.
Native FFmpeg remains the merge/reel/validation tool.

The wiring details for Music/Progress/merge/reel are in
[`vizzy/BATCH-ORCHESTRATION.md`](vizzy/BATCH-ORCHESTRATION.md).

---

## 2. Pipeline flow

```
Music: Generate
  └─ batches created (one per planned day × channel pair)
       └─ Suno songs downloaded
            └─ Image: background + thumbnail jobs
                 └─ Auto-Video (per song/profile/branch)
                      ├─ resolve pipeline template for the profile
                      ├─ bind audio, logo, background, title/album, palette, duration
                      ├─ render frames on the Vizzy renderer (headless)
                      ├─ encode MP4 with native FFmpeg
                      └─ validate output
                           └─ Auto-Merge (concat long-form outputs)
                                ├─ validate merged MP4
                                └─ Auto-Reel (vertical variant)
                                     └─ Existing publication/manual upload
                                          (Auto-Upload toggle stays disabled)
                                          └─ Progress stages update
```

A failure at any stage stops that branch, preserves the last good output, reports a specific
reason, and can be retried without re-rendering completed work.

---

## 3. Inputs and binding

A pipeline job is built from the same run data the old Video page used:

| Input | Source | Used for |
|---|---|---|
| `run_dir` | run/channel/date folder | locating MP3s and outputs |
| `background_path` | Image stage output for the branch | background media binding |
| `template_id` | profile (`videoTemplateId` / `reelTemplateId`) or explicit selection | pipeline template |
| `branch` | `long` or `reel` | resolution, aspect, output suffix |
| `batch_id`, `role` | run metadata | traceability |
| `output_resolution` | profile/settings (long), fixed 1080×1920 (reel) | render size |
| `fps` | settings (24/30/48/60) | render/encode |
| `mp3_paths` | run folder | per-song render |
| `logo_path` | profile | logo binding |
| `title`, `album`, `artist` | song/batch metadata | text bindings |
| `palette` | template/profile/settings | color bindings |
| `publication` | profile publication settings | YouTube upload |

### 3.1 Template selection

1. The user opens any of the **91 templates** in Vizzy and previews it.
2. They adjust what they want and click **Save as video template**. The save captures the
   current project exactly as previewed and auto-detects bindings (audio, background, logo,
   title/artist/album, palette) with optional overrides.
3. The saved user template appears in the profile’s Video/Reel template picker.
4. Profile `videoTemplateId` for long-form; `reelTemplateId` for reels. If missing, the
   pipeline falls back to the default user template for that kind.
5. If the template is missing or incompatible, the job fails with a specific reason and a
   link to Settings → Profiles → Templates. It does not silently render a different template.

**Preview parity:** the pipeline renders the saved project, not a re-creation. Same project,
same renderer, same analyser settings, same effects. The output resolution may be higher than
the preview, but the composition is identical.

The detailed save dialog, auto-detection rules, error states and acceptance tests are in
[`vizzy/PIPELINE-TEMPLATE-CONTRACT.md`](vizzy/PIPELINE-TEMPLATE-CONTRACT.md). The complete
91-template inventory is in [`vizzy/TEMPLATE-LIBRARY.md`](vizzy/TEMPLATE-LIBRARY.md).

---

## 4. Pipeline template contract

A pipeline template is **a Vizzy project plus a manifest**. The project is the composition
the user previewed. The manifest is generated by **Save as video template** and declares what
the pipeline may replace and what it must not touch. Bindings are auto-detected from the
project (audio track, background media, logo media, title/artist/album text, palette) and can
be confirmed or overridden in the save dialog.

```
templates/<template-id>/
  template.json          # the Vizzy project snapshot (Rea schema)
  pipeline.json          # bindings, requirements, output defaults
  thumbnail.png
  assets/                # optional local assets
```

### 4.1 `pipeline.json`

```json
{
  "schemaVersion": 1,
  "name": "Night Drive — Long",
  "kind": "long",
  "project": "template.json",
  "output": { "width": 1920, "height": 1080, "fps": 30 },
  "duration": { "mode": "audio" },
  "bindings": {
    "audio":       { "nodeId": "audio-track",    "required": true },
    "background":  { "nodeId": "media-background", "required": true, "fit": "cover" },
    "logo":        { "nodeId": "media-logo",     "required": false, "circleMask": true },
    "title":       { "nodeId": "text-title",     "required": true,  "maxChars": 80 },
    "artist":      { "nodeId": "text-artist",    "required": false },
    "album":       { "nodeId": "text-album",     "required": false },
    "palette":     { "nodeIds": ["spectrum-main"], "mode": "accent" }
  },
  "requirements": {
    "renderer": "vizzy",
    "minVersion": "2.0.0",
    "features": ["audio-analysis"]
  }
}
```

### 4.2 Binding rules

| Binding | Type | Behaviour |
|---|---|---|
| `audio` | audio media | Replaces the project audio; duration and analysis follow the track |
| `background` | image/video media | Replaces the background media; fit/cover/contain |
| `logo` | image media | Replaces the logo media; optional circle mask |
| `title` / `artist` / `album` | text | Replaces the text content; overflow policy (clip, shrink, wrap) |
| `palette` | color/spectrum | Applies a palette to the declared nodes |
| `duration` | project | `audio` (track length) or `fixed` |
| `branch` | output | `long`/`reel` resolution and safe area |

### 4.3 Authoring in Vizzy

- The Vizzy inspector gains a **Pipeline** section for supported nodes:
  - "Use as audio / background / logo / title / artist / album".
  - "Bind palette".
  - Overflow policy and max characters for text.
- The editor validates the template:
  - required bindings exist and point to the right node kind;
  - no duplicate binding;
  - output resolution/aspect is valid for the kind;
  - no external network assets;
  - fonts and media are bundled or resolvable.
- "Save as pipeline template" writes `pipeline.json` + `template.json` into the template store.

---

## 5. Headless render service

### 5.1 Runtime

- An **offscreen Electron render host** (`BrowserWindow` with `show: false` or
  `WebContentsView`) loads the Vizzy bundle and the project.

> **Current 2.0.0 implementation:** the attached editor renders and encodes in its own
> `runExport` path and streams chunks to the main process. This is the same renderer and
> analyser as the preview. The offscreen host below remains the throughput target for batch
> rendering, not a correctness requirement.
- WebGL2/Three.js is the renderer; `gl.readPixels` (or `capturePage`) returns RGBA frames.
- Audio analysis uses the existing Vizzy analyser (WASM/JS fallback) with **project time**,
  not wall clock.
- Frames are sent to the main process as `ArrayBuffer` (never base64) and written to a raw
  stream or temp frame files.

### 5.2 Determinism

A frame must be a function of `(project, time, bound inputs)`, not the machine:

- fixed time step (`1/fps`);
- analysis window centred on project time;
- seeded randomness per project/time;
- no dependence on `Date.now()`, wall-clock deltas or the previous playback state;
- prewarm the analyser for the same lead-in on every run;
- disable "bounce" and editor-only overlays;
- render at export resolution, not preview resolution.

A repeat render of the same project/inputs must produce a frame-identical result at the
accepted tolerance; a mismatch is a bug.

### 5.3 Throughput

| Target | Budget |
|---|---|
| 1080p, 30 fps, one worker | ≥ 12 fps render (2.5× realtime slow-down acceptable for batch) |
| 1080p, 30 fps, two workers | ≥ 20 fps aggregate on a mid-range GPU |
| 720p preview-quality pipeline | ≥ 30 fps |
| Reel 1080×1920 | ≥ 12 fps |
| Frame readback + encode | ≤ 25 % of total time |
| Memory per worker | ≤ 700 MB |

If the budget is not met, the pipeline falls back to a lower worker count and reports the
estimated time before starting. It does not silently render at a lower resolution.

### 5.4 Encoding

- Native FFmpeg (ADR-004), H.264/AAC MP4 by default.
- Fallback ladder: MPEG-4/AAC MP4 → VP9/Opus WebM → VP8/Vorbis WebM.
- Validate output with `ffprobe` (duration, streams, dimensions) before success.
- Partial outputs are deleted on failure/cancel.
- Output names: `{song-stem}.mp4` for long, `{song-stem}_REEL.mp4` for reel.

---

## 6. Batch orchestration

### 6.1 Job model

```ts
PipelineJob {
  id: string
  batchId: string
  role: "ok" | "alt"
  branch: "long" | "reel"
  runDir: string
  templateId: string
  backgroundPath: string
  logoPath: string
  audioPaths: string[]
  outputDir: string
  status: "queued" | "rendering" | "encoding" | "merging" | "uploading" | "done" | "failed" | "cancelled"
  progress: number
  attempts: number
  error?: { code, message, detail, retryable }
}
```

### 6.2 Rules

- One active render per worker; default workers 1, max 2 for 1080p (configurable).
- Deduplicate by `(batchId, role, branch, audioPath, templateId)`.
- Resume: a completed valid output is not re-rendered unless `force` is set.
- Cancel: stops the render, kills FFmpeg, removes partial output.
- Retry: retries the failed stage only; a failed upload does not re-render.
- Billing: preflight → consume on start → refund on failure per the existing contract.
- Failure isolation: one song fails, the rest of the batch continues; the batch is marked
  partial, not failed.
- Status events feed Progress and the shell footer.

### 6.3 Merge and reel

- Long-form merge concatenates the validated per-song MP4s in run order.
- Reel renders a vertical variant (1080×1920) with the same bindings and a reel-safe layout.
- Merge uses `concat` with `-c copy` when stream parameters match; otherwise re-encodes with
  the fallback ladder.
- A merged output is valid only when `ffprobe` confirms duration and streams.
- Merge is skipped when there is one output and the branch does not require it.

### 6.4 YouTube upload

- Uses the platform API publish endpoint, never a direct Google call from the renderer.
- Publication fields come from the profile's Publication settings: visibility, schedule,
  audience, AI disclosure, category, playlist, title/description templates, tags.
- Upload is a separate stage: a failed upload leaves the local file intact and can be retried.
- Credits: the existing per-upload cost is preflighted and shown before the batch starts.
- Quota/consent errors are surfaced with a link to Settings → Publication / YouTube.
- **Auto-Upload keeps the 1.7.1 behavior exactly:** the toggle stays disabled. The pipeline
  produces the validated file; the user uploads through the existing publication/manual flow.
  No new auto-publish behavior is introduced in 2.0.0.

---

## 7. UI surfaces

| Surface | What the user sees |
|---|---|
| **Vizzy** | Editor + **all 91 templates** + **Save as video template** + **Renders** panel: job queue, progress, cancel/retry, open output |
| **Vizzy template library** | Create/duplicate/rename/delete/import/export templates, set a default, protect/lock, thumbnail/version |
| **Vizzy inspector** | Pipeline binding section for audio/background/logo/text/palette, prefilled by auto-detection |
| **Music** | Auto-Video / Auto-Merge / Auto-Reel toggles enabled with cost impact; Auto-Upload unchanged (disabled) |
| **Progress** | Live Converter / Merge stages, row detail, retry only the failed stage; upload remains the existing flow |
| **Settings → Profiles** | Video/Reel template pickers point at saved user video templates |
| **Settings → Publication** | YouTube defaults unchanged from 1.7.1 |
| **Marketplace** | All 91 templates available; template kind/compatibility labels |

There is **no separate Video page**. Its template management and export queue live in Vizzy;
its per-run automation lives in Music/Progress.

---

## 8. Cost and billing

- Video render, merge and upload use the existing operation costs from `/credits/operation-costs`.
- The Music automation card shows the full preflight: render + merge + upload.
- The pipeline consumes credit only after a valid output exists; failure refunds per the
  existing contract.
- A retry does not double-charge when the previous attempt failed before output validation.
- The estimate is visible before Generate; a batch over the user's balance is blocked.

---

## 9. Template source and Vizzy content parity

**Decision:** old 1.7.1 Camxora video templates are **not migrated** in 2.0.0. The pipeline
accepts **Vizzy-native pipeline templates only**.

- Old Camxora templates are not selectable in Settings or the Renders panel.
- They are not converted, re-authored or rendered by a sidecar in 2.0.0.
- A user who needs an old template stays on 1.7.x or re-authors it in Vizzy later.
- The UI states the policy; it does not show a broken/empty picker.

**Why:** the old schema is a parameter file for the Python visualizer, not a Vizzy project.
Converting it would add 4–8 weeks, a compatibility layer and approximate output. The 2.0.0
goal is one renderer and one native template format. Keeping the old templates is a product
decision for a later release, not a 2.0.0 dependency.

**Consequences:** no converter, no sidecar, 4–8 weeks saved. The break is explicit and
documented in the release notes and Settings.

### 9.1 Vizzy content parity (release gate)

Everything already in Vizzy must work as-is. This is a first-class acceptance surface, not a
cleanup item.

| Content | Count | Required |
|---|---|---|
| Built-in spectrum presets | 5 | Apply, render, save, reload |
| Spectrum catalogue presets | 32 | Load, apply, render, thumbnails |
| Particle presets | 18 | Apply, movement/reaction distinct, Default restores |
| Butterchurn presets | 6 | Load, render |
| Community presets | empty array | Loads safely; no error |
| User presets | user-defined | Create/save/update/delete/import/export |
| Templates modal/panel | shipped set | List, apply, import/export |
| Preset thumbnails/images | shipped set | Resolve; no broken images |
| Node kinds/effects used by presets | all | Render without console errors |

The parity suite enumerates each item, applies it, saves/reloads the project and captures a
screenshot. A preset that cannot render fails the release gate.

### 9.2 The 91-template library

The library is **90 reference project exports + the Moai Money creation = 91**. All 91 are
available to users; they are both the template library and the fidelity corpus.

| Fact | Value |
|---|---|
| Project JSON | 90 files, 14.2 MB |
| Ported media/assets | 560 files, 265.6 MB (89 template folders) |
| Import coverage | 1,289 effects, 890 of 891 automations |
| Provenance | Vizzy editor exports: 10 curated + 80 staff picks (2026-10-27) |
| Audio | Licensed tracks are **not** copied; the manifest names them |
| Parity | ~42.5 % exact, ~77 % within the review band at the last Rea baseline |

**Decision: all 91 are part of the product library.**

1. **Port and ship all 91.** Every template must open, preview, save, reopen, export, and be
   saveable as a user video template. This is a release gate; users can enjoy all of them.
2. **Delivery:** the 91 are 14.2 MB of JSON + 265.6 MB of media. Recommended delivery is a
   first-run **“Vizzy Templates”** pack so the base installer stays lean; bundling everything
   in the installer is acceptable if product accepts the size. The app presents all 91 as
   available either way.
3. **Licensing/asset clearance** is a release dependency. Engineering ports all 91; legal must
   record clearance for public distribution. Licensed audio is not copied — the manifest names
   the track; the user supplies their own audio anyway.
4. **Pipeline use:** any of the 91 can be opened, previewed and saved as a video template.
   The save flow auto-detects audio/background/logo/text/palette bindings. If a template has
   no suitable placeholder, it renders as previewed with the run audio; the user can add
   bindings later.
5. **No curated subset.** All 91 are available. A “featured” row may help discovery, but it
   does not remove anything.

If product confirms a redistribution licence for all 91, we can ship them as an optional
lazy-downloaded pack; they still do not all become pipeline templates.

---

## 10. Observability and recovery

- Every job has a `jobId`, `batchId`, `templateId`, `audioPath`, `outputPath` and stage.
- Progress updates at least every 500 ms.
- The log records stage transitions, FFmpeg argv, render worker count, fps and validation.
- A stale job is detected after 2× the estimated render time and marked `stalled`; Retry is
  offered without deleting the last good output.
- On app quit, running jobs are cancelled with a persisted marker; the next launch offers
  Resume.
- Diagnostics include the pipeline version, template hash, worker count and last error.

---

## 11. Feature checklist

### 11.1 Template + binding

- [ ] **PL-01** `pipeline.json` schema + Zod validation
- [ ] **PL-02** Template store with `template.json` + `pipeline.json` + assets
- [ ] **PL-03** Vizzy inspector "Pipeline" section
- [ ] **PL-04** Bind audio
- [ ] **PL-05** Bind background
- [ ] **PL-06** Bind logo
- [ ] **PL-07** Bind title/artist/album with overflow policy
- [ ] **PL-08** Bind palette
- [ ] **PL-09** Duration = audio/fixed
- [ ] **PL-10** Template validation + **“Save as video template”** from the current preview
- [ ] **PL-11** Template detail shows compatibility and missing features

### 11.2 Render

- [ ] **PL-12** Offscreen render host with WebGL2
- [ ] **PL-13** Deterministic time/audio analysis
- [ ] **PL-14** Frame readback + ArrayBuffer transport
- [ ] **PL-15** Long-form 1080p render
- [ ] **PL-16** Reel 1080×1920 render
- [ ] **PL-17** Output validation with `ffprobe`
- [ ] **PL-18** Repeat render determinism test
- [ ] **PL-19** Worker count/throughput controls

### 11.3 Orchestration

- [ ] **PL-20** Job model + SQLite persistence
- [ ] **PL-21** Queue, concurrency, single-flight
- [ ] **PL-22** Progress events to shell/Progress
- [ ] **PL-23** Cancel
- [ ] **PL-24** Retry failed stage only
- [ ] **PL-25** Resume after restart
- [ ] **PL-26** Dedupe and skip valid outputs
- [ ] **PL-27** Partial batch handling
- [ ] **PL-28** Stalled job detection

### 11.4 Merge, reel, upload

- [ ] **PL-29** Merge long-form with FFmpeg
- [ ] **PL-30** Reel variant
- [ ] **PL-31** Stream validation and fallback ladder
- [ ] **PL-32** Existing YouTube publication/manual upload flow (no new auto-publish)
- [ ] **PL-33** Publication fields, schedule, playlist, AI disclosure unchanged
- [ ] **PL-34** Upload retry without re-render
- [ ] **PL-35** Auto-Upload toggle remains disabled exactly as 1.7.1

### 11.5 Surfaces

- [ ] **PL-36** Music Auto-Video/Auto-Merge/Auto-Reel enabled with cost impact; Auto-Upload disabled
- [ ] **PL-37** Progress live stages + retry
- [ ] **PL-38** Settings Video/Reel template pickers
- [ ] **PL-39** Marketplace template kind/compatibility
- [ ] **PL-40** Vizzy Renders panel

### 11.6 Vizzy content parity

- [ ] **PL-41** 5 built-in spectrum presets apply/save/reload
- [ ] **PL-42** 32 spectrum catalogue presets load/apply/render/thumbnail
- [ ] **PL-43** 18 particle presets apply; Default restores; movement/reaction distinct
- [ ] **PL-44** 6 Butterchurn presets + community presets (empty) load
- [ ] **PL-45** User presets and templates modal/panel CRUD/import/export
- [ ] **PL-46** Template library: create/duplicate/rename/delete/import/export/default/protect/thumbnail
- [ ] **PL-47** All 91 templates available to users (open/preview/save/reopen/export)
- [ ] **PL-48** “Save as video template” captures the current preview exactly
- [ ] **PL-49** Auto-detect and confirm bindings for any of the 91
- [ ] **PL-50** 91-template delivery pack + licensing/asset clearance record

---

## 12. Acceptance

| ID | Scenario | Assert |
|---|---|---|
| PL-T1 | Long render | A run produces a valid 1080p MP4 with audio |
| PL-T2 | Reel render | A vertical 1080×1920 MP4 with the same bindings |
| PL-T3 | Merge | Multiple songs merge into one valid MP4 |
| PL-T4 | Upload | A file uploads with the configured publication fields |
| PL-T5 | Determinism | Two renders of the same inputs match at tolerance |
| PL-T6 | Retry | A failed upload retries without re-rendering |
| PL-T7 | Resume | Restart resumes a queued job |
| PL-T8 | Partial batch | One failure does not cancel the rest |
| PL-T9 | Vizzy content parity | Every enumerated preset/catalogue/template applies, renders, saves and reloads |
| PL-T10 | No dead controls | Every toggle/stage has a real effect; old Camxora templates are not offered |
| PL-T11 | 91-template library | Every template opens, previews, saves, reopens, exports and can be saved as a video template |
| PL-T12 | Preview parity | The pipeline output matches the preview the user saved (same project, same renderer) |

---

## 13. Open decisions

| # | Question | Needed by | Owner |
|---|---|---|---|
| PL-Q1 | Do we bundle the 91-template pack in the installer or deliver it as a first-run pack? | P7 start | Product |
| PL-Q2 | ~~Auto-Upload default~~ — resolved: keep 1.7.1 behavior (toggle disabled) | — | — |
| PL-Q3 | Are 48/60 fps required for pipeline export, or is 30 acceptable? | P7 | Product |
| PL-Q4 | Do we need multi-GPU/worker > 2 in 2.0.0? | P7 | Engineering |
| PL-Q5 | Is the reel template the same project with a vertical binding, or a separate template? | P7 | Design |
| PL-Q6 | Do we ship a "Renders" panel inside Vizzy, or a route? | P7 | Design |

---

## 14. Definition of Done

- [ ] PL-01 … PL-50 implemented; all `P0` verified.
- [ ] Auto-Video/Merge/Reel/Upload work end-to-end from Music Generate.
- [ ] The old Video page is gone; no dead links, settings or toggles.
- [ ] Every Vizzy preset/catalogue/template works as-is (content parity gate).
- [ ] All 91 templates are available, pass the library matrix, and can be saved as video templates.
- [ ] The pipeline output matches the saved preview.
- [ ] The 91-template delivery pack and licensing record are complete.
- [ ] Auto-Upload remains disabled exactly as 1.7.1.
- [ ] Old Camxora video templates are not selectable and the policy is published.
- [ ] Deterministic render and resume/retry verified.
- [ ] Throughput budget met or an approved fallback exists.
- [ ] Release notes describe the clean break and the Vizzy template requirement.
