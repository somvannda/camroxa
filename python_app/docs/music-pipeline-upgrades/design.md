# Music Pipeline Upgrades (Design)

## Goals
- Ensure bulk generation produces the requested song count per batch (e.g., 10 rows in History for a 10-song request).
- Make MP3→MP4 conversion faster while keeping output quality acceptable.
- Randomize merge order for each merged output.
- Split AI configuration into:
  - Lyrics generation provider: DeepSeek / SLAI / Suno
  - Title+Album generation provider: DeepSeek / SLAI
- Use pools as inspiration for Title/Album, but always generate unique outputs via the selected Title+Album provider (not direct pool pick).

## UX Changes

### 1) Bulk Generation Reliability
- When generating in bulk, the status line should reflect:
  - Current batch
  - Songs completed out of requested per-batch count
  - Retry attempts (when a song draft generation fails and is being retried)
- When a batch cannot reach the requested count (after limits), show a clear error summary:
  - Which indexes failed
  - Why (pool empty, provider error, timeout, etc.)
  - Recommended action (seed pools, check API keys, retry)

### 2) Faster MP3→MP4
- Keep the existing Video page worker count, but also apply it to Auto-Video after Suno.
- Add a new export speed control in Settings → Video (or Video page) with a small set of options:
  - Balanced (current behavior)
  - Fast (recommended for bulk)
  - Very Fast (lower quality)
- Display effective settings in Export status text (workers + speed mode).

### 3) Random Merge Ordering
- When merging videos in Auto-Video, shuffle the track order before merge.
- Each merge should produce a new random ordering (Boss requested “Always random”).
- Record the merge ordering into the batch folder (text file) so results are reproducible for debugging.

### 4) AI Provider Split
- Settings → AI should be split into two groups:
  - Title/Album Provider (DeepSeek / SLAI)
  - Lyrics Provider (DeepSeek / SLAI / Suno)
- For Lyrics Provider = Suno:
  - show Suno API base URL and key field (reuse existing Suno key if compatible, or add a dedicated key if required by the API).
- For Title/Album:
  - show provider-specific key/model fields and a “Use pools as inspiration” description.

## States / Edge Cases
- Pools empty:
  - Title pool empty should block generation (clear message).
  - Album pool empty should block generation (clear message).
- Lyrics provider failure:
  - If title/album succeeds but lyrics fails, retry lyrics generation first before discarding title/album.
- Export CPU/GPU constraints:
  - If NVENC is not available, fall back to libx264 (already supported).
  - Workers should clamp to a safe max to avoid saturating the machine.
