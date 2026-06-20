## Profile-Scoped Image Configuration - Design

### Product Goal
Make each Profile behave like an independent “channel/brand pipeline”, so background/thumbnail generation does not depend on global settings and can be reused safely across users.

### Why (Boss intent)
- Profiles already store per-channel decisions (logo, video template, YouTube visibility, tags, etc.).
- Image generation inputs are currently mostly global (`settings.imagePrompt`, sample selection), which makes profiles tightly coupled and harder to operate independently.

### User Concepts
- **User Account (future)**: who is signed in.
- **Profile (now)**: a reusable pipeline preset for a brand/channel.
- **Batch/Jobs (now)**: per-batch work items keyed by `batchId + profileId + kind`.

---

## UX Proposal

### A) Where to Configure
Add an **Image** section under **Settings → Profiles** (same place where logo/template/YouTube profile settings live today).

Code anchors (current Profiles UI load/save):
- Load UI: [MainWindow._load_music_settings_profile_details](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L4429-L4620)
- Save UI: [MainWindow._save_music_settings_profile](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L4814-L4925)

### B) Profile Image Mode (the checkbox you asked for)
Expose as a single profile option (radio/combobox, not multiple toggles):
- **Mode: Background + Thumbnail (2 images)** (default)
- **Mode: Thumbnail Only (reuse thumbnail as background)** (1 image)

### C) Profile Prompts
Provide per-profile prompt fields:
- **Base Prompt** (optional shared prefix)
- **Background Prompt** (optional, overrides base)
- **Thumbnail Prompt** (optional, overrides base)

Behavior:
- If the specific field is empty, fall back to Base Prompt.
- If Base Prompt is also empty, fall back to the current preset logic (existing behavior).

Code anchor (current prompt selection):
- [ImageController._enqueue_batch_channel_jobs](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/controllers/image_controller.py#L189-L318)

### D) Profile Sample Strategy
Per-profile background and thumbnail sample controls:
- **Background Samples Directory** (optional)
- **Thumbnail Samples Directory** (optional)
- **Background Sample Mode**: Inherit / Random / Use selected list
- **Thumbnail Sample Mode**: Inherit / Random / Use selected list
- **Selected Background Samples** (multi-select list)
- **Selected Thumbnail Samples** (multi-select list)

Rationale:
- Different brands/channels usually have different typography styles and background mood references.

### E) Edge States
- If DB is not configured: disable saving profile image settings (consistent with current profile behavior).
- If Mode is “Thumbnail Only”: background UI controls may hide/disable, but the existing output consumers still receive a background path (reused thumbnail path).
- If directories are missing: show a warning in status label; do not crash.

---

## Acceptance Criteria
- Changing a profile’s image settings affects only that profile’s jobs.
- Two profiles can run in parallel without overwriting each other’s prompt/sample choices.
- Existing global Image settings can remain as defaults for profiles that don’t configure overrides.
