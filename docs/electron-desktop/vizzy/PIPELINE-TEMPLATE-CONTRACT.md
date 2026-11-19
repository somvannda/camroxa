# Pipeline Template Contract — “Save the preview as a video template”

> **Document ID:** CAMXORA-ED-VZ-PIPE
> **Status:** Required for P7
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

The save dialog pre-fills bindings from the project. Detection is conservative; the user
confirms or overrides.

| Input | Detection order |
|---|---|
| Audio | project audio track → first audio node → none (offer “Add audio track”) |
| Background | node tagged background / `isBackground` → first image or video layer at the back → none |
| Logo | node tagged logo / `isLogo` / `isCoverArt` → media with circle mask → none |
| Title | text node named title/heading/song → first text node → none |
| Artist | text node named artist/author → none |
| Album | text node named album → none |
| Palette | spectrum/image nodes with colour controllers → none |

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
│ Audio       [ audio-track        ▼ ]  required               │
│ Background  [ media-background   ▼ ]  fit [ Cover ▼ ]        │
│ Logo        [ media-logo         ▼ ]  [x] circle mask        │
│ Title       [ text-title         ▼ ]  max [80] overflow ...  │
│ Artist      [ — none —           ▼ ]                         │
│ Album       [ text-album         ▼ ]                         │
│ Palette     [ spectrum-main      ▼ ]  accent                 │
│                                                              │
│ Output: 1920 × 1080 · 30 fps · duration = audio              │
│ [ Cancel ]                              [ Save template ]    │
└──────────────────────────────────────────────────────────────┘
```

- Defaults come from the project resolution; the kind determines long vs reel.
- The save writes atomically (`template.json` + `pipeline.json` + thumbnail).
- Saving an existing template offers Save / Save as new.
- A validation summary lists missing required bindings and incompatible nodes.

### 4.1 Selecting a template per profile

Saved templates are identified by their template id (the directory name under `templates/`).
The existing profile publication fields `video_template_id` and `reel_template_id` store that
id:

- Settings → Publication gets **Video template** and **Reel template** pickers backed by
  `vizzy:templates:list`; they show name, kind and output size, and an empty state that opens
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

---

## 7. All 91 templates

Every one of the 91 templates can be opened, previewed and saved as a video template:

- templates with suitable nodes auto-bind;
- templates without a placeholder still render as previewed with the run audio;
- the user can add bindings later;
- a template that cannot be rendered reports the exact missing feature/asset.

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

---

## 9. Implementation checklist

- [ ] `pipeline.json` schema + Zod validation
- [ ] Save dialog with auto-detection and overrides
- [ ] Atomic write + thumbnail
- [ ] Template library entry with kind and bindings
- [ ] Profile Video/Reel pickers read saved templates
- [ ] Pipeline loader resolves bindings and missing-node errors
- [ ] Preview-parity test
- [ ] 91-template save matrix
- [ ] Old Camxora template rejection
- [ ] Docs and support copy

---

## 10. Non-goals (2.0.0)

- Migrating old Camxora video templates.
- A separate template language.
- Auto-enabling YouTube Auto-Upload (it stays disabled as 1.7.1).
- Rendering templates that require missing licensed assets.
