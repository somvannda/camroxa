# musicapi: artifact-aware actions in the dashboard usage logs

## Summary

The user dashboard logs (`/dashboard/logs`) assumed every row was a music clip:
it read only `clips`/`items`/`data` arrays, required a clip `id`, and offered
exactly two actions — MP3 and WAV — plus an audio player. Any result that wasn't
an audio clip (recovery tracks, MP4 renders, MIDI transcriptions, lyric/subtitle
text, voice personas) fell through to a disabled `no clip` row even when the job
succeeded. This makes the download/listen actions **artifact-type aware** so each
result exposes the export and preview its data actually supports.

## Product impact

- **Recovery audio** (`recovery_audio`) shows playable MP3/WAV again: its
  `tracks[]` entries are now read like clips.
- **MP4 / music video** (`mp4_generate`, `mp4_detail`, `video_detail`) gets an
  `MP4` download and an inline `<video>` player.
- **MIDI** (`midi_generate`) exposes a downloadable Standard MIDI File (`.mid`)
  synthesized from the transcribed instruments, plus a per-instrument note count.
- **Lyrics / subtitles** (`timestamped_lyrics_detail`, `lyrics_detail`,
  `subtitle_detail`) exposes LRC / SRT / TXT downloads and a copyable text view.
- **Voice persona** (`voice_generate`) no longer claims to be a clip: it shows
  the persona fields and states plainly that there is no downloadable audio.
- Failed rows still open the raw response; successful rows no longer render a
  misleading `no clip`.

## Technical impact

- `musicapi/web-user/lib/artifacts.ts` (new)
  - `classifyResult(resultJson, endpoint)` → typed `Artifact`
    (`audio` | `video` | `midi` | `text` | `persona` | `image` | `raw`).
  - `extractClipList` now reads `tracks` in addition to `clips`/`items`/`data`.
  - `buildMidiFile(instruments)` — dependency-free SMF Format-1 encoder
    (120 BPM / 480 PPQ, note on/off per instrument, track names).
  - `lrcToSrt(lrc)` and `alignedLinesToSrt` for subtitle export.
  - `downloadBytes` for client-side blob downloads (MIDI/SRT/LRC/TXT).
- `musicapi/web-user/app/dashboard/logs/page.tsx`
  - Result row renders an `ArtifactActions` cell; the `Result` button opens the
    row and the modal switches on the artifact kind.
  - New `MiniButton` tones; `DownloadButton` widened to `mp3 | wav | mp4`.
- `musicapi/web-user/components/playground.tsx`
  - `downloadClip` accepts `format: "mp3" | "wav" | "mp4"`.
- `musicapi/src/server.ts`
  - `GET /me/download?format=mp4` serves the stored B2 render
    (`videos/<clipId>.mp4`) as an attachment. Free to re-fetch — the
    `mp4_generate` job already charged — so it bypasses the audio
    download-purchase ledger.

No schema change.

## Files touched

- `musicapi/web-user/lib/artifacts.ts` (new)
- `musicapi/web-user/app/dashboard/logs/page.tsx`
- `musicapi/web-user/components/playground.tsx`
- `musicapi/src/server.ts`
- `docs/changelog/2026-10-04-musicapi-logs-artifact-actions.md` (this file)

## Migration / deploy

- No migration. Deploy via the normal sandbox-first chain.
- MIDI/SRT/LRC/TXT exports are generated in the browser; only MP4 needs the
  backend route, and it reuses existing B2 objects.

## Tests

- `npm run typecheck` (musicapi) → clean.
- `npm run typecheck` (web-user) → clean.
- `npm run lint` (web-user): no new findings (pre-existing errors in
  `playground.tsx`/`auth-modal.tsx`/`layout.tsx` only).
- Throwaway probe of `classifyResult` for recovery/video/midi/text/persona/music
  and of `buildMidiFile`/`lrcToSrt` (MIDI header `MThd`, format 1, expected
  73-byte length; SRT timestamps). Harness removed after.

## Follow-ups

- `subtitle_detail` still returns `subtitle: ""` (Suno has no captions route);
  the UI derives SRT from `lrc`/`aligned_lines`. A server-side SRT field would
  remove that client-side assumption.
- Consider a server-side `.mid` export for non-UI API consumers; today MIDI is
  only offered through the dashboard.
