# SUNO STUDIO STATE SCHEMA

What a Suno Studio project document actually contains, captured from real
projects and proven by a live save. This is the source of truth for
`musicapi/src/studioStateCodec.ts`.

## Provenance

- **Capture (read-only, 2026-11-13):** `GET /api/studio/list-projects` and
  `GET /api/studio/project/{id}` for 11 projects on one Camxora-owned pool
  account, via the production `__client` cookie (decrypted locally, never
  written to disk). No project was modified.
- **Contract:** the shipped client bundle (`/api/studio/create-project`,
  `save-project`, `project/{id}`) decoded from the captured session.
- **Live verification:** one throwaway project created, saved twice, read back,
  hit with a stale save, then archived. Results in §7.

## 1. Project envelope

```
GET /api/studio/project/{id} -> {
  id, title, owner_user_id, created_at, updated_at, archived,
  state,                 // object (some older rows store it as a JSON string)
  latest_version_id,     // absent on a brand-new project, present after first save
}
```

`POST /api/studio/create-project?title=&major_version=` returns `{id, title}` and
creates a project with **no** `latest_version_id` and an empty state.

`POST /api/studio/save-project {project_id, state, title, base_version_id}` → `{version_id}`.
A stale `base_version_id` answers **409** with `{latest_version_id}`. Rate limiting
is 429.

## 2. Top-level `state`

Keys seen across the captured projects (project count in brackets):

```
actors[9]                 layout[11]               selection[2]
amplitude[11]              libraryPanelState[9]     songFadeInBeats[11]
contextualWindowConfig[9]  limiterLookaheadMs[9]    songFadeOutBeats[11]
editorPointerModes[11]     loop[11]                 styleSummary[1]
lyricsCorrectionsByClipId[11]  majorVersion[9]      tab[9]
markersRegistry[11]        masterRoutingMode[9]     takePreviews[9]
metadata[3]                masterSignalChain[9]     timeSignatureChanges[11]
metronome[11]              midiCcMappings[9]        timing[11]
midiController[3]          midiControllerSignalChain[9]  title[1]
midiNotePreviewEnabled[9]  recording[9]             tracks[11]
                           routing[9]
```

The codec generates: `title, majorVersion, timing, timeSignatureChanges,
amplitude, songFadeInBeats, songFadeOutBeats, loop, metronome,
editorPointerModes, tracks, selection`. Every other key is copied from the
baseline, so a save never erases state we have not modelled.

## 3. Transport and meter

```
timing: { type: "manual" | "follow-track", bps, bpsAutomation, lockBPS?,
          firstBeatSeconds?, fallbackBPS?, trackId? }
timeSignatureChanges: [{ startBeats, subdivisionsPerBar, beatsPerSubdivision }]
loop: { enabled, startBeats, endBeats }
metronome: { enabled, amplitude }
```

- `bps` is **beats per second** (`bpm / 60`).
- `beatsPerSubdivision = 4 / denominator`, `subdivisionsPerBar = numerator`
  (4/4 → 4 and 1; 6/8 → 6 and 0.5).
- Seconds → beats: `beats = seconds * bps`.

## 4. Tracks

`state.tracks` is an **array** (not a map). Two shapes exist: 20 keys for current
tracks, 16 for older ones.

```
{
  id, name, color, type: "audio" | "midi",
  height, hidden, arm, mute, solo,
  amplitude,      // 0–1 (1 = unity)
  balance,        // -1..1
  eq: { enabled, band1..band6: { type, frequency, gain, q, enabled } },
  routingMode, signalChain: [{ id, pluginVersionId, presetId?, bypassed, params, paramAutomation }],
  faderAutomation: [{ timeBeats, value }],
  clips: [...],
  takeLanes: [{ id, name, type, height, dismissed, clips, clipCreationIntents }],
  takeLanesExpanded, clipCreationIntents: [],
}
```

Older tracks omit `signalChain`, `faderAutomation`, `routingMode` and
`takeLanesExpanded`. MIDI tracks carry no `instrument`; the synth lives in
`signalChain`.

## 5. Clips

```
{
  id, type: "audio" | "midi", name, color?,
  startBeats, endBeats, readStartBeats,
  fadeInBeats, fadeOutBeats, fadeInCurve, fadeOutCurve,
  mute, amplitude?, transposition?,
  clipId?,            // audio: the source clip
  streaming?, warp?: { enabled, markersHash, awaitingAnalysis },
  loop: { enabled, startBeats, endBeats },
  asset?: { id, type },      // audio: the Suno song/upload asset
  midi?: {
    notes: [{ id: number, startBeats, durationBeats, pitch, velocity }],
    controlChanges: [], pitchBend: [], channelPressure: [], sysex: [],
  },
}
```

Notes use **beats and numeric ids**; the codec derives a stable int32 from the
local note id.

## 6. Mapping used by the codec

| Local document | Suno state | Notes |
|---|---|---|
| `bpm` | `timing.bps = bpm/60` | verified |
| `timeSignature` | `timeSignatureChanges[0]` | verified |
| `masterVolume` | `amplitude = volume/100` | verified |
| `loopStart/loopEnd` | `loop` | verified |
| `tracks[].volume` | `tracks[].amplitude = volume/100` | verified |
| `tracks[].pan` | `tracks[].balance = pan/100` | verified |
| `tracks[].muted/solo/hidden` | `mute/solo/hidden` | verified |
| `tracks[].color/name` | `color/name` | verified |
| `tracks[].volumeAutomation` | `faderAutomation[{timeBeats,value}]` | written, pending read-back |
| `lanes[].start/duration` | `startBeats/endBeats` | MIDI verified live |
| `lanes[].midi.notes` | `clips[].midi.notes` | verified live |
| generated clip asset | `asset {id,type:"song"}` | when the local clip carries a Suno clip id |
| local upload without a Suno asset | — | — | **not mirrored**; the clip is reported in `skipped_clip_ids` |
| audio clips already on Suno | preserved from the baseline | never dropped by a save |

Track/clip ids are stable UUIDs derived from the local id, stored back as
`sunoId` when a document is pulled, so saves update instead of duplicating.

## 7. Live verification (2026-11-13)

Throwaway project, saved through the same API the mirror uses:

| Step | Result |
|---|---|
| `create-project` | 200, project id returned |
| first `save-project` (`base_version_id: null`) | 200, `version_id` A |
| read back | `bps=2` (120 BPM), 3/4 meter, 1 MIDI track, 1 clip `startBeats=4 endBeats=12`, 2 notes with beats values |
| second save (base A, 90 BPM) | 200, `version_id` B |
| read back | `bps=1.5`, `latest_version_id == B`, 1 track |
| stale save (base A) | **409** with `latest_version_id = B` |
| archive | 200 |

Second probe (audio): a saved audio clip kept `asset {id, type:"clip"}`,
`clipId`, `startBeats 0 / endBeats 16` and Suno's default `warp`; the project was
archived afterwards.

The project was archived after the probe.

## 8. Still unmapped

- `signalChain` plugin params: captured (hundreds of parameter names) but our
  plugin ids do not map to Suno's `pluginVersionId` yet.
- `masterSignalChain`: captured compressor/EQ params, same id-mapping problem.
- Audio clip timing/trim/fades for clips whose audio is not on Suno.
- `takeLanes` semantics (alternate takes) beyond an empty lane.
- `asset.type` values other than `"clip"` (uploads).

## 9. Section markers (`sections`)
`sections` is a registry keyed by id:

```
sections: {
  "<id>": { id, name, startBeats, endBeats, color }
}
```

Verified on 2026-11-13 by saving two synthetic markers on a throwaway project and
reading them back: both survived with their ids, names, colours and beat ranges
(the first ends where the next begins). The codec writes this shape from
`data.markers` and projects it back when loading a Suno document.

## 10. Plugin catalog ids (signalChain)

Captured read-only from the same account's project chains on 2026-11-13
(`pluginVersionId`, use count, parameter names). This is what a future effects
mapping needs; the codec does not write chains yet.

| Role | `pluginVersionId` | Uses | Parameters |
|---|---|---|---|
| Synth (MIDI voice) | `77cd4e27-c6cc-47ae-981a-7342778e8ff5` | 11 | 119 params (oscillators, envelopes, filters, LFO matrix) |
| Compressor | `a4838315-…` | 25 | attack, gain, input, knee, makeupGain, output, ratio, release, threshold |
| Convolution | `ddcfbfdc-…` | 7 | crossImpulseResponse, gain, impulseResponse, mix, predelay, trimEnd, trimStart, width |
| Limiter | `bf422c67-…` | 5 | attack, link, lookahead, preGain, release |
| EQ (v1) | `b1a718a1-…` | 28 | enabled1–6, freq1–6, gain1–6, q1–6, … (31 params) |
| EQ (v2) | `91a75c2b-…` | 3 | same 31-param shape |
| Reverb | `dec400a6-…` | 6 | damping, highCut, lowCut, mix, predelay, time, width |
| Delay (v1) | `e2b9270b-…` | 14 | beats, feedback, highCut, lowCut, milliseconds, mix, mode |
| Delay (v2/v3) | `e871ca3a-…`, `1b5d6b90-…` | 6 | same shape |
| Distortion / crusher | `20c5b585-…` | 5 | Bias, Crush, Input Gain, Mix, Output Gain, Post Cutoff, Post Resonance, Pre Tilt, Shape |
| Chorus | `537ba288-…` | 3 | attack, depth, mix, rate (1/16, 1/8, 1/4), release |
| Gate | `14fb47e6-…` | 6 | attack, floor, hold, release, threshold |
| Filter / warm drive | `d51aa72c-…` | 3 | cutoff, filter type, high-pass resonance, low-pass resonance, mix, warm drive |
| Stereo / master utility | `d645cdcd-…` | 3 | Bass Mono Crossover, Level, Output Trim, Pan, Phase Invert, Stereo Flip, Width |

Notes for the mapping:

- Parameter names are case-sensitive (`Bias`, `Input Gain`, …), and some ids exist
  in several versions (EQ, Delay) — pick the most-used one and keep the others in
  a fallback list.
- Our local plugin ids are semantic (`compressor`, `reverb`, …), so a mapping table
  plus a per-parameter translation (`gain` → `output`) is required.
- Entries are `{ id, pluginVersionId, presetId?, bypassed, params, paramAutomation }`;
  `params` values are numbers, and `paramAutomation` is an object (empty in every
  captured entry).
- The synth plugin carries the MIDI instrument voice; our `instrument` selector
  currently maps to a simple oscillator, which is a separate gap.
