# Image Generation (Samples) — Design / UX

## Product Intent

Make image generation feel as simple as picking a few sample images + a prompt, then the system reliably generates background + thumbnails for many channel pairs and dates (including long runs).

The UI should stay “file-list simple” (no heavy media database), while still feeling professional and scalable.

## Page Placement

Use the existing primary navigation item `"Image"` (currently a placeholder page in Python).

## Layout (Wireframe)

Target window is currently fixed at 1670×1080, so the design assumes a desktop layout.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Header                                                                       │
├───────────────┬──────────────────────────────────────────────────────────────┤
│ Left Nav      │ Image Workspace                                              │
│ Home          │                                                              │
│ Workflow      │  ┌────────────────────────────────────────────────────────┐  │
│ Music         │  │ CONFIG (in Settings)                                      │  │
│ Image (active)│  │ Configure provider, keys, dirs, auto-run in Settings      │  │
│ Video         │  └────────────────────────────────────────────────────────┘  │
│ Merger        │                                                              │
│ Settings      │                                                              │
│               │                                                              │
│               │  ┌───────────────┬────────────────┬────────────────────────┐  │
│               │  │ BG SAMPLES    │ BG PREVIEW     │ PROMPT + RUN            │  │
│               │  │ (max 5)       │ (16:9)         │                        │  │
│               │  │ [file list]   │ [preview]      │ Preset: [dropdown..]   │  │
│               │  ├───────────────┼────────────────┤ [Manage] [Pick Random]  │  │
│               │  │ THUMB SAMPLES │ THUMB PREVIEW  │ Prompt: [.............]│  │
│               │  │ (max 5)       │ (16:9)         │ Batches (multi-select) │  │
│               │  │ [file list]   │ [preview]      │ [batch list from History]│ │
│               │  │               │                │ [Generate Now] [Stop]  │  │
│               │  │               │                │ [Clear Job Queue]      │  │
│               │  └───────────────┴────────────────┴────────────────────────┘  │
│               │                                                              │
│               │  ┌────────────────────────────────────────────────────────┐  │
│               │  │ JOB QUEUE                                               │  │
│               │  │ Batch separator rows (BatchId + Run Date)               │  │
│               │  │  • Channel | Role (OK/ALT) | BG Dot | TH Dot | BG File | TH File ││
│               │  │  • Actions: Open Folder / Retry                         │  │
│               │  └────────────────────────────────────────────────────────┘  │
├───────────────┴──────────────────────────────────────────────────────────────┤
│ Footer: shows last error / last generated path / progress summary             │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Interaction Design

### Samples

- **List is file-system based**:
  - Background list loads from `imageSamplesDir/background` (default proposal).
  - Thumbnail list loads from `imageSamplesDir/thumbnail`.
- Multi-select up to 5:
  - Selecting item 6 shows a warning and prevents selection.
  - Selected items also appear as removable chips (“• filename [x]”).
- Preview:
  - When a file is highlighted, show a small preview (scaled, keep aspect).

### Prompts

- Prompt input supports:
  - Manual typing (primary)
  - Preset selection
  - “Pick Random” that avoids repeats by using a usage history store.
- Optional “Smart Prompt”:
  - Uses AI to expand the base prompt into a richer art direction prompt.
  - Must be non-blocking and show “Generating prompt…” state.

### Run Controls (Boss update)

- Batch picker:
  - List batches from **Music History** (songs table) and allow multi-select.
  - Manual run generates images for the selected batches only.
- Generate Now:
  - Enqueues jobs into DB and starts processing queue in background.
- Stop:
  - Stops queue consumption (does not corrupt already-downloading tasks).
- Clear Job Queue:
  - Deletes all image jobs from DB (with a confirmation).

### Job Queue

- Shows one row per channel per batch:
  - Batch separator rows (BatchId + Run Date)
  - Per row:
    - Channel + Role (OK or ALT)
    - Background dot + Background file
    - Thumbnail dot + Thumbnail file
- Clicking a row shows full error details in the footer (same UX as Music History).
- Clicking a row also loads the generated Background + Thumbnail previews (when READY).

## States

- Empty samples dir: show “No images found” + browse action.
- No selections: Generate Now disabled (or shows validation).
- Provider missing API key: show blocking warning.
- Long run: status shows “Running… X/Y completed (Z failed)”.

## Accessibility / Usability

- All buttons have tooltips.
- Keyboard navigation for lists (up/down + space to toggle).
- Clear feedback for selection limit (max 5).
