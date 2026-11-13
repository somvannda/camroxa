# PARITY REMOVAL LIST (D-034)

Strict parity says a Studio control with no reference counterpart is removed, not
kept beside the clone. This is the audit that decides which ones those are.

## Method

1. Every editor label, menu item and panel name is compared against
   `reference/ui-strings.json` (strings harvested from the captured reference
   session) and the `Ref` column in `SUNO_STUDIO_FEATURE_INVENTORY.md`.
2. A feature marked `H` (seen in the reference) or present in the harvested
   strings is **KEEP**.
3. A feature with no reference evidence is a **candidate**. It is removed only
   after a second check, because the harvested string set is not the whole app
   (it is the screens we captured):
   - search the 85 captures in `reference/screens/` for the control;
   - search the shipped bundle for the label or endpoint.
4. Anything still unproven is marked **VERIFY** and stays until the next capture
   pass, so we never delete a real reference feature by accident.

## Result (2026-11-13)

| Feature | Reference evidence | Verdict |
|---|---|---|
| MIDI chord + arpeggiator modes | `Chord`, `Arpeggiator` in `ui-strings.json`; MIDI-012 `H` | KEEP |
| MIDI instrument selector | `Instrument` in `ui-strings.json` | KEEP |
| MIDI transpose / clear notes | `Transpose`, `Increase/Decrease Pitch` in strings; MIDI-006 `H` | KEEP |
| MIDI file import / export | MIDI-011 `H`, `Download MIDI` in strings | KEEP |
| Master presets | ADV-017 `H` (mastering presets); `Preset` in strings | KEEP |
| Personas | GEN-025/026 `B` | KEEP |
| Get Stems dialog | ADV-001…004 `B`, stems strings | KEEP |
| Ruler section markers | ARR-026 `H`, `Create Section` in strings | KEEP |
| Remove FX | `Remove FX` in strings | KEEP |
| `Z` zoom | ARR-004 `H` | KEEP |
| Volume / pan automation | TRK-021/022 `H`, `Automation` in strings | KEEP |
| Track groups + group mix | ARR-027 `H`, `Group`/`Groups` in strings | KEEP |
| Heal Edits | `Heal Edits` in strings | KEEP |
| Get MIDI (transcription) | `Get MIDI`, `Transcribe the selection to a MIDI file` in strings | KEEP |
| Polled presence + remote cursors | PRJ-017/018 `H`, `Cursor` in strings | KEEP |
| Clip-settings copy / paste | ARR-014 (clip copy/paste) `H`; no captured "Copy settings" label | VERIFY |
| Remix | No `Remix` string in the harvested set, but it is a core song action on the reference | VERIFY |
| Footer Plugins / Automation / Clip editor / Take lanes | all four labels in strings | KEEP |
| **Track groups** (named groups with volume/mute/solo) | No `group`/`bus`/`folder`/`parent` key in any of 11 real documents; the S19 track menu has no group item; the "A" badge is a route indicator | **REMOVED** 2026-11-13 |
| **Wavetable Designer** (harmonic partials, save custom table, select on clip) | No counterpart: `Wavetable` exists only as an asset category (`3 × Wavetables`, `used on`), never as an editor | **REMOVED** 2026-11-13 |

## What removal means for the document

The Suno state has no field for a designed table, so under D-034 these fields go
with the UI:

- `lanes[].wavetableId` (clip override)
- the custom-table library entry (`lib/studio-wavetable.ts` storage)
- the MIDI panel's "Design table" control

The rest of the MIDI synth (instrument voice, notes, bend/mod lanes) stays: those
map onto the reference's MIDI clip.

## Settled (owner, 2026-11-13)

- **Literal pixels are not the goal.** D-025 stays: we match captured geometry,
  spacing and type sizes, and keep the CAMXORA palette and wordmark. Copying
  Suno's trademarked look is out of scope.
- **Unverified features stay** until a capture proves Suno does not have them.
  `Remix` and clip-settings copy/paste are VERIFY, not removal candidates.

## Sync coverage after the live capture

The document side is now measured against a real schema
(`SUNO_STUDIO_STATE_SCHEMA.md`). Mapped today: bpm/meter, master level, loop,
track name/colour/hidden/mute/solo/volume/pan, MIDI clips and notes, track volume
automation. Still pending: audio assets, clip trim/fades, effects chains, master
chain, section markers, groups, pan automation. `STUDIO_STATE_COVERAGE` in
`musicapi/src/sunoStudio.ts` is the list the health endpoint reports, so this
section cannot drift from the code.

## Designed plugins: a decision, not a wiring gap (2026-11-13)

Our custom plugin designer writes parameters to a local document; Suno has no
parameter-import endpoint. What it has is an **agent job**:

```
POST /api/agent/author-plugin
  { instruction, required_controls, studioAgentSessionId, studioProjectId }
  -> { job_id }
GET  /api/agent/author-plugin/{job_id}
```

(from `reference/endpoint-inventory.json`). So mirroring a designed plugin means
asking Suno's agent to author one and then referencing the returned
`pluginVersionId` — a generative, credit-spending, non-deterministic flow, not a field
mapping. Three ways forward, and one of them must be chosen:

1. **Rebuild the designer on their agent** — closest to parity, spends credits per
   design and changes a shipped feature's architecture.
2. **Drop the designer** — what D-034 says when a feature has no mapped document field,
   but Suno *does* have plugin authoring, so this deletes capability the reference has.
3. **Keep it local and record it as a deliberate divergence** — honest, documented, and
   reversible; the chain entry simply stays out of `signalChain` on Suno.

Until someone picks, the codec keeps custom entries out of `signalChain` and the sync
docs list them under "still unmapped". Nothing silently drops: a project with a
designed plugin reports the same `skipped_clips`-style gap through the coverage list.

