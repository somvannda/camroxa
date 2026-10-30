# Suno Studio `state` schema (from shipped bundles)

Recovered 2026-10-30 by scanning **133 JS chunks** (~9.1 MB) from
`/studio-welcome`, `/create`, `/library` and `/studio`. No HAR is required for
the shapes below; they are literal initialisers in the shipped editor bundle.

Evidence ids below are Turbopack module ids inside the chunk files:

| Module | What it is |
|---|---|
| `960687` | default editor state (`createEmptyProjectState`) |
| `46472` | track factories + track/arrangement type predicates |
| `979354` | `createStaticAudioArrangement` (audio clip shape) |
| `634782` | pre-save marker dedupe (`markersRegistry`, `actors`) |
| `805451` | default `timing` (120 BPM) |
| `140764` | Studio project HTTP client |
| `588758` | `render-state` body builder |
| `17660` | strips non-audio clips before render |
| `180172` / `950155` | drops muted clips before render |

## Default state (`960687`)

```jsonc
{
  "amplitude": 1,                      // Main fader, 0..1 (see audio engine)
  "sections": {},
  "lyricsCorrectionsByClipId": {},
  "metronome": { "enabled": false, "amplitude": 1 },
  "midiNotePreviewEnabled": true,
  "timing": { "type": "manual", "bps": 2, "bpsAutomation": [], "firstBeatSeconds": 0 },
  "timeSignatureChanges": [ /* default 4/4 at beat 0 */ ],
  "tracks": [],
  "actors": {},                        // { [userId]: { lastSeenAt } }
  "tab": {
    "selection": {
      "anchorBeats": 0, "focusBeats": 0,
      "trackIds": [], "focusedTrackId": null, "focusedTakeLaneId": null,
      "focusedArea": null,
      "arrangementAnchorBeats": null, "arrangementFocusBeats": null,
      "noteIds": [], "pluginIds": [],
      "warpMarkerSeconds": {}, "automationPointIndices": [],
      "contextBeforeBeats": 32, "contextAfterBeats": 32
    }
  },
  "loop": { "enabled": false, "startBeats": 0, "endBeats": 0 },
  "songFadeInBeats": 0,
  "songFadeOutBeats": 0,
  "layout": {
    "editorPanelType": null,
    "midiAutomationLaneId": "<default>",
    "midiAutomationLaneHeight": "<default>",
    "arrangementEditorHeight": "<default>"
  },
  "editorPointerModes": { "audio": "select", "midi": "select" },
  "masterSignalChain": [],
  "midiControllerSignalChain": [],
  "masterRoutingMode": "linear",
  "routing": {}
}
```

- `bps` is **beats per second**: `2` = 120 BPM. Seconds per bar (4/4) = 2.
- A new project is `{...defaults, tracks: [createAudioTrack()]}`.
- Tempo can be automated through `timing.bpsAutomation` (`[{beats, value, curve}]`).

## Track (`46472`)

```jsonc
// audio
{
  "type": "audio",
  "id": "<uid>",
  "input": null,
  "color": "<derived from id>",
  "name": "Audio Track",
  "clips": [],
  "clipCreationIntents": [],
  "height": "<default>",
  "solo": false, "mute": false, "arm": false,
  "amplitude": 1,          // volume, 0..1
  "balance": 0,            // pan, -1..1
  "instrument": "<default>",
  "soloTakeLaneId": null,
  "takeLanesExpanded": false,
  "hidden": false,
  "takeLanes": [],
  "eq": "<default>",
  "signalChain": [],
  "routingMode": "linear"
}

// midi: same fields, "type": "midi", no instrument
// video: { type, id, color, name, clips, height, solo, mute,
//          soloTakeLaneId, takeLanesExpanded, hidden, takeLanes }
```

## Clip / arrangement (`979354`)

```jsonc
{
  "type": "audio",
  "id": "<uid>",
  "streaming": false,
  "name": "Clip",
  "color": "#4a90e2",
  "transposition": 0,
  "formantCorrection": 0,
  "amplitude": 1,          // per-clip gain
  "startBeats": 0,         // timeline position
  "endBeats": 8,           // timeline end (length = end - start)
  "readStartBeats": 0,     // offset into the source clip
  "fadeInBeats": 0, "fadeOutBeats": 0,
  "fadeInCurve": 1, "fadeOutCurve": 1,
  "mute": false,
  "reversed": false,
  "loop": { /* default: disabled */ },
  "warp": { /* default: no markers */ },
  "asset": { "type": "clip", "id": "<suno clip_id>" }
}
```

`asset.type` is `clip` (Suno clip), `upload` (uploaded audio) or `video`.
MIDI clips carry `midi: { notes: [{ id, startBeats, durationBeats, pitch, velocity }] }`.

## Persistence contracts

### Save (`140764`)

```http
POST /api/studio/save-project
{ "project_id", "state", "title", "base_version_id" }
→ 200 { "version_id" }
→ 409 { "latest_version_id" }      // someone saved first
→ 429                              // too many saves
```

Before sending, the editor runs the `634782` pass:

- collect every `warp.markers` on clips/take lanes,
- deduplicate them into `state.markersRegistry` and replace each clip's
  `warp.markers` with `warp.markersHash`,
- prune `actors` entries that have no valid ISO `lastSeenAt`,
- keep the rest of the state verbatim (including `tab`, `layout`, `loop`).

The whole editor state is saved, UI selection included.

### Load

```http
GET /api/studio/project/{project_id}
→ { "state", "title", "latest_version_id", ... }
```

State is accepted when `"timing" in state && "tracks" in state`. The client then
hydrates it, and in **edit** mode (`/studio?clip=…`) reduces it to a single
track with `amplitude = 1`, `balance = 0`, `mute = solo = false`.

```http
GET /api/studio/{project_id}/version/{version_id}   → { "state", ... }
GET /api/studio/project_revision/{revision_id}      → { "state", ... }
POST /api/studio/project_revision/{revision_id}/clone  { "title", "major_version" } → { "id" }
```

## Mixer mapping (verified in the audio engine)

The engine builds the graph from the state document:

- `timeline.masterGain = state.amplitude ?? 1`
- `createTrack(track.amplitude, track.balance, solo, …, eq, signalChain, clips)`
- `createAudioClip(…, clip.amplitude, clip.startBeats, clip.endBeats,
  loop.startBeats, loop.endBeats, clip.readStartBeats, clip.fadeInBeats, …,
  clip.mute)`

So Main, track volume, pan, mute and solo all live in `state`, which is why
Camxora's local mixer is documented as local-only until autosave ships.

## Export (`588758`)

```http
POST /api/studio/render-state
{
  "title": "<title> (<state.editClipId> ? \" (Edit)\" : \"\")",
  "lyrics": "<lyrics>",
  "state": "<state after 17660 + 180172>",
  "project_id": "<id>",
  // one of:
  "studio_project_id": "<id>", "export_mode": "studio_export",
  "from_studio_project_id": "<id>", "export_mode": "rendered_context_window",
  "start_beats": 0, "end_beats": 0, "downbeats": [],
  "web_client_pathname": "/studio",
  "render_engine": "…", "encode_latents": true
}
```

`17660` keeps only audio clips with a `clip` asset (drops MIDI/video);
`180172` drops muted clips. Export modes captured: `studio_export`,
`rendered_context_window`, `selection_download_export`.

```http
POST /api/studio/render-state-multitrack  → { "download_url" }
GET  /api/studio/clip/{clip_id}/download?format=…   (poll until ready)
```

## Camxora implications

- Ruler must follow `timing.bps` (default 2 beats/s), not the current fixed
  1.25 s/bar.
- Our local `volume` (0–100) maps to `amplitude` (0–1); pan is `balance`.
- Clip position/length must be persisted as beats, not percents.
- `state.amplitude` is the Main fader — the value the mixer already drives
  locally.
