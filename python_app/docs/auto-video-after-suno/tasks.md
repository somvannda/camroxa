## Auto-Video After Auto-Suno — Tasks

### Goal
- When Auto-Suno + Auto-Gen Image + Auto-Video are enabled, the app should run end-to-end:
  - wait for MP3 downloads and background image
  - export MP3 → MP4 per channel folder using that channel’s `videoTemplateId`
  - merge MP4s in the same folder

### Tasks
- [ ] Add setting: `autoVideoAfterSuno` (default OFF).
- [ ] Add Music page toggle: “Auto-Video (after Suno)”.
- [ ] Track recent batches from generated songs for auto processing.
- [ ] Add a 30s scheduler that checks readiness and triggers export+merge.
- [ ] Readiness rules per (batchId, profileId, role):
  - [ ] output folder exists (okDir/altDir)
  - [ ] at least 1 `.mp3` exists in folder
  - [ ] background image is READY for that profile/batch
  - [ ] profile has `videoTemplateId` and template exists
  - [ ] ffmpeg path is configured
- [ ] Implement headless export for a folder using `ExportJob` (no Video page UI required).
- [ ] Implement headless merge into same folder.
- [ ] UI updates:
  - [ ] log status lines into footer / terminal log
  - [ ] prevent overlapping runs (skip if export/merge already running)
- [ ] Verification: py_compile for touched modules.
- [ ] Documentation: update DEVELOPMENT_LOG.md.

### Acceptance Checklist
- [ ] OK and ALT folders export separately and never mix.
- [ ] Export uses background_*.png from that folder.
- [ ] Export uses template resolved from profile.videoTemplateId.
- [ ] Merge output saved into the same folder as the exported MP4s.
