# SUNO STUDIO — IMPLEMENTATION SPEC

**Purpose:** the single document an implementer works from. Every surface, control,
placement, behaviour and API capability we have evidence for, plus an explicit
backlog of what is still uncaptured. If a feature is not in this document, it is not
cleared for implementation.

**Evidence modes**

| Tag | Source |
|---|---|
| `M` | Measured in a live authenticated session (geometry/tokens) |
| `L` | Observed in a live authenticated session (text/behaviour) |
| `B` | Recovered from the publicly shipped client bundle |
| `?` | Not yet captured — **do not implement from assumption** |

**Status vocabulary** (same as `README.md`): `IMP` implemented · `TST` testing ·
`VER` verified · `MISS` missing · `BLK` blocked.

Captured on 2026-10-30 from `suno.com/studio` at 1958×1245 (DPR 1). Bundle chunk
count 134. Numbers are checkpoints, not constants: re-capture before implementing
responsive rules.

---

## 1. Global frame `M`

| Property | Value |
|---|---|
| App background | `#101012` (`--color-background-primary`) |
| Shell background | `rgb(10,10,10)` |
| Surface secondary | `#1c1c1f` |
| Text primary | `#f7f4ef` |
| Text secondary | `#c2c2c1` |
| Base spacing | 4 px (`--spacing: .25rem`) |
| Body font size | 16 px |
| Typeface | **Neue Montreal** (commercial — substitute, do not ship) |
| Header height | **52 px** |
| Track panel width | **260 px** |
| Timeline | remainder, x 260 → viewport |
| Transport band | bottom, controls at y ≈ 1124–1157 |

Region order (left→right): track panel · timeline · (overlay) inspector/library.

## 2. Header `M L`

Layout rule: **transport centred**, **session settings right-aligned**.

| # | Control | x | Size | Behaviour | Ours |
|---|---|---|---|---|---|
| H-01 | Project menu | 115 | 126×32 | Opens project menu (§8.1) | IMP (menu differs) |
| H-02 | Undo | 254 | 36×32 | Undo last edit | IMP |
| H-03 | Redo | 292 | 36×32 | Redo | IMP |
| H-04 | Loop toggle | 781 | 34×32 | Toggle loop region playback | IMP |
| H-05 | Back to Start | 817 | 32×32 | Playhead → 0 | IMP |
| H-06 | Record | 851 | 32×32 | Arm/capture | IMP |
| H-07 | Play | 885 | 32×32 | Play/pause | IMP |
| H-08 | Stop/forward | 919 | 32×32 | Stop / advance | IMP |
| H-09 | Metronome | 963 | 32×32 | Click track | IMP |
| H-10 | Time `00:00.000` | 997 | 87×32 | Editable/label | IMP |
| H-11 | Bar.beat `001.1.1` | 1090 | 87×32 | Position readout | IMP |
| H-12 | BPM `120 BPM` | 1641 | 70×32 | Edit tempo | IMP |
| H-13 | Time signature `4/4` | 1713 | 50×32 | Edit meter | IMP |
| H-14 | Export menu | 1775 | 80×32 | Export dialog | IMP |
| H-15 | Open library | 1866 | 82×32 | Toggle library panel | IMP |

Note the ~550 px gap between the clock and BPM: it is the visual separation of
"transport" from "session settings". Reproduce the grouping, not the exact pixel.

## 3. Track panel `M`

| # | Element | Geometry | Behaviour |
|---|---|---|---|
| T-01 | Collapse tracks | 28×28 @ y53 | Collapse the panel |
| T-02 | Collapse controls | 28×28 @ y53, x232 | Hide per-track controls |
| T-03 | Track colour strip | 10×85 @ x8 | Colour picker (T-11) |
| T-04 | Collapse chevron | 16×32 @ x24 | Collapse this track |
| T-05 | Track name | 89×17 @ x48,y98, 11 px | Rename |
| T-06 | Mute | 28×32 @ x150 | Mute |
| T-07 | Solo `S` | 28×32 @ x179 | Solo |
| T-08 | Arm `A` | 28×32 @ x208 | Record arm |
| T-09 | Row extend | 16×32 @ x236 | Extend row / options |
| T-10 | `Add new track` | full 260 px column | Add-track menu (§8.3) |
| T-11 | Master mute ×2 | 28×32 @ y1124, y1157 | Main bus mute |

Track row rhythm: header at `y=90`, control band at `y=126` (36 px step).

## 4. Timeline `M L`

| # | Feature | Evidence | Notes |
|---|---|---|---|
| TL-01 | Bar ruler (`00:00 → 02:00` visible at this zoom) | L | 15 s major ticks at default zoom |
| TL-02 | Playhead | L | Follows transport, seek on click |
| TL-03 | Clip blocks | L | Title + waveform |
| TL-04 | Empty-state cards over the timeline (onboarding) | L | 4 cards (§11) |

Not yet measured: clip height, lane height, ruler height, zoom steps, loop-bracket
geometry. See §14 backlog.

## 5. Prompt / Studio AI `M L`

| # | Control | Geometry | Copy |
|---|---|---|---|
| P-01 | Prompt input | 335×38 @ (941,844) | "Select a spot on the timeline and ask me to add a part" |
| P-02 | Submit `Ask Studio` | 42×42 @ (1088,842) | — |
| P-03 | Add to prompt `+` | 32×32 @ (798,799) | — |
| P-04 | Conversation toggle | 32×32 @ (1352,800) | — |
| P-05 | Collapse | 32×32 @ (1388,800) | — |
| P-06 | Model selector | 53×32 @ (1331,840) | shows `v6` |
| P-07 | Send | 32×32 @ (1388,840) | — |
| P-08 | `BETA` badge | L | marks the AI feature |

Behaviour: the prompt is **placement-aware** — it asks the user to select a timeline
spot, then generates there. This is the single most important interaction to get
right; it is the DAW's "create" verb.

## 6. Model catalog `L`

Captured verbatim from the live model picker:

| Model | Description | Cost |
|---|---|---|
| `v6 Pro` | "Powerful. Versatile. Refined." | plan-dependent |
| `v6-wild Pro` | "Best for experimental ideas." | plan-dependent |
| `v6-mini` | "A free, more efficient version of premium v6 models." | free |
| `Create Custom Model` | "Create a model based on your uploads" | **100 Credits** |
| `ALL MODELS` | section header | — |

Our implementation must map model ids through `musicapi`, never hardcode vendor
labels in the UI (pricing/limits live in `pricing`).

## 7. Footer / transport `M`

| # | Element | Behaviour |
|---|---|---|
| F-01 | Master `Main` fader + meter | Master volume, persisted |
| F-02 | `Mute main` (two rows) | Master mute |
| F-03 | Learn menu | Opens help/tour |
| F-04 | "What's This?" card | "Hover over any control to see how it works. Click Learn to turn What's This? off." with `Dismiss` / `Turn off` |

The hover-help system is a real feature: every control has an explanatory tooltip,
toggled globally by `Learn`.

## 8. Menus and dialogs

### 8.1 Project menu — `?` (trigger works, overlay not captured)
Expected contents (from bundle + prior captures): rename, versions, duplicate,
archive, delete, share. **Capture before implementing.**

### 8.2 Export menu — `?` (overlay not captured)
Expected: range (full/selection), format, stems. **Capture before implementing.**

### 8.3 Add track — `L` ✅

```
Add a track
  Audio    A
  MIDI     M
  Upload   U
```

Single-letter accelerators are shown in the menu — implement both the menu and the
keys.

### 8.4 Clip context menu — `?`
### 8.5 Track options menu — `?`
### 8.6 Library panel — `?` (opens; content not captured; `Close library` exists)

## 9. Library panel

Trigger label observed: `Open library` → after opening: `Close library`.
Tabs/content not captured. Prior evidence suggests songs / liked / stems / uploads /
workspaces / projects. **Verify, do not assume.**

## 10. Onboarding overlay `L`

Title: **"How do you want to start?"**

| Card | Subtitle | Size |
|---|---|---|
| Edit Your Song | "Open a song from your library" | 238×232 |
| Drum & Bass Demo | "A finished track to play, poke at and pull apart" | 226×218 |
| Upload Audio | "Bring in a file from your computer" | 212×204 |
| Video Tutorial | "Learn all the basics" | — |

Secondary entries: `Empty Project`, `Browse Studio projects`, `Learn`.
Dismiss: `Skip to the empty project`.

## 11. Keyboard `B`

Key literals present in the studio chunks: `Space`, `Escape`, `Enter`, `ArrowLeft`,
`ArrowRight`, `ArrowUp`, `ArrowDown`, `Backspace`, `Delete`, `Home`, `End`, `Tab`.
Exact bindings are **not yet mapped** (modifier detection failed on minified code).

Known from the add-track menu: `A` audio, `M` MIDI, `U` upload.

Prior captures (verify): `Space` play/pause, `Cmd/Ctrl+Z` undo, `Shift+Cmd/Ctrl+Z`
redo, `Delete` remove clip.

## 12. API surface — 81 studio-related endpoints `B`

Full machine-readable list: `reference/endpoint-inventory.json`.
Human table: `reference/endpoint-inventory.md`.

Capability groups recovered:

| Group | Representative paths | Ours |
|---|---|---|
| Project lifecycle | `create-project`, `create-or-load-project-for-clip/{clip_id}`, `project/{project_id}`, `save-project`, `project_revision/{id}`, `project_revision/{id}/clone` | IMP |
| Render/export | `render-state`, `render-state-multitrack`, `clip/{clip_id}/download` | IMP |
| Clip edits | `edit/crop/{clip_id}`, `edit/fade/{clip_id}`, `clips/adjust-speed`, `clips/reverse-clip` | IMP |
| Lyrics/alignment | `gen/{clip_id}/aligned_lyrics/v2|v3`, `gen/{clip_id}/downbeats`, `gen/{clip_id}/waveform-aggregates` | partial |
| Personas | `persona/create`, `persona/get-personas`, `persona/get-persona/{id}` | IMP |
| Comments/perms | `gen/{clip_id}/comments*`, `clip/{clip_id}/permissions*` | partial |
| Clip state | `gen/{clip_id}/convert_wav`, `wav_file`, `toggle_comments` | partial |

**Rule:** the reference's field names are the contract to match in `musicapi`
(D-008). Where we already expose a different shape, add a compatible path rather than
renaming ours.

## 13. What we already have vs. this spec

| Surface | Reference | Ours | Verdict |
|---|---|---|---|
| Header grouping | transport centred, settings right | similar but not measured | align |
| Track panel | 260 px fixed, 32 px controls | wider, different control order | align |
| Prompt bar | centred above transport, placement-aware | present, position differs | align |
| Add-track menu | Audio/MIDI/Upload + letters | present, different items | align |
| Model picker | 4 entries + credits | absent in DAW | build |
| Hover help (`Learn`) | global tooltip system | absent | build |
| Onboarding cards | 4 + 2 entries | absent | build |
| Library panel | tabs | songs/liked only | extend |
| Project menu | full lifecycle | present via dialog | reconcile |
| Export menu | not captured | present | reconcile after capture |

## 14. Capture backlog (blocks implementation)

| # | Missing | Why it blocks |
|---|---|---|
| C-01 | Project menu contents | cannot match lifecycle UX |
| C-02 | Export dialog contents | cannot match export UX |
| C-03 | Clip context menu | cannot match edit verbs/order |
| C-04 | Track options menu | cannot match per-track actions |
| C-05 | Library panel tabs + empty states | cannot match library UX |
| C-06 | Timeline metrics (ruler/lane/clip heights, zoom steps) | cannot match proportions |
| C-07 | Keyboard binding map | cannot match shortcuts |
| C-08 | Layout at 1280 / 1024 / 768 | cannot write responsive rules |
| C-09 | Loading / error / empty states of each panel | cannot match feedback |
| C-10 | Share/version dialogs | cannot match collaboration UX |

Method for each: open the surface in the signed-in tab, then read
`document.body.innerText` before/after and record the delta; for metrics use the
`getBoundingClientRect` probe; for keys, dispatch the candidate key and observe the
state change.

## 15. Build order (do not reorder without a reason)

1. **Deep link** `?project=` in the editor (unblocks the Studio home).
2. **Header + track panel geometry** per §2/§3.
3. **Prompt bar** position + placement-aware generation.
4. **Add-track** parity (Audio/MIDI/Upload + keys).
5. **Model picker** wired to `musicapi` + `pricing`.
6. **Hover help** system.
7. **Onboarding** overlay.
8. **Library panel** tabs.
9. **Project / export / clip / track menus** — only after C-01…C-05.
10. **Responsive** after C-08.

Each step: implement → typecheck → `check:ui` → manual run → update
`PROJECT_PROGRESS.md` → commit.

---

## 16. Feature areas discovered from shipped strings `B` (new — not yet in the inventory)

Mined from 9,679 strings across 134 chunks; 2,400 belong to studio chunks.
Full grouped lists: `reference/derived-features.md`.
These areas exist in the reference but were **absent from our inventory**. Add them
as rows (`ST-NEW-*`) before implementing.

| # | Area | Evidence strings | Our status |
|---|---|---|---|
| N-01 | **Time selection editing** — select a time range, then delete / duplicate / insert time across selected tracks | `Delete Time on Selected Tracks`, `Duplicate Time`, `Delete Time`, `Extend Selection Left/Right` | MISS |
| N-02 | **Take lanes** — stacked takes per clip/lane with preview | `take lanes (preview Take 1)`, `Take`, `Clip is not complete` | MISS |
| N-03 | **Master limiter** with lookahead control | `Master limiter lookahead (ms)`, `Master bus` | MISS |
| N-04 | **Realtime collaboration transport** (Ably) | `new Ably.Realtime()`, `new Ably.Rest()`, presence/cursor strings | MISS (we poll) |
| N-05 | **MIDI file export/download** | `Download MIDI`, `Download the selected MIDI clips as a MIDI file` | IMP |
| N-06 | **Bounce / render in place** | `Bounce`, `Exporting on track #`, `render mixdown` | MISS |
| N-07 | **Cover with original audio** variant | `Cover (With Original Audio)` | MISS |
| N-08 | **Focused-track mute commands** | `Mute Focused Track`, `Mute Focused Main Track`, `Mute All Hidden Tracks` | MISS |
| N-09 | **Loop variants** | `Loop selection`, `Loop boundary`, `Loop clip`, `Loop a section while you work` | partial |
| N-10 | **Clip gain vs. audio-arrangement rule** | `Clip gain only applies to audio arrangements.`, `Fades only apply to audio arrangements.` | MISS (we allow everywhere) |
| N-11 | **Strict edit-operation conflicts** | `Extend cannot be combined with other operations`, `Duplicate one arrangement at a time` | MISS |
| N-12 | **Copyright / policy gate with specific copy** | `Copyright infringement detected`, `Lyrics likely contain copyrighted material`, `Lyrics 2.0 M1 cowriter drafts.` | partial |
| N-13 | **Error taxonomy** — 827 distinct error/validation strings | see `derived-features.md` | partial (we have generic messages) |

### Why N-01/N-02/N-03 matter most

They change the interaction model, not just the feature list:

- **Time selection** introduces a second selection type (range vs. clip) with its own
  editing verbs. Our current editor has clip selection only.
- **Take lanes** change the clip model: a clip is not one audio source but a stack
  with an active take — this affects playback, export and persistence.
- **Master limiter lookahead** means mastering is part of the product surface, not a
  hidden implementation detail.

Implementing on top of the current clip model without these would force a rewrite
later. Decide the clip/take model **before** building further clip features.

### Error copy is a spec, not boilerplate

827 distinct error/validation strings is the reference telling us its edge cases.
Mine them into `SUNO_STUDIO_INTERACTION_SPECIFICATION.md` §6 rather than inventing
our own failure text.

---

## 17. Captured control surface — live aria-label map `L` (2026-10-30, Run 4)

Enumerated from the signed-in Studio. These are the app's own accessible names, i.e.
the authoritative control list. Use them as our `aria-label` values so behaviour and
accessibility stay aligned.

### 17.1 Global / header
`Suno logo` · `Project menu` · `Undo` · `Redo` · `Back to Start` · `Record` · `Play` ·
`Export menu` · `Collapse tracks` · `Collapse controls`

### 17.2 Track row
`Change track color` · `Collapse Track` · `Add new track` · `Mute main` ·
`Remove Soft Piano` *(per-instrument remove, name interpolated)*

### 17.3 Prompt bar (**internally "Magic Bar"**)
`Magic Bar prompt` · `Ask Studio` · `Add to prompt` · `Open conversation` ·
`Collapse` · `Model` · `Send`

### 17.4 Per-track panels
`Plugins` · `Automation` · `Clip editor` · `Take lanes` · `Add effect`

### 17.5 Keyboard & zoom
`Playable keyboard` · `Zoom out` · `Fit to content` · `Zoom in`

### 17.6 Global chrome
`Learn menu` · `Go back` · `Search` · `Liked only` · `Like` · `More` ·
`Bottom notifications` · `Top notifications` · `Bottom edge notifications`

> **Naming consequence:** our UI calls it "Studio AI". The reference calls it the
> **Magic Bar**. Match the label if we are cloning 1:1.

## 18. Captured menus `L`

### 18.1 Project menu ✅

```
New Project
Open Project
Rename
Duplicate Project
Version History
Share Project
Open a copy in v1 Studio
Settings                ctrl shift ,
Show Quick Start again
```

Notes: `Settings` carries the accelerator `ctrl shift ,`. There is a **v1 Studio**
escape hatch — the current editor is v2, and projects keep a v1-compatible copy.
`Show Quick Start again` re-opens the onboarding overlay (§10).

### 18.2 Export menu ✅

```
Full Song
Selected Time Range
Multitrack
```

Three export scopes. `Selected Time Range` implies a time-selection mode exists
(corroborates ST-NEW-01). `Multitrack` implies stem/per-track export.

### 18.3 Add track menu ✅

```
Add a track
  Audio    A
  MIDI     M
  Upload   U
```

## 19. Library = workspaces `L`

The library panel is **workspace-scoped**, not a flat song list:

| Entry | Detail |
|---|---|
| `New workspace` | create |
| `My Workspace` | `902 songs` |
| `BDBT50` | `42 songs` |
| `BDBT-16-May` | `67 songs` |
| `BVBR19-May` | `20 songs` |

Plus panel tools: `Search`, `Liked only`, `Like`, `More`.

Implication: our current "songs / liked tabs" model is wrong. The reference organises
a user's material into **workspaces**, each with its own song count, and the DAW
draws from the active workspace.

## 20. Instrument/plugin model `L`

- A track can host an instrument shown by name (`Soft Piano`) with a remove control.
- Per-track sections are `Plugins`, `Automation`, `Clip editor`, `Take lanes`.
- `Add effect` opens an effect picker.

So a track is: instrument → plugins/effects → automation → clip editor → take lanes.

## 21. Shortcuts discovered `L`

| Keys | Action | Evidence |
|---|---|---|
| `ctrl shift ,` | Settings | project menu |
| `A` / `M` / `U` | Add audio / MIDI / upload | add-track menu |
| `Space` · `Escape` · `Enter` · arrows · `Home`/`End` · `Delete`/`Backspace` · `Tab` | present in bundle | `B` |

## 22. Studio Settings `L`

Opened with `ctrl shift ,` (or Project menu → Settings). Sections observed:

```
Studio Settings
  Performance
  Window management
  Content
```

Captured setting (verbatim):

> **Ghost drag for arrangement moves** — "On, a move holds DSP applies for the whole
> gesture: audio keeps playing the pre-drag arrangement and one apply lands at drop.
> Off, move frames stream to the engine live. Read at gesture start."

Implications for our engine:

1. Dragging a clip must **not** re-schedule audio per frame. Hold the DSP graph and
   apply once on drop. Our current implementation re-schedules continuously.
2. The setting is read **at gesture start**, not per frame — a mid-drag change must
   not alter behaviour.
3. Sections `Window management` and `Content` exist but were not expanded in this
   run (capture pending, C-11).

## 23. Version History & Share — `?`

Both are reachable from the Project menu but did not render as `role="dialog"` within
the capture window. They may open a route, a side panel, or a portal without the
dialog role. Capture pending (C-10). **Do not implement their contents from
assumption.**

## 24. Share dialog `L` (captured verbatim)

Header shows the project name and relative age (`Drum & Bass Demo` · `5d, 3h ago`).

> **Share "Drum & Bass Demo"**
> Anyone with the link can view this project and create their own editable copy.
> Your original project will remain unchanged — others can't edit or affect your version.

Actions: `Done`, `Copy Link`.

Semantics: the share link is **view + fork**, never live co-editing. Anyone opening
it gets their own editable copy; the owner's project is untouched. Our implementation
must not imply real-time collaboration on a share link.

## 25. Version History panel `L`

Not a modal — a **left side panel, 300 px wide, full height** (x 8, y 8, 1229 px tall).

```
History                                    ×
Projects are saved automatically

10/30/2026
  10:00 PM
  10:19:16 PM
  10:19:05 PM
  10:18:32 PM
```

Facts:

1. Versions are automatic — the panel states it outright. There is no "Save" verb.
2. Entries are timestamped to the second and grouped under a date heading.
3. Saves cluster within seconds of each other (10:18:32 → 10:19:05 → 10:19:16),
   i.e. an autosave cadence of a few seconds, not one version per editing session.
4. The panel opens from Project menu → `Version History` and is dismissable with `×`.

## 26. Loaded project facts `L`

Demo project `Drum & Bass Demo`: **174 BPM**, `4/4`, tracks `Electric Keyboards`
(1) and `Soft Piano` (2). With audio loaded, the Magic Bar placeholder changes from
the empty-project hint to a contextual suggestion:

> "Add a warm reverb to this track"

So the placeholder is **context-sensitive**, not static: empty project → "Select a
spot on the timeline…"; populated project → a suggested action for the selection.

## 27. Revised capture status

| # | Surface | State |
|---|---|---|
| C-01 | Project menu | ✅ captured (§18.1) |
| C-02 | Export menu | ✅ captured (§18.2) |
| C-03 | Clip context menu | ⬜ not captured — clips are not plain DOM nodes; needs pointer click on a snapshot ref |
| C-04 | Track options menu | ⬜ not captured |
| C-05 | Library workspaces | ✅ list captured; per-workspace view ⬜ |
| C-06 | Timeline metrics | ⬜ clip/lane geometry still unknown |
| C-07 | Keyboard map | 🟡 partial (`ctrl shift ,`, `A`, `M`, `U`) |
| C-08 | Responsive layouts | ⬜ blocked (no viewport resize) |
| C-09 | Loading/error/empty states | 🟡 empty + onboarding captured |
| C-10 | Settings / History / Share | ✅ all three captured (§22, §24, §25) |
| C-11 | Settings sub-sections | ⬜ Window management, Content not expanded |

## 28. Rendering architecture `L` — the timeline is a canvas

Measured: **one `<canvas>` 1942 × 1141 at (8, 52)** covers the arrangement area.
Track rows are DOM: **260 px wide, 85 px tall, 86 px step** (rows at y = −118, −32
relative to the scrolled viewport).

Consequences for a 1:1 clone — this is the most important structural finding so far:

1. **Clips, waveforms, grid and playhead are drawn, not DOM.** Our editor builds
   clips as DOM nodes. Visual parity is achievable in DOM, but performance parity
   (hundreds of clips) is not. Decide: canvas renderer (match) or DOM + virtualisation
   (diverge, cheaper).
2. **Hit-testing is manual.** Their context menus come from canvas coordinates, which
   is why programmatic DOM right-click never opened a clip menu (C-03). Capture must
   use real pointer coordinates over the canvas, then read the floating menu.
3. **Accessibility must be layered.** A canvas arrangement needs an offscreen
   semantic mirror for screen readers; the reference exposes `aria-label`s for
   controls but the timeline itself is opaque.
4. **Drag-and-drop is internal.** `data-studio-nested-drop-target` markers confirm a
   custom DnD layer rather than HTML5 drag events.

Track-row geometry to match: `85 px` row height, `260 px` header column, `86 px` step.

## 29. Studio Settings → Content `L`

Captured copy (partial, verbatim):

> "…uploaded at the same time) keep their original timing. Off: added audio always
> keeps its original timing and does not set the project tempo. Generated clips are
> not affected."
>
> **Advanced content features** — "Sound-design tools like the Wavetable Designer and
> Impulse Response Designer. Off, the menu items that open them are hidden."

Two behaviours to implement:

1. **Tempo detection on import.** There is a setting governing whether added audio
   can set the project tempo. Generated clips are explicitly exempt. Our importer
   currently never touches tempo.
2. **Advanced content features are gated.** `Wavetable Designer` and
   `Impulse Response Designer` are real product surfaces behind a setting. When off,
   their menu entries are hidden — not disabled. Match that pattern.

## 30. New feature areas (add to inventory)

| # | Area | Evidence | Ours |
|---|---|---|---|
| N-14 | **Wavetable Designer** — design your own synth wavetables | settings + marketing "Plugins you can design yourself" | MISS |
| N-15 | **Impulse Response Designer** — design your own reverb IRs | same | MISS |
| N-16 | Tempo detection / import timing policy | Content setting copy | MISS |
| N-17 | Feature-gated menu items (hidden, not disabled) | Content setting copy | MISS |

> N-14/N-15 are the "plugins you can design yourself" pillar from the landing page.
> They are a differentiator, not a side feature. Scope them before promising "1:1".

## 31. Clip context menu `L` (captured verbatim)

Right-click over a clip in the canvas:

```
Copy            ctrl C
Paste           ctrl V
Duplicate       ctrl D
Delete          backspace
Heal Edits
Split           ctrl E
Rename
Clip Info
Clip Color
Get Stems
Download .WAV
Get MIDI
Remove FX
```

### What this proves

| Observation | Implication |
|---|---|
| Accelerators are printed in the menu | these are real bindings, not hints |
| `Heal Edits` | a clip keeps a stack of applied edits (crop/fade/speed/reverse) that can be collapsed/reverted. We currently bake edits destructively. |
| `Remove FX` | clips carry their own effect chain, separate from track plugins |
| `Get MIDI` (per clip) | audio→MIDI transcription exists per clip |
| `Get Stems` | stems are a clip action, not a track action |
| `Clip Info` | a per-clip metadata panel distinct from the inspector |
| `Download .WAV` (per clip) | per-clip export without rendering the project |

Menu order matters for muscle memory: clipboard → edit history → split → identity/appearance → extraction (stems/MIDI) → export → destructives.

## 32. Keyboard map (updated) `L`

| Keys | Action | Evidence |
|---|---|---|
| `ctrl C` / `ctrl V` | copy / paste clip | clip menu |
| `ctrl D` | duplicate clip | clip menu |
| `ctrl E` | split at playhead | clip menu |
| `Backspace` | delete clip | clip menu |
| `ctrl shift ,` | Studio Settings | project menu |
| `A` / `M` / `U` | add audio / MIDI / upload track | add-track menu |

Still unmapped: `Space`, `Delete`, arrows, `Home`/`End`, `?`, undo/redo, loop, metronome.

## 33. Clip edit stack — `Heal Edits`

A clip is **not** a pointer into an audio file with baked transforms. It carries an
ordered edit chain (crop → fade → speed → reverse, per the API surface) that can be
healed. To clone this faithfully the clip model needs:

```
clip {
  source_id
  edits: [ {type: "crop", ...}, {type: "fade", ...}, {type: "speed", ...} ]
  takes: [ ... ]          // see N-02
  fx:    [ ... ]          // "Remove FX"
}
```

`Heal Edits` collapses the chain back to the source. Without this model, per-clip
"heal" is impossible to implement later without a migration.

## 34. Clip-level FX

`Remove FX` in the clip menu means effects can be attached to a clip independently of
its track. Our FX chain is track-only. Add a clip-level insert point in the audio
graph (clip → clip FX → clip gain/fade → track chain).

## 35. Coverage ledger — what an implementer can rely on

Use this as the checklist. Anything **not** in the "captured" column must be captured
before code is written.

### Captured (implementation-ready)

| Area | Spec | Confidence |
|---|---|---|
| Colour tokens, spacing, base frame | §1 | measured |
| Header: 15 controls, positions, sizes, grouping | §2 | measured |
| Track panel: 11 elements, 260 px, 85 px rows | §3, §28 | measured |
| Timeline: canvas renderer, canvas rect, row metrics | §28 | measured |
| Prompt / Magic Bar: 8 controls, geometry, context-sensitive placeholder | §5, §26 | measured + observed |
| Model catalog: 4 entries + credit cost | §6 | observed |
| Footer: master, mute, Learn, What's This? | §7 | measured |
| Project menu: 9 items + `ctrl shift ,` | §18.1 | observed |
| Export menu: 3 scopes | §18.2 | observed |
| Add-track menu: 3 types + accelerators | §18.3 | observed |
| Clip context menu: 13 items + accelerators | §31 | observed |
| Clip model: edits chain, takes, clip FX | §33, §34 | observed |
| Settings: Performance + Content (incl. plugin designers, tempo policy) | §22, §29 | observed |
| Share: copy + view/fork semantics | §24 | observed |
| Version history: 300 px panel, autosave cadence | §25 | measured |
| Library: workspace model + counts | §19 | observed |
| Track stack: instrument → plugins → automation → clip editor → takes | §20 | observed |
| Control names (38 aria-labels) | §17 | measured |
| Keyboard: 7 bindings confirmed | §32 | observed |
| Reference API: 322 endpoints / 81 studio | §12 | bundle |
| Feature areas beyond ours (N-01…N-17) | §16, §30 | bundle strings |

### Not captured (do not implement from assumption)

| # | Gap | Why it is still open |
|---|---|---|
| C-04 | Track options menu | right-click on the header returns the clip menu; trigger unclear |
| C-05 | Per-workspace library view | clicking a workspace did not change the panel |
| C-06 | Ruler height, zoom steps, loop-bracket geometry | not measured |
| C-07 | `Space`, arrows, `Home/End`, `?`, undo/redo, loop, metronome | not tested |
| C-08 | Layout at 1280 / 1024 / 768 | viewport cannot be resized from the automation surface |
| C-11 | Settings → Window management | section did not change the panel text |
| C-12 | Clip Info panel | menu item exists, panel not opened |
| C-13 | Stems / Get MIDI result surfaces | paid actions, not exercised |
| C-14 | Loading, error and empty states per panel | only empty-project and onboarding seen |
| C-15 | `Learn` tour contents | not opened |

### Consequence for planning

Eleven of the fifteen open items are **read-only observations** — no product decision
blocks them. Only three require your call:

1. **Render the arrangement on canvas** (match performance and hit-testing) or keep
   DOM clips (cheaper, diverges).
2. **Adopt the full clip model** — `edits[] + takes[] + fx[]` — now, or ship
   single-source clips and schedule a migration.
3. **Wavetable Designer / Impulse Response Designer** — in scope or explicitly cut.

Everything else can proceed against this spec today.

## 36. Complete keyboard map `L` — the authoritative shortcut overlay

Captured by pressing `shift ?` (the app has a built-in "Keyboard Shortcuts" overlay).
This closes C-07 completely.

### General

| Action | Keys |
|---|---|
| Play / Pause | `SPACE` |
| Play from selection start | `ALT SPACE` |
| Ask Studio | `ENTER` |
| Dismiss | `ESC` |
| Toggle arrangement mute | `0` |
| Move tracks up / down | `CTRL ↑` / `CTRL ↓` |
| Delete | `BACKSPACE` / `DEL` |
| Toggle metronome | `SHIFT C` |
| Toggle arrangement panel | `SHIFT L` |
| Toggle recording | `SHIFT R` |
| Add track | `SHIFT T` |
| Toggle loop | `CTRL L` |
| Rename focused track | `F2` |
| Studio settings | `CTRL SHIFT ,` (also `CTRL SHIFT <`, `CTRL ,`) |
| Toggle keyboard | `CTRL K` |
| **Save project** | `CTRL S` |
| Toggle fade | `SHIFT F` |
| Copy / Cut / Paste / Duplicate | `CTRL C` / `CTRL X` / `CTRL V` / `CTRL D` |
| Undo / Redo | `CTRL Z` / `CTRL SHIFT Z`, `CTRL Y` |
| Solo / mute focused main track | `SHIFT S` / `SHIFT M` |
| Hide selected tracks / show all hidden | `SHIFT H` / `SHIFT ALT H` |
| Toggle chat / bottom / lanes / library panels | `1` / `2` / `3` / `4` |
| Swap bottom panels | `SHIFT TAB` |
| Toggle automation panel | `SHIFT A` |
| Zoom in / out timeline | `CTRL =` / `CTRL -` |
| Double / halve grid density | `SHIFT 1` / `SHIFT 2` |
| Keyboard shortcuts | `SHIFT ?` or `SHIFT /` |

### Timeline

`CTRL A` select all · `CTRL E` split · `CTRL SHIFT D` duplicate time ·
`CTRL SHIFT BACKSPACE` delete time · `CTRL BACKSPACE` delete time on selected tracks ·
`ENTER` promote take-lane selection · `←/→` move selection · `SHIFT ←/→` extend
selection · `↑/↓` focus track above/below · `ESC` dismiss.

### Tracks
`CTRL A` select all tracks · `↑/↓` focus · `←/→` move · `SHIFT ←/→` extend.

### Effects chain
`CTRL A` select all plugins · `ESC` clear selection.

### Clip editor — audio
`CTRL A` select all **warp markers** · `SHIFT Q` quantize warp markers ·
`SHIFT 1/2` grid density.

### Clip editor — MIDI
`CTRL A` select all notes · `SHIFT Q` quantize notes · `0` toggle notes disabled ·
`CTRL =/-` zoom · `Z` zoom to selection · `SHIFT 1/2` grid density ·
`←/→` move · `↑/↓` semitone · `SHIFT ←/→` shorten/lengthen · `SHIFT ↑/↓` octave.

### Automation lanes
CC lane: `←/→` nudge points · `↑/↓` increase/decrease value.
Velocity lane: `←/→` move notes · `↑/↓` velocity.

### Playable keyboard
`A – ;` play notes · `Z`/`X` octave down/up · `C`/`V` velocity down/up.

### Library panel
`↓` audition next · `↑` audition previous · `→` replay selected.

## 37. What the shortcut map proves

| Finding | Implication |
|---|---|
| **`CTRL S` "Save Project"** | a manual save exists alongside autosave — our "no save button" assumption was wrong |
| **Warp markers + quantize** | audio time-warping with editable markers is a first-class clip-editor feature |
| **Take-lane promotion (`ENTER`)** | takes are selected then promoted — confirms the take-lane model |
| **`DELETE TIME` / `DUPLICATE TIME` on selected tracks** | destructive/rippling time edits are core, not optional |
| **Hidden tracks (`SHIFT H`, `SHIFT ALT H`)** | tracks have a hidden state separate from mute |
| **Four panels: chat, bottom, lanes, library** | the workspace is a 4-panel layout, not the 3 we modelled |
| **Velocity + CC automation lanes** | MIDI isn't just notes; it has per-lane CC/velocity editing |
| **Playable keyboard with velocity** | `C`/`V` velocity mapping we don't have |

## 38. Learn menu `L`

```
Keyboard Shortcuts   shift ?
YouTube Tutorials
Learning Center
What's This?   On
```

`What's This?` is a **toggle** here, matching §7.

## 39. Settings → Window management `L`

> **Keyboard & plugin windows** — "Docked, with a Pop out control on each surface's
> header. Popping one out is remembered for next time."
> **Panels** — "Windows Show toggle…"

So instrument/plugin surfaces can be **docked or popped out into separate windows**,
and the choice persists per surface. Match this for the playable keyboard and plugin
editors.

## 40. Panel widths and canvas behaviour `L`

| State | Canvas width |
|---|---|
| Library closed | 1942 px (x 8 → 1950) |
| Library open | **1574 px** (x 8 → 1582) |

So the library panel occupies **≈368 px** and the arrangement canvas **shrinks**
rather than being overlaid. The canvas is also the ruler: `00:15`-style bar labels
are **not DOM nodes**, so ruler height, tick spacing and zoom steps cannot be read
from the accessibility tree — they need pixel analysis of a screenshot.

### Practical consequence for capture

C-06 (ruler/zoom metrics) is only obtainable from screenshots:

1. Take a screenshot at each zoom level.
2. Measure the pixel distance between bar labels and the ruler band height.
3. Convert to musical units using the known BPM and time signature.

Until that is done, implement zoom as a multiplier of pixels-per-beat with our own
steps and mark the value **unverified**.

## 41. Reference project structure `L`

The `Drum & Bass Demo` project contains **17 tracks**, which shows how a real
arrangement is organised and how granular the track model is expected to be:

```
1  Electric Keyboards      10 Held String
2  Soft Piano              11 Sound Effects Alarm
3  Brass Section           12 Sound Effects Crash
4  Vocal Cuts              13 Drum Kit Main
5  Long Vocal              14 Drum Kit Tops
6  Bass Line               15 Drum Kit Fills
7  Bass Answer             16 Hats
8  Bass 2                  17 Xtra Snare
9  String Build up
```

Observations:

1. **One instrument per track** — no compound "band" tracks. Our track model must
   stay single-instrument.
2. **Section-level vocal tracks** (`Vocal Cuts`, `Long Vocal`) — vocals are split by
   role, not one vocal bus.
3. **Layered drums** (Main / Tops / Fills / Hats / Xtra Snare) — the reference expects
   users to have 5+ drum tracks; the UI must stay usable at 17+ tracks.
4. **SFX as tracks** (`Alarm`, `Crash`) — effects are arrangement elements, not a
   separate pool.

Design consequence: the track panel must remain legible at 20 tracks without
scrolling friction — row height 85 px gives ~12 visible rows at 1080p, so **track
collapse/filter and the `SHIFT H` hide-tracks command are load-bearing**, not extras.

## 42. Plugins panel `L`

Opening `Plugins` on a track shows an **effects chain** with a plugin card:

```
Compressor            [Custom ▾]   [None ▾]
Thresh   Ratio   Knee   Atk   Rel   Gain
```

Facts:

1. Plugins are **cards inside a chain**, not a flat list — the chain is ordered (hence
   `CTRL A` "select all plugins", `ESC` clear selection).
2. Each card has a **preset selector** (`Custom` / named preset) and a **preset slot**
   (`None`).
3. The compressor exposes six parameters: `Thresh · Ratio · Knee · Atk · Rel · Gain`.
4. `Automation` and `Plugins` share the same panel region (switching tabs), and
   `Take lanes` opens empty until a take lane exists (amber: not an error).

This closes H1 (structure) and part of I3 (chain behaviour).

## 43. Capture remainder after Run 5

Still open and requiring the pixel pass or approval:

- E1–E3 ruler/lane/zoom geometry (canvas — pixels only)
- F2–F9 clip sub-surfaces (trim handles, fades, warp, takes, heal, clip FX, Clip Info)
- G3 conversation panel, G5 generation result
- H2/H4 automation + MIDI editor detail, H5 take lanes with content
- I1/I2 master + track strips
- J2 per-workspace library view, J5 uploads/stems tabs
- K2 version entry actions, K4 v1 Studio copy
- L2/L3 export dialog + multitrack output
- M1–M3 stems/MIDI/persona (paid)
- N4 remaining settings
- P2/P3 comments/presence (second session)
- Q1/Q3–Q5 loading/error/offline/credits states
- R1 responsive widths (no resize control)

---

## 44. Visual capture — full editor screenshot `L` (Drum & Bass Demo, 174 BPM)

Read from a full-window screenshot (1958×1245). Positions are approximate (±4 px) and
are here to settle structure and order, not to replace DOM measurement.

### 44.1 Header, left → right

```
[SUNO]  [Drum & Bass Demo ⌄]   ↶ ↷   |◀  ◀◀  ■  ▶   +   00:30.345   023.1.1      ...   174 BPM  4/4   [⬆ Export]  [▤ Library]
```

- Project **chip** (name + chevron) sits left, not a bare title.
- Undo/redo are immediately after the chip.
- Transport cluster is centred: back-to-start, rewind, stop, play, forward, plus.
- Then **two** readouts: time `00:30.345` and bar.beat `023.1.1` (three-decimal time,
  three-field bar.beat).
- Right cluster: `174 BPM`, `4/4`, `Export` (with icon), `Library` (with icon).

### 44.2 Project menu (open)

Anchored under the project chip, ~220 px wide, icon + label per row, accelerator
right-aligned on the settings row:

| Icon | Item |
|---|---|
| ＋ | New Project |
| ▤ | Open Project |
| ✎ | Rename |
| ⧉ | Duplicate Project |
| ◷ | Version History |
| ↗ | Share Project |
| ⇱ | Open a copy in v1 |
| ⚙ | Studio Settings  · `ctrl shift ,` |
| ✦ | Show Quick Start again |

### 44.3 Two rulers

- **Top**: bar numbers `1 · 9 · 17 · 25 · 33 … 137` (every 8 bars).
- **Bottom**: time `00:00 · 00:30 · 01:00 … 03:00` (every 30 s).

Both are visible simultaneously — bars for musical work, time for audio work. Our
editor has one ruler; the reference has two.

### 44.4 Track rows

```
[#]  [──────── level bar ────────]  [S] [A] [⌄] [◉]
```

- Track number in the gutter (`1`, `7`, `8`, `9`, `10`, `11`…).
- A wide horizontal **level/volume bar** with a vertical handle (not a fader knob).
- `S` (solo) and `A` (arm) as small square buttons; a chevron and a round button at
  the right edge (row extend / options).
- Rows are colour-coded by a thin left strip matching the clip colour.

### 44.5 Track colours (semantic families)

| Family | Colour |
|---|---|
| Vocals | magenta / pink (`Vocal Cuts`, `Long Vocal`) |
| Bass | blue (`Bass Answer`, `Bass 2`) |
| Strings / keys | violet (`String Build up`, `Held String`) |
| SFX | orange (`Sound Effects Alarm`, `Sound Effects Crash`) |
| Drums | olive / yellow (`Drum Kit Main`, `Drum Kit Tops`) |

Consequence: colour is **assigned per instrument family**, not per track index. Our
palette cycles by index; theirs is semantic.

### 44.6 Clips

- Rounded rectangles, colour = track family, **darker header band** with the clip
  name, waveform below.
- Selected clip gets a **white 2 px border** (`Vocal Cuts`).
- Names truncate with an ellipsis (`Vo…`, `Str…`, `So…`, `Dru…`), so the label must be
  legible at very small widths.
- Clips are not aligned to a single track height — inline take lanes/overlaps appear
  as stacked rows inside a track (see the drum tracks).

### 44.7 Bottom tool row

```
[⚙ tools] [✏ pencil] [☰]        ●  Delay  Compressor  +          [⧉] [⌕] [⤢] [⤢] [⟲]        [Learn]
```

- Left: tool cluster (sliders, pencil, list).
- Centre: the **FX chain chips** for the selected track (`Delay`, `Compressor`) with a
  `+` to add — this is the same chain as the Plugins panel, surfaced inline.
- Right: duplicates/search/zoom-out/zoom-in/loop-ish icons, then `Learn`.
- Bottom-left: `Main` bus with level bar and speaker (mute).

### 44.8 Overlays

- **Tooltip**: "Press play to hear the demo" anchored near the playhead.
- **What's This?** card bottom-right: "Hover over any control to see how it works.
  Click Learn to turn What's This? off." + `Dismiss` / `Turn off`.
- **Playhead**: thin vertical line with a small blue triangle marker on the bar ruler.
- **Project end**: a vertical boundary line at the right of the last clip.

### 44.9 Corrections to earlier notes

| Earlier | Corrected |
|---|---|
| "Track name 11 px, name + M/S/A" | the wide element is a **level bar**, not the name field; name is in the clip band and gutter |
| "One ruler" | **two rulers**: bars on top, time at the bottom |
| "Palette cycles per track" | palette is **semantic per instrument family** |
| "Export/Library at far right with BPM" | BPM and signature sit in a separate right cluster before Export/Library |

## 45. Icon and text inventory — editor view `L`

Measured on the loaded demo project:

| Metric | Value |
|---|---|
| SVG elements rendered | 147 |
| Distinct SVG glyphs | **52** |
| Distinct accessible names | 36 |
| Distinct visible text nodes | 65 |

The 36 accessible names are listed in §17. The notable additions since then:
`Remove Vocal Cuts` (per-clip remove, name interpolated), `Bottom notifications`,
`Top notifications`, `Bottom edge notifications` (three separate notification
surfaces), `Fit to content` (a zoom mode between in/out).

**Gap:** the 52 SVG glyphs have no names. Capturing "all icons" means a glyph→name map,
which requires a screenshot per icon or an icon-font/CSS audit. Until that exists we
cannot guarantee icon parity — only icon *placement* parity.

## 46. Narrow-viewport editor `L` (≈706 px window)

Captured from a narrow window. This is the first real responsive evidence (C-08 partial).

### What changes at narrow width

| Region | Behaviour |
|---|---|
| Header | collapses to `SUNO · [project chip] · ⋯ · undo/redo`. **Transport, BPM, signature, Export and Library disappear entirely** — no wrapping, no scroll. |
| Track panel | stays visible at ~285 px (≈40% of viewport); timeline keeps the rest |
| Timeline | scrolls horizontally; ruler shows every 8th bar (`1 · 9 · 17 · 33`) |
| Bottom bar | tools collapse to four icon buttons |

Rule: below ~900 px the transport is **not** rendered, not merely shrunk. Any clone
must implement that state explicitly rather than relying on flex-wrap.

### Track row at narrow width (corrected anatomy)

```
[#] [name]                    [🔊] [S] [A] [⌄]
    [ colour-gradient bar ][── fader ──][── fader ──]
```

Two horizontal sliders per row plus a **gradient bar tinted with the track colour**
(pink for vocals, violet for strings, olive for drums). The gradient is not a waveform
— it is a level/spectrum-style meter. This supersedes the single "level bar" reading
in §44.4: the row carries **two controls + one colour meter**.

### Ruler markers

Blue triangular flags sit on the bar ruler (x ≈ 549 and 645 in this window) —
these are **section markers**, distinct from the playhead (white line + round handle).
Our editor draws markers as text chips; the reference uses flags on the ruler.

### Playhead

White 1 px line with a circular handle on the ruler, spanning the full arrangement
height, drawn above clips.

## 47. Clip menu — two captured variants (it is state-dependent)

Variant A (DOM sweep, §31) and Variant B (screenshot) differ. This proves the clip menu
is **generated from clip state**, not a fixed list.

| Item | A | B | Note |
|---|---|---|---|
| Copy `ctrl C` | ✓ | ✓ | |
| Paste `ctrl V` | ✓ | ✓ | |
| Duplicate `ctrl D` | ✓ | ✓ | |
| Delete `backspace` | ✓ | — | shown when a deletable clip is focused |
| **Heal Edits** | ✓ | — | only when the clip has a non-empty edit chain |
| Split `ctrl E` | ✓ | ✓ | |
| **Create Section** | — | ✓ | **new** — stamps a section marker from the clip |
| Rename | ✓ | ✓ | |
| Clip Info | ✓ | ✓ | |
| Clip Color | ✓ | ✓ ▸ | **has a submenu** (colour swatches) |
| Get Stems | ✓ | ✓ | |
| Download .WAV | ✓ | … | below the fold in B |
| Get MIDI | ✓ | … | below the fold in B |
| Remove FX | ✓ | … | below the fold in B |

### Layout facts from B
- ~180 px wide, dark surface (`#2b2b2e`-family), 8 px radius, soft shadow.
- Each row: **icon + label + right-aligned accelerator**.
- **Dividers group the menu**: clipboard → edit → identity → extraction.
- Submenu arrow (`▸`) on `Clip Color`.

### Rule for our implementation

Build the menu from clip state:

```
canPaste      → Paste
clip.edits>0  → Heal Edits
isAudio       → Download .WAV, Get MIDI
clip.fx>0     → Remove FX
supportsSection → Create Section
```

Never hardcode the list — the reference already varies it between two ordinary clips.

## 48. "Add a track plugin" dialog `L`

Modal, ~760 px wide, dark surface, rounded. Structure:

```
Add a track plugin                    [🔍 Search plugins]  [⋯] [×]
MY PLUGINS
  ┌ ─ ─ ─ ─ ─ ─ ─ ┐
  │      ＋        │   Create new plugin
  └ ─ ─ ─ ─ ─ ─ ─ ┘
AUDIO EFFECTS
  [card] [card] [card]
  [card] [card] [card]
```

Card anatomy (grid, 3 per row): **mini preview graphic** (curve or knobs) with a small
preset chip, then **name + ○ Learn**, then a two-line description.

### Built-in audio effects (captured names + descriptions)

| Plugin | Description (verbatim, truncated) |
|---|---|
| Compressor | "Classic dynamics compressor: threshold, ratio, and knee set how hard peaks are…" |
| Convolution | "Places the signal in a sampled real space: load an impulse response, then shape it…" |
| Delay | "Echo with feedback and mix, free-running in milliseconds or synced to the beat, wi…" |
| Distortion | "A comprehensive distortion / waveshaper: drive into a pre-tilt tone stage, six…" |
| EQ | "Multi-band parametric EQ: per-band frequency, gain, Q and filter type on an…" |
| Gate | "Noise gate: silences the signal below the threshold, with floor, attack, hold, and…" |
| Limiter | "Brickwall lookahead limiter: drives the signal into a fixed ceiling with lookahead…" |
| Reverb | "Algorithmic reverb with time, mix, width, damping, predelay, and low/high cut…" |

Preview parameters visible on the cards:

- Compressor: Threshold · Ratio · Knee · Attack · Release
- Distortion: Tilt · Bass · Freq · Drive, with modes **Hard · Fold · Align · Sine · Crush**
- EQ: per-band chip (`Band 2`) + Freq
- Gate: Threshold · Floor · Attack · Hold
- Limiter: Lookahead · Pre Gain · Attack · Release
- Reverb: Low Cut · High Cut · Decay · Damping · Predelay
- Delay: Time · Feedback · Mix
- Convolution: impulse-response slot (`IR: WEIRD VINTAGE CONVOLVER`) + Mix

**"Create new plugin"** is the entry point to user-designed plugins (the marketing
"plugins you can design yourself" pillar, related to N-14/N-15).

## 49. Plugin editor panel `L`

Docked panel (bottom), ~470 px wide:

```
● Delay            [Custom ▾]        [Update]  ×
[Time] [Tempo]                                   ← mode tabs
 ◯ Time    ◯ Feedback    ◯ Mix                    ← large knobs
                             ◯ Low Cut            ← small knobs
                             ◯ High Cut
```

Right side of the dock:

```
            [ + Add effect ]
[ EQ ]      [ Compressor ]      [ Reverb ]        ← remaining chain slots
```

Rules extracted:

1. **Preset selector + `Update`** — `Custom` means an unsaved tweak; `Update` writes it
   back to the selected preset.
2. **Mode tabs** (`Time` / `Tempo`) change the parameter semantics, not the plugin —
   delay can run in milliseconds or beat-synced.
3. **Two knob sizes**: primary parameters large, secondary (filters) small.
4. **Chain is a horizontal rail** of effect cards with an `Add effect` slot at the end.
5. The chain also appears as chips in the main footer (`Delay ＋`).

## 50. Multi-plugin chain dock `L` — several effects open at once

The chain is **not** a single-panel tab. Each plugin in the chain renders its own
editor panel side by side in a horizontally scrollable dock:

```
[● Delay   Custom  ▾   Update  ⤢ ×] [● Compressor Default ▾ ⤢ ×] [● Convolution Default ▾ ⤢ ×] [● EQ Default ▾ ⤢ ×]
   Time | Tempo                       curve + 6 knobs              IR slot + Mix/Pre/Width      band chips + Freq/Q/Gain
───────────────────────────────────────────────────────────────────────────────────────────────
        Delay   Compressor   Convolution   EQ   ＋            ← footer chain chips
```

Panel anatomy (every plugin): **colour dot · name · preset selector · popout (⤢) · close (×)`.
`Update` appears only when the preset is dirty (`Custom`), otherwise the preset name
(`Default`) is shown.

### Parameter sets captured

| Plugin | Controls |
|---|---|
| Delay | tabs `Time` / `Tempo`; Time · Feedback · Mix (large); Low Cut · High Cut (small) |
| Compressor | threshold curve; Thresh · Ratio · Knee · Atk · Rel · Gain (six small knobs) |
| Convolution | IR slot (`NO ASSET LOADED`); Mix · Pre · Width; time ruler 1 s / 2 s |
| EQ | band chip (`Band 2`); band row; Freq · Q · Gain; draggable curve points |

### Rules

1. **Unlimited chain length** — four plugins open simultaneously in the screenshot;
   the dock scrolls horizontally.
2. **"Add effect" lives at the end of the chain rail** and in the footer (`＋`).
3. **Popout (⤢)** on every plugin header — matches Settings → Window management
   ("Docked, with a Pop out control on each surface's header").
4. Chain order = signal order; the footer chips are the same ordered list.
5. A track can therefore be modelled as: `instrument → plugins[] → automation → clips`.

This supersedes the single-card reading in §42: that was one plugin in a chain, not the
whole chain UI.

## 51. Plugin system — decompiled facts `B`

Identifiers recovered from the 134 authenticated chunks (1,074 plugin-related strings;
the meaningful ones):

### Chain operations
`add_plugin` · `add_plugin_to_chain` · `chainPlugin` · `Clear Plugin Selection` ·
`Clear Plugin Selection` bound to `ESC` (see §36)

### Effects registry (ids)
`compressor` · `convolution` · `convolution-reverb` · `chorus` · `reverb` · `delay` ·
`distortion` · `gate` · `limiter` · `eq`

These match the eight catalog cards captured in §48, plus `chorus`, which has no card
in the visible grid — so the catalog is longer than one screen.

### Authoring
`authored-plugin` · `author_plugin` · `Creating Plugins` · `A custom plugin.` ·
`Saved to My Plugins.` · `Saved to My Plugins as a new version.` ·
`Could not resolve the plugin instance` · `missing required function` ·
`blocked_broken_plugins`

Implications:

1. **User plugins are versioned artefacts** — saving produces a *new version*, not an
   edit in place. Our model needs `plugin_versions(plugin_id, version, definition)`.
2. **A plugin is code**, not a parameter preset: `missing required function` and
   `Could not resolve the plugin instance` are runtime errors from executing authored
   plugin bodies, and `blocked_broken_plugins` is a safety gate that can disable one.
3. **Presets are exported in bulk** (`Bulk-export presets`, `bulk-preset-export-assets`)
   — presets are portable assets, not rows on a plugin.

### Library filters that exist but we never modelled
`filterCovers` · `filterDislikedClips` · `filterDownloadedClips` · `filterExtensions` ·
`filterFullSongs` · `filterLikedClips` · `filterPrivateClips` · `filterPublicClips` ·
`filterRemasters` · `filterUploadedClips`

That is ten clip filters — the library surface is far richer than the two tabs we have.

### Consequence

The plugin surface is a **sandboxed, versioned, user-programmable effect host**, not a
fixed list of knobs. Implementing it faithfully is a security and isolation problem
(sandbox + versioning + failure containment), not a UI task. Scope it deliberately.

## 52. Full editor with plugin dock open `L` (1272 px wide)

Measured from a full-window capture at 1272 px.

### Track rows (this is the final anatomy)

```
[#] [name]                          🔊  S  A  ⌄
    [──────── volume ────────|──][── pan ──|──]
```

- Number at far left, aligned with the colour strip.
- Name on the first line, left.
- `🔊 S A ⌄` right-aligned on the same line.
- **Two horizontal sliders** below: a wide volume slider and a narrower pan slider, each with a vertical handle. (Earlier notes said "one level bar" — it is two.)
- The selected row gets a lighter fill across the **full row width** (track 5 in the capture).
- A focused slider draws a **green outline** (track 2).
- Row height 85 px, step 86 px; `Main` bus at the bottom with the same slider pair.

### Plugin dock (open)

Full-width dock above the footer, horizontally scrollable, ~370 px tall:

| Slot | Header | Body |
|---|---|---|
| Delay | magenta dot · `Delay` · `Custom` ▾ · **Update** · × | tabs `Time`/`Tempo`; large knobs Time · Feedback · Mix; small knobs Low Cut · High Cut |
| Compressor | magenta dot · `Compressor` · `Default` ▾ · × | transfer curve with −40/−16 axis; preset `None`; small knobs Thresh · Ratio · Knee · Atk · Rel · Gain; bypass dot |
| Convolution | magenta dot · `Convolution` · `Default` ▾ · × | IR grid with `0s 1s 2s` ruler and `NO ASSET LOADED`; preset `None`; Mix knob |

Card width ≈ 480 px for Delay/Compressor, ≈ 370 px for Convolution. Cards are
separated by a 1 px divider, each with its own colour dot matching the plugin.

### Footer

`[⚙][✎][☰][🎤]` ······ `Delay  Compressor  Convolution  EQ  +` ······ `[▤][⌕][−][+][⟲]  Learn`

Tool cluster left, chain chips centred, view/zoom/loop + Learn right.

### Header (at 1272 px)

`SUNO · [Drum & Bass Demo ⌄] · ↶ ↷` — then centred `|◀ ◀ ■ ▶ ▶| ⊕ 00:00.000 001.1.1` — then right `174 BPM · 4/4 · ↗Export · ▤Library`.

Six transport glyphs before the readouts: back-to-start, rewind, stop, play, forward, plus.

### Deltas against our shell

| Element | Reference | Ours |
|---|---|---|
| Track sliders | two (volume + pan) | one level bar |
| Selected row | full-width lighter fill | purple tint |
| Focused slider | green outline | none |
| Plugin dock | present in the editor | not mounted in the shell |
| Footer | tools · chips · view controls · Learn | chips only |
| Transport glyphs | six | five |

## 53. Plugin dock — second capture (played state, EQ + Compressor)

Captured from my own screenshot at 1104 px with playback running (`02:05.589`,
bar `092.1.1`) on a selected drum track.

### Newly discovered capabilities

| Feature | Evidence |
|---|---|
| **Named presets** | header shows `Kick Comp` and `Band 5` — not just `Custom`/`Default` |
| **Sidechain source picker** | Compressor panel shows `Drum Kit Main — Pre-fx` |
| **EQ band shapes** | a row of five filter-shape icons + a band number chip |
| **Per-plugin bypass dot** | small circle at each card's top-right |
| **Focus ring on a knob** | the hovered/focused knob draws a green ring (`Freq`) |

### Card anatomy (final)

```
● <name>            <preset ▾>                    ●(bypass) ×
  [optional: sidechain / asset / band selector]
  <graph or knobs>
  Thresh  Ratio  Knee
  Atk     Rel    Gain
```

### Compressor

- Transfer curve with `−40` / `−16` axis labels.
- Preset `Kick Comp`.
- **Sidechain** selector reading `Drum Kit Main — Pre-fx`.
- Six knobs: Thresh · Ratio · Knee · Atk · Rel · Gain.
- Bypass dot top-right.

### EQ

- Preset `Band 5` plus a band chip.
- **Five filter-shape icons** (bell, shelf, notch, high/low pass shapes).
- Three knobs: Freq · Q · Gain.
- A draggable curve with numbered nodes (band index inside the node).
- Selecting a node (green node `5`) highlights its `Freq` knob with a green ring.

### Track selection correlation

Selecting track 13 dims the other lanes and outlines that track's clips, so the
selected track is identifiable in both the left bar **and** the arrangement.

### Deltas our dock still has

1. No named presets — we only show `Custom`/`Default`.
2. No sidechain picker on the compressor.
3. EQ shows one band, not a multi-band editor with shape selection.
4. No per-plugin bypass dot (we have a power button in the header instead).
5. Focus rings are on sliders only, not knobs.
