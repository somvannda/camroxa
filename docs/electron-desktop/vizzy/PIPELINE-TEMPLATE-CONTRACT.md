# Pipeline Template Contract — “Save the preview as a video template”

> **Document ID:** CAMXORA-ED-VZ-PIPE
> **Status:** Save, preview and single-template render implemented (P7); batch, merge, reel and upload remain stubbed
> **Implements:** `09-PIPELINE-AUTOMATION.md` §3–§4
> **Updated:** 2026-11-19

---

## 1. Rule

The pipeline renders **the project the user previewed**, not a re-creation and not a separate
template language.

1. The user opens any of the 91 templates (or a new project).
2. They preview and adjust it.
3. They click **Save as video template**.
4. The save captures the current project exactly as previewed and writes a sibling
   `pipeline.json` with detected bindings.
5. The saved template appears in the profile’s Video/Reel picker.
6. The pipeline loads the same project, binds the run inputs, and renders it at the requested
   resolution.

**No legacy Camxora video templates** are accepted. They are a different schema and are not
migrated in 2.0.0.

### 1.1 Implemented today (2026-11-19)

| Step | Mechanism |
|---|---|
| Save | Vizzy strip → **Save as video template** → `vizzy:template-options` (live `readSnapshot()` + `detectBindings()`) → modal with name/kind only → `vizzy:save-template` (shell-only, zod) → host re-reads the live snapshot, captures `webContents.capturePage()` as `thumbnail.png`, auto-detects every binding (including all palette nodes) and writes `template.json` + `pipeline.json` + `thumbnail.png` **atomically** through `saveVideoTemplate()`. |
| List / manage | **Templates** rail in Vizzy: thumbnail, name, kind, output size, created date. Preview loads the saved `template.json` into the editor with `vizzy:open-project-json` (no re-creation). Delete is confirmed and emits `video-templates:changed`, which refreshes the rail and the Settings query. |
| Library | **Library** in the Templates rail runs the editor's own `editorOpenCreations()`; the staged 91-template pack is served from `CAMXORA_VIZZY_LIBRARY_DIR` → `resolveLibraryRoot()` by the `camxora-vizzy://` handler. |
| Render | Templates rail **Render** → `window.camxora.files.pick` → `vizzy:render-template` → `buildPipelineRenderPlan()` applies the run bindings to the saved project, `openProjectJson()` loads it, `loadAudioTrack()` streams the run file over `camxora-media://` into the editor's own loader, then the existing `exportVideo()` path renders `renders/<template-slug>-<timestamp>.mp4` with progress. |

`vizzy:render-template` fails loudly (never a silent fallback) for a missing template, a
kind/aspect mismatch, a missing or empty audio file, an unreadable audio probe, a missing
background/logo file, a missing bound node, an editor that is not ready, and an encoder
failure.

**Not built (still stubbed):** batch/queue orchestration, long-form merge, the reel variant,
YouTube upload from the pipeline, and the headless/offscreen renderer. One job at a time; the
job needs the attached, ready editor.

---

## 2. Stored shape

```
templates/<template-id>/
  template.json      # the Rea project snapshot (exactly what was previewed)
  pipeline.json      # bindings + requirements
  thumbnail.png
  assets/            # only if the project has local assets
```

### 2.1 `pipeline.json`

```json
{
  "schemaVersion": 1,
  "name": "Night Drive — Long",
  "kind": "long",
  "project": "template.json",
  "output": { "width": 1920, "height": 1080, "fps": 30 },
  "duration": { "mode": "audio" },
  "bindings": {
    "audio": { "nodeId": "audio-track", "required": true },
    "background": { "nodeId": "media-background", "fit": "cover" },
    "logo": { "nodeId": "media-logo", "circleMask": true },
    "title": { "nodeId": "text-title", "maxChars": 80, "overflow": "shrink" },
    "artist": { "nodeId": "text-artist", "maxChars": 60, "overflow": "clip" },
    "album": { "nodeId": "text-album", "maxChars": 60, "overflow": "clip" },
    "palette": { "nodeIds": ["spectrum-main"], "mode": "accent" }
  },
  "requirements": {
    "renderer": "vizzy",
    "minVersion": "2.0.0",
    "features": ["audio-analysis"]
  },
  "createdAt": "2026-11-19T00:00:00Z"
}
```

### 2.2 Binding types

| Binding | Node kind | Behaviour |
|---|---|---|
| `audio` | audio media / project audio | Required. Replaces the project audio; duration and analysis follow the run MP3. |
| `background` | image/video media | Replaces the background media; `cover`/`contain`/`stretch`. |
| `logo` | image media | Replaces the logo media; optional circle mask. |
| `title` | Skia text / animated text | Replaces the text; overflow policy `clip`/`shrink`/`wrap`. |
| `artist` | text | Same. |
| `album` | text | Same. |
| `palette` | spectrum/color nodes | Applies the run palette as an accent. |
| `duration` | project | `audio` (track length) or `fixed`. |

---

## 3. Auto-detection

The host detects bindings automatically when the template is saved. The dialog does not ask the
user to select nodes; it only asks for a name and long/reel kind.

| Input | Detection order |
|---|---|
| Audio | project audio track → first audio node → none (offer “Add audio track”) |
| Background | node tagged background / `isBackground` → first image or video layer at the back → none |
| Logo | node tagged logo / `isLogo` / `isCoverArt` → media with circle mask → none |
| Title | text node named title/heading/song → first text node → none |
| Artist | text node named artist/author → none |
| Album | text node named album → none |
| Palette | nodes with a writable colour property (`props.color` or `props.fillStyle`) → none |

Rules:

- A node can hold only one binding.
- A required binding must point to a compatible node; the save is blocked otherwise.
- Optional bindings are allowed to be empty.
- Duplicate binding or an incompatible node kind blocks the save with a field-level error.
- Missing audio has an explicit **Add audio track** action; no silent fallback.

---

## 4. Save flow UI

```
┌──────────────────────────────────────────────────────────────┐
│ Save as video template                                       │
│ Name: [ Night Drive — Long ]     Kind: [ Long ▼ ]            │
│                                                              │
│ Everything is saved: layers, objects, effects, spectrum,     │
│ particles, analyzers, automations, media and assets.         │
│                                                              │
│ Per song, only the run audio and detected nodes are filled.  │
│                                                              │
│ Output: 1920 × 1080 · 30 fps · duration = audio              │
│ [ Cancel ]                              [ Save template ]    │
└──────────────────────────────────────────────────────────────┘
```

- Defaults come from the project resolution; the kind determines long vs reel.
- The save writes atomically (`template.json` + `pipeline.json` + thumbnail).
- The dialog blocks a name/aspect mismatch (`Long` requires landscape, `Reel` portrait; square
  projects may use either).
- The native editor view is hidden while the modal is open (a `WebContentsView` paints above
  shell DOM) and re-shown for the thumbnail capture and after close.
- Every binding is auto-detected and saved, including every palette node. There is no per-node
  selector; a node that is not detected stays exactly as designed.
- "Save as new" is the default behaviour: each save gets a unique slug id, so an existing
  template is never overwritten.

### 4.1 Selecting a template per profile

Saved templates are identified by their template id (the directory name under `templates/`).
The existing profile publication fields `video_template_id` and `reel_template_id` store that
id:

- Settings → Publication gets **Video template** and **Reel template** pickers backed by
  `video-templates:list`; they show name, kind and output size, and an empty state that opens
  Vizzy.
- Saving a profile keeps the current ids; choosing a template writes the id in the same PUT.
- The pipeline resolves the profile's id to a saved template. A missing id, a deleted template,
  or a kind mismatch is an explicit error (see §6), never a silent fallback.
- Old Camxora template ids (non-Vizzy) are rejected with the 2.0.0 policy.
- `null` means "no saved template"; it must not be treated as an empty string.

---

## 5. Preview parity

The pipeline must match the preview the user saved:

| Factor | Requirement |
|---|---|
| Project | Same `template.json`; no re-generation |
| Renderer | Same Rea renderer and shader paths |
| Analyser | Same settings; analysis at project time |
| Time step | `1/fps`; deterministic |
| Randomness | Seeded per project/time |
| Resolution | Export resolution may differ; composition scales |
| Duration | Project/audio duration, never wall clock |
| Audio | Same processing chain as the preview |

A repeat render of the same inputs must match at the accepted tolerance. Divergence is a bug.

**Verified today:** the save → preview → render round-trip uses the same project JSON
(`tests/e2e/vizzy-templates.mjs` asserts semantic equality between `template.json` and the
project the editor holds after Preview, ignoring Rea's runtime-only counters). The render uses
the saved output size/fps and the run track's ffprobe duration; the E2E re-probes the MP4
(h264/aac, 1920×1080, 60 frames, ~1.97 s for a 2 s WAV, 10.1–11.1 s wall clock). **Not verified yet:** frame-identical
determinism across repeat renders and the 91-template render matrix.

---

## 6. Error and compatibility states

| State | UI |
|---|---|
| No saved template | “Save a video template in Vizzy first.” + Open Vizzy |
| Missing required binding | “This template has no audio binding.” + Edit template |
| Incompatible node | “The title binding points to a non-text node.” |
| Old Camxora template | “Old Camxora video templates are not supported in 2.0.0.” |
| Missing asset | “The template references a missing image/video.” + Open template |
| Pipeline unavailable | “Pipeline integration is not available in this build.” (never a silent no-op) |

Exact IPC error codes returned by `vizzy:render-template` today: `TEMPLATE_NOT_FOUND`,
`TEMPLATE_KIND_MISMATCH`, `AUDIO_FILE_MISSING`, `AUDIO_FILE_EMPTY`, `AUDIO_UNREADABLE`,
`TEMPLATE_ASSET_MISSING`, `TEMPLATE_BINDING_MISSING`, `VIZZY_NOT_READY`, `VIZZY_NOT_ATTACHED`,
`VIZZY_RENDER_FAILED`; `vizzy:save-template` returns `TEMPLATE_INVALID` (with `detail.fields`)
or `TEMPLATE_SAVE_FAILED`. The message is shown verbatim in the rail/dialog. Old Camxora
templates never reach these paths because only Vizzy template directories are listed.

---

## 7. All 91 templates

Every one of the 91 templates can be opened, previewed and saved as a video template:

- templates with suitable nodes auto-bind;
- templates without a placeholder still render as previewed with the run audio;
- the user can add bindings later;
- a template that cannot be rendered reports the exact missing feature/asset.

The staged pack is served by the `camxora-vizzy://` handler from
`resolveLibraryRoot()` (`CAMXORA_VIZZY_LIBRARY_DIR` → packaged resources → app directory).
The Vizzy **Templates → Library** action opens the editor's own Creations browser, which lists
all 91 with real thumbnails; `tests/e2e/vizzy-library.mjs` asserts the manifest, all 91 rows,
a loaded thumbnail and one template load.

---

## 8. Acceptance tests

| ID | Scenario | Assert |
|---|---|---|
| PIPE-T1 | Save as template | `template.json` + `pipeline.json` written atomically; thumbnail exists |
| PIPE-T2 | Reopen | Project is semantically identical |
| PIPE-T3 | Auto-detect | Expected audio/background/logo/text nodes are pre-selected |
| PIPE-T4 | Override | A user-chosen binding is saved and used |
| PIPE-T5 | Missing audio | Save blocked with a specific error |
| PIPE-T6 | Duplicate binding | Save blocked |
| PIPE-T7 | Preview parity | Pipeline output matches the saved preview at tolerance |
| PIPE-T8 | Long/reel | Output dimensions and duration are correct |
| PIPE-T9 | Old Camxora template | Rejected with the 2.0.0 policy |
| PIPE-T10 | 91 templates | Each can be saved; suitable ones render through the pipeline |
| PIPE-T11 | Profile selection | A saved template id round-trips through Settings and the pipeline resolves it |
| PIPE-T12 | Missing/deleted selection | An explicit error is shown; no silent fallback |

Coverage today: `tests/e2e/vizzy-templates.mjs` covers T1–T5 (including the duplicate guard
and a real render), `tests/unit/vizzy-template-model.test.ts` covers detection, option lists,
duplicate/incompatible errors and kind inference, and `tests/e2e/vizzy-library.mjs` covers the
91-template catalogue, thumbnails and one load. T7's frame-level tolerance, T8's reel branch,
T9's old-template rejection UI, T10's 91-save matrix and T11/T12's profile round-trip are still
open.

---

## 9. Implementation checklist

- [x] `pipeline.json` schema + Zod validation
- [x] Save dialog saves the whole snapshot with automatic bindings (no node selection)
- [x] Atomic write + thumbnail
- [x] Template library entry with kind and bindings
- [x] Profile Video/Reel pickers read saved templates (Publication)
- [x] Single-template loader resolves bindings and missing-node errors
- [ ] Preview-parity test (semantic project verified; frame-level tolerance open)
- [ ] 91-template save matrix (catalogue + one load verified)
- [x] Old Camxora template rejection (never listed; policy copy)
- [x] Docs and support copy
- [ ] Batch render, merge, reel, upload (next milestone)

---

## 10. Non-goals (2.0.0)

- Migrating old Camxora video templates.
- A separate template language.
- Auto-enabling YouTube Auto-Upload (it stays disabled as 1.7.1).
- Rendering templates that require missing licensed assets.
