## Auto-Video After Auto-Suno — Design

### Toggle Placement
- Music page inline toggles row:
  - Auto-Gen Image
  - Auto-GSuno
  - Auto-Video (after Suno)

### Behavior
- Auto-Video does not start immediately when turned on.
- It starts when a batch becomes “ready” per channel (OK/ALT) and runs in background.
- It must not block the UI.

### UX Expectations
- Status updates should be visible in footer:
  - “Auto-Video: waiting for MP3s…”
  - “Auto-Video: waiting for background…”
  - “Auto-Video: exporting 3/10…”
  - “Auto-Video: merging…”
  - “Auto-Video: done”

### Safeguards
- If template is missing for a profile, show a clear status and skip that channel.
- If background is missing, keep waiting (do not fail permanently).
- If SLAI jobs fail transiently, retry runs should continue to allow end-to-end success.
