# UX · UI · FLOW — captured behaviour model

Consolidated from the live captures (spec §44–§51). This is the document to read
before building any Studio screen. Where a rule is inferred rather than observed it
says so.

---

## 1. The interaction model in one page

The Studio is a **document editor with a transport**, not a form.

```
open project ─► arrangement document ─┬─► edit (non-destructive, undoable)
                                      ├─► play (transport)
                                      ├─► generate (Magic Bar → job → clip)
                                      └─► export (server render)
```

Five rules that hold everywhere:

1. **Everything is a document edit.** Clip moves, mixer changes, plugin params and
   markers all mutate one versioned document. Undo is document-level.
2. **Destructive verbs are rare and guarded.** Delete asks; time-deletes (`DELETE
   TIME`) are explicit; everything else is reversible.
3. **Long operations are jobs.** Generation, stems, MIDI extraction, export — all
   return immediately and report progress elsewhere.
4. **Selection is contextual.** What the inspector, the Magic Bar and the footer show
   depends on whether a clip, a track, or nothing is selected.
5. **The grid is the contract.** Bars on top, time at the bottom, and every object
   snaps to one of them.

## 2. Selection model

| Selection | Trigger | What it drives |
|---|---|---|
| none | click empty lane area | **seeks the playhead** (observed §44) |
| clip | click inside a clip | inspector (clip editor), Magic Bar context, footer FX chain |
| time range | drag on the ruler / `SHIFT ←→` | range export, delete/duplicate time |
| track | click track header | plugins/automation panels, mute/solo/arm |
| take | take-lane click, promoted with `ENTER` | which audio source plays |

Rule: **clicking empty space never deselects silently** — it moves the playhead, which
is the reference behaviour. Our editor currently selects on lane click; that must
change.

## 3. Primary flows

### 3.1 Start

```
/studio (home)
  ├─ New project ──► empty arrangement (1 audio track, Main bus)
  ├─ Resume card ──► last project
  ├─ project card ─► ?project=<id>
  └─ from a song ──► seeded project
```
Onboarding overlay (first run): `Edit Your Song · Drum & Bass Demo · Upload Audio ·
Video Tutorial` + `Empty Project` + `Browse Studio projects` + `Skip to the empty project`.

### 3.2 Create inside the arrangement (Magic Bar)

```
select a spot on the timeline
  ► Magic Bar placeholder changes to a suggestion
  ► type / choose model
  ► ENTER (Ask Studio) → job
  ► placeholder clip appears on the lane
  ► job completes → clip replaces placeholder
  ► failure → the clip states the reason; credits refunded
```

### 3.3 Arrange

```
add track (SHIFT T / Audio·MIDI·Upload)
  ► drag clip from library or move an existing clip (ghost drag, one DSP apply on drop)
  ► trim / split (CTRL E) / duplicate (CTRL D) / fade (SHIFT F)
  ► marker flags on the ruler for sections
```

### 3.4 Mix

```
select a track
  ► footer chips show its chain (Delay + …)
  ► Plugins: add effect → plugin card opens in the dock (multiple at once)
  ► tweak → preset becomes "Custom" → Update writes it back
  ► Automation: volume / pan / CC / velocity lanes
  ► Main: level + mute
```

### 3.5 Export

```
Export ▸ Full Song | Selected Time Range | Multitrack
  ► job → progress → artifact download
```
Server-side render; the browser does not mix for export.

### 3.6 Share

```
project menu ▸ Share Project
  ► copy link (view + fork)
  ► recipient gets their own editable copy; owner's project unchanged
```
There is **no live co-editing on a link** — do not build presence into it.

## 4. UI composition rules

| Rule | Evidence |
|---|---|
| Header = project identity + transport + session settings, in that order | §44.1 |
| Transport is centred; BPM/signature/Export/Library right-aligned, separated by a gap | §44.1 |
| Track column is fixed width; canvas takes the rest and shrinks when a panel opens | §28, §40 |
| Two rulers: bars on top, time at the bottom | §44.3 |
| Track colour is semantic per instrument family, not cycled | §44.5 |
| Clips: dark header band + waveform, white 2 px border when selected | §44.6 |
| Menus: icon + label + right-aligned accelerator, grouped by dividers | §47 |
| Menus are **generated from state**, not fixed | §47 |
| Right-side panels dock; plugin windows can pop out and the choice persists | §39, §50 |
| Footer holds the chain chips for the selected track | §44.7 |
| Every control has hover help behind a global `What's This?` toggle | §7, §38 |

## 5. State coverage

| State | Rule |
|---|---|
| Loading project | skeleton, no layout shift |
| Empty project | one audio track + Main bus, `Add new track` affordance |
| No selection | inspector teaches: select a clip vs. select a track |
| Job running | placeholder object on the arrangement + progress |
| Job failed | reason on the object, credits refunded, retry offered |
| Save failed | persistent banner + retry; never a silent loss |
| Insufficient credits | cost shown before the action, purchase path in place |
| Policy/copyright block | verbatim reason; no retry until input changes |

## 6. Keyboard (user-facing summary)

`SPACE` play · `ALT SPACE` from selection · `ENTER` Ask Studio · `CTRL S` save ·
`CTRL Z` / `CTRL SHIFT Z` undo-redo · `CTRL C/X/V/D` clipboard · `CTRL E` split ·
`BACKSPACE` delete · `SHIFT T` add track · `SHIFT F` fade · `CTRL L` loop ·
`SHIFT C` metronome · `SHIFT R` record · `F2` rename · `CTRL K` keyboard ·
`CTRL =/-` zoom · `SHIFT 1/2` grid density · `1-4` panels · `SHIFT ?` shortcut sheet.

Full map: spec §36.

## 7. Copy rules

- Sentence case for labels, Title Case avoided except proper nouns.
- Placeholders are **actionable**: "Select a spot on the timeline and ask me to add a
  part", "Add a warm reverb to this track".
- Errors: what happened → why → what to do. Reference has 827 distinct error strings;
  mine them before inventing our own (spec §16, `reference/derived-features.md`).
- Never claim a capability we don't have. If a control is not wired, it does not ship.

## 8. What is still unobserved (do not invent)

- Playback-time visuals: meters, clip pulse, ruler scroll during play.
- Drag affordances: trim cursors, snap guideline, ghost opacity.
- Take-lane expanded layout and comping.
- Warp-marker editing.
- Per-workspace library view.
- Export dialog contents.
- Responsive rules below 706 px (and at 1024/1280).
