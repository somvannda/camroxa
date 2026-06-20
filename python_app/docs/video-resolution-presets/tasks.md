# Output Resolution Presets (Global + Per-Profile)

## Goals
- Add short/reel (9:16) output support and other common social media aspect ratios.
- Support a global default resolution and an optional per-profile override.
- Ensure end-to-end workflow uses the selected resolution consistently:
  - Image generation (background + thumbnail)
  - Thumbnail composition/overlay
  - Video export (GPU renderer)
  - Merge output

## Tasks
- [pending] Inspect current pipeline resolution usage:
  - Image generation resolution (global)
  - Export resolution (manual export + auto-video)
- [pending] Add preset list shared by Image + Video (16:9 / 9:16 / 1:1 / 4:5 + optional higher res).
- [pending] Global setting:
  - Keep existing `imageResolution` UI but upgrade it to include social presets
  - Add/repurpose a single global “Output resolution” value that drives both Image + Video
- [pending] Per-profile override:
  - Add `Use global (default)` + presets
  - Persist in Postgres (either `profiles.video_resolution` or `profiles.image_config.videoResolution`)
- [pending] Wire resolved resolution into:
  - Image job creation (background + thumbnail size)
  - Thumbnail overlay/composition canvas size
  - Auto-Video exports (per channel/profile)
  - Manual batch export
  - Video preview aspect ratio (recommended)
- [pending] Verify:
  - 16:9 preset matches current output behavior
  - 9:16 preset generates BG/TH at correct dimensions and exports MP4 correctly
  - Progress/Workflow counts remain correct
  - No crash/regression in image workers, export workers, and merge flow
- [pending] Update `DEVELOPMENT_LOG.md` with changes, migration notes, and limitations.
