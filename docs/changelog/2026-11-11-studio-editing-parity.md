# Studio editing parity: time selection, warp markers, clip settings, bounce, MIDI export

**Date:** 2026-11-11
**Branch:** `feat/studio-rebuild` (stack of `feat/studio-time-selection`, `-warp-markers`, `-bounce`, `-midi-export`, `-audio-settings`, all merged)
**Surfaces:** camxora.com (Studio editor)
**Status:** implemented, gates green, not deployed

## Summary

Five captured Studio feature areas that were still missing or partial are now built,
tested and recorded: time-selection editing (N-01), warp markers and the audio clip
editor (S30), per-clip Volume/Loop/Reverse/Pitch/Speed and Quantize (§81), track bounce
(N-06) and MIDI download (N-05).

The editor previously had only clip selection, no audio clip editor, and no way to
hand back the arrangement as MIDI or a per-track mixdown. Three of these change the
interaction model rather than the feature list, which is why they landed together with
decisions rather than as isolated menu rows.

## Product impact

- **Time selection**: dragging the bar ruler selects a range (click still seeks,
  `Shift`-click and `Shift ←/→` extend, `Esc` clears). The range has its own rendering
  and verbs: loop selection, duplicate time, delete time on all tracks or the focused
  one, export the selection, clear. Delete/duplicate ripple the arrangement instead of
  removing whole clips.
- **Audio clip editor (double-click an audio clip)**: the captured `Clip Settings`
  column beside a zoomed waveform — Volume in dB, Loop, Reverse, Pitch, Stretch modes
  with Formant, Speed and Quantize — plus the white pennant warp markers on the
  waveform (drag to move, click to select, `Ctrl A`, `Shift Q`).
- **Track bounce**: the track options menu renders that track through its own effect
  chain and hands back a WAV mixdown, with the reference's per-track reporting
  (`Exporting on track #` → `Bouncing <track>…` / `Bounce on <track> started!`).
- **MIDI download**: the clip menu exports the selected MIDI clips as one Standard MIDI
  File, preserving their timeline offsets.

## Technical impact

- `lib/studio-time.ts` — pure ripple edits: head/tail trimming with content-offset
  advance, MIDI notes rebased onto their slice, track `clipIds` rebuilt, stable ids
  when a clip's head does not survive.
- `lib/studio-warp.ts` + `lib/studio-peaks.ts` — marker pairs (timeline seconds + source
  seconds), three auto-generation modes, onset detection over the decoded peak envelope
  with an honest bounds fallback, quantize to beat or explicit grid.
- `lib/studio-clip-audio.ts` — one planner (`planClipPlayback`, `clipRate`, `reverseBuffer`,
  `dbToGain`, `quantizeStep`) used by **both** live playback and `renderMix`, so a bounce
  or export hears the clip exactly as the editor does. Pitch and Speed both map to
  `playbackRate`; there is no time-stretcher.
- `lib/studio-midi-file.ts` — format-0 SMF writer (480 PPQ, tempo meta, VLQ deltas).
- `components/studio/StudioAudioEditor.tsx` — the captured editor band; `StudioTimeline`
  gained the range overlay, ruler drag and the double-click hook; the shell owns the
  pointer sessions, persistence and the range menu.
- Selection model: the time range is transient (not persisted), and clip/time selection
  are mutually exclusive (D-029).

## Files touched

`camxora.com/components/studio/{StudioEditorShell,StudioTimeline,StudioTrackPanel,StudioAudioEditor,Waveform}.tsx`,
`camxora.com/lib/{studio-time,studio-warp,studio-peaks,studio-clip-audio,studio-midi-file,studio-export,studio-help}.ts`,
`camxora.com/app/globals.css`, new tests under `camxora.com/tests` and
`camxora.com/tests/e2e`, plus `docs/studio/*` (decisions D-029…D-032, parity log,
progress, handoff).

## Migration/deploy

No migration. Project documents gain optional fields (`warp`, `audio`) that older
readers ignore and that are absent until edited; existing exports are byte-identical
because default clip settings add no nodes and no rate change. Deploy follows the usual
verified-source path once the branch reaches `main`.

## Tests

| Layer | Result |
|---|---|
| `npm run typecheck` / `npm run check:ui` | clean |
| `npm run build` | all routes build |
| Vitest | **255 passed** (27 files) |
| Playwright (studio) | **116 passed / 1 skipped** (43 specs) |
| Backend, for the merged `main` | **3349 passed**, 2 known warnings |

New coverage worth naming: exported RMS at 0 dB vs −12 dB proves clip gain reaches the
mix; a routed click-track WAV proves transient markers land on attacks; the MIDI spec
parses the downloaded bytes; a stale `main` test expecting the old v3 charge call shape
was corrected (`provider=ai_service`).

## Follow-ups

- **Render-in-place bounce** is blocked on configured upload storage
  (`storage_not_configured`; B-006/B-007). The mixdown form is what the captured strings
  describe.
- **Key/BPM rows** stay blocked: the corpus carries neither field (D-016).
- **S60/S61 captures** still need a signed-in reference session with real triggers.
- PR is not open yet: local `gh` token is invalid (`gh auth login -h github.com`), and
  merging to `main` is a ship decision.
