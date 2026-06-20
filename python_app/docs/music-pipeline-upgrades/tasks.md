# Music Pipeline Upgrades (Tasks)

## Phase 1 — Batch Integrity (Must-hit requested count)
- [ ] Fix draft retry loop to honor `songDraftMaxAttempts` (currently runs only once).
- [ ] Add pool repick retry (`poolPickMaxAttempts`) and batch-level extra attempt caps.
- [ ] Add DB verification per batchId to ensure `songs_per_batch` rows exist; backfill if short.
- [ ] Keep album name consistent within the same `batchId` (one album per batch).
- [ ] Add clearer progress/status messages during retries (batch id + index + attempt).
- [ ] Verification:
  - [ ] Request 10 songs for 1 day/1 channel pair; confirm History shows 10.
  - [ ] Confirm all 10 songs in a batch show the same album name.
  - [ ] Confirm `autoGSuno` produces 10 Suno tasks and downloads 10 OK + 10 ALT MP3s.

## Phase 2 — Faster MP3→MP4 (Workers + speed mode)
- [ ] Apply export worker concurrency to Auto-Video after Suno (reuse existing Workers setting).
- [ ] Add `videoExportSpeedMode` setting: balanced / fast / very_fast.
- [ ] Pass speed mode into `visualizer.main` (new CLI flag) and map to encoder params (NVENC + x264).
- [ ] Verification:
  - [ ] Export 10 tracks with workers=1 vs workers=3; confirm throughput improves.
  - [ ] Confirm output video plays correctly and audio stays synced.

## Phase 3 — Always Random Merge Order
- [ ] Shuffle merge ordering each merge run (Auto-Video merge).
- [ ] Save merge ordering file into batch folder for traceability.
- [ ] Verification:
  - [ ] Merge same set twice; ordering differs.

## Phase 4 — AI Provider Split + Suno Lyrics
- [ ] Add new settings:
  - [ ] Title/Album provider: DeepSeek / SLAI
  - [ ] Lyrics provider: DeepSeek / SLAI / Suno
- [ ] Refactor generation pipeline into:
  - [ ] Title+Album generation (uses pools as context; always generate unique)
  - [ ] Lyrics generation (provider-specific; add Suno `generate-lyrics` integration)
- [ ] Update song DB persistence so generated lyrics are stored consistently.
- [ ] Verification:
  - [ ] Generate 10 songs with lyricsProvider=suno; confirm lyrics present.
  - [ ] Generate 10 songs with lyricsProvider=deepseek/slai; confirm behavior unchanged except split settings.

## Regression Checklist
- [ ] Music History filters (date range + “Last batch only”) still work.
- [ ] Image auto-gen still triggers on `song` event.
- [ ] Auto-Video still triggers only when prerequisites exist (MP3s + BG + template mapping).
- [ ] YouTube auto-upload still triggers after merge when enabled.
