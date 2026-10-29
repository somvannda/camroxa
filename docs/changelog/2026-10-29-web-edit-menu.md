# Edit menu parity + Sample

**Date:** 2026-10-29
**Branch:** `feat/web-edit-menu`
**Surface:** `camxora.com` Create/Library + Platform API

## What Suno's Edit menu does

Checked against Suno's help centre and release notes (not guessed):

| Item | Suno behaviour |
|---|---|
| Extend | continue the song from a point, new lyrics/style, two takes |
| Crop | keep a start/end window, produces a new song |
| Remove Section | cut a middle window out, produces a new song |
| Reverse | play the song backwards, new song |
| Adjust Speed | change playback rate, new song |
| Find a Collaborator | bring another creator onto the track |
| Fade In / Fade Out | fade the ends, new song |
| Replace Section | regenerate a 10–30 s window with new lyrics, two takes |
| Get Stems / MIDI | vocals only, 2 stems, or 12 stems |
| Remaster | re-render at a newer model |
| Open in Studio / Open in Editor | jump to the editor |
| Sample this song (Remix ▸) | drag a section on the waveform; that slice seeds a new song |

## What this branch ships

**Backend** (`platform_api`)

- `audio_preview_trim`: `trim_audio_range_bytes`, `remove_audio_range_bytes`,
  `transform_audio_bytes`, `probe_audio_duration_bytes` (ffmpeg; duration probed
  from a temp file because ffprobe cannot read a pipe).
- `WebMusicService.request_studio_sample()` — cuts the selected section, stores
  it, and hands it to Suno as an uploaded clip (`/internal/studio/upload-cover`),
  so the new song grows from that slice. `sample` joins the feed-row types.
- `WebMusicService.derive_generation()` — Crop, Remove Section, Reverse,
  Adjust Speed, Fade In, Fade Out. A new `suno_tasks` row is written with a
  **task-scoped** B2 key (`edits/<user>/<task-id>/ok.mp3`), duration and title
  suffix, so the result streams and downloads like any other song.
- Routes: `POST /studio/generations/{id}/sample` (202) and
  `POST /generations/{id}/derive` (201).

**Frontend**

- `components/EditSongModal.tsx` — one dialog for extend, crop, remove section,
  replace section, sample, speed, and fades: waveform-style start/end sliders
  with timecodes, a 30 s sample cap, the 10–30 s Replace Section window, speed
  and fade sliders, lyrics and prompt fields.
- `components/SongRowMenu.tsx` — Edit now mirrors Suno's order, with
  **Get Stems / MIDI** as a submenu and Sample wired in Remix.
- Both pages pass handlers; results land in the feed/library.

## Deliberate differences

- No Pro badges: CAMXORA is credit-based, there is no Pro plan.
- Sample dialog omits Chop / As-is / Blend, Keep pitch & speed and the
  Audio/Style influence sliders: Suno's upload-cover surface accepts a clip and
  a prompt only, so those controls would be dead. The slice itself is used
  unchanged, which is "keep pitch and speed" by construction.
- Find a Collaborator copies a share link (no collaborator graph in CAMXORA yet).

## Verification

- `python -m py_compile` clean; `npx tsc --noEmit` clean; `check:ui` compliant.
- Live: `POST /generations/{song}/derive {"operation":"reverse"}` → **201**,
  `title: "Drive tonight (Reversed)"`, `status: SUCCESS`, `ready: true`, stream
  URL minted, duration 226.9 s. Test rows removed afterwards.
- ffmpeg slice helper verified against a generated tone (10 s → 3 s).

## Follow-ups

- Sample and derive run locally. Suno's own editor endpoints (crop / reverse /
  speed / fade) are not exposed by the current musicapi client; capturing them
  from Suno's bundle would let these proxy Suno instead.
- Replace Section still returns whatever musicapi/Suno gives (Suno makes two
  takes; we surface the first).
- Use as Inspiration (Inspo slot, up to 4 references) is not built yet.
