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

### 6.1 The picker, measured (S38)

Capture `screens/S38-model-picker.jpeg`, opened from the `v6 ▾` chip in the Magic
Bar.

| Property | Value |
|---|---|
| Panel | **246 × 305**, right edge aligned to the chip, opening **upward** from it (bottom at y = 1121, chip top at 1134) |
| Anchor | the `v6 ▾` chip itself — 53 × 32, no chevron caret, the panel just sits above it |
| Rows | four stacked cards, **73 / 73 / 56 / 73 px**, full panel width |
| Selected row | rose-tinted 1 px border + filled pink check circle at the right edge |
| Section header | `ALL MODELS`, uppercase, muted, between the custom-model card and the list |
| Badges | `Beta` pill on `Create Custom Model`; `Pro` pill inline after `v6` and `v6-wild` |

Card order is deliberate: **the paid upgrade sits first, above the free options**,
separated by the section header so it never reads as one of the model choices.
The selected model is the only row with a filled control; the others show only a
label and description — no radio rings, no hover chrome baked in.

Each description is a single clause ending in a period, which is what keeps the
cards at a stable height (56 px for the one-liner, 73 px for two lines):

- `Powerful. Versatile. Refined. Our best model yet.`
- `Best for experimental ideas.`
- `A free, more efficient version of premium v6 models.`
- `Create a model based on your uploads (100 Credits)`

## 7. Footer / transport `M`

| # | Element | Behaviour |
|---|---|---|
| F-01 | Master `Main` fader + meter | Master volume, persisted |
| F-02 | `Mute main` (two rows) | Master mute |
| F-03 | Learn menu | Opens help/tour |
| F-04 | "What's This?" card | "Hover over any control to see how it works. Click Learn to turn What's This? off." with `Dismiss` / `Turn off` |

The hover-help system is a real feature: every control has an explanatory tooltip,
toggled globally by `Learn`.

### 7.1 The hover card, measured (S15)

Capture `screens/S15-whats-this-card.jpeg`, 1689 × 1277 px at DPR 1. Hovering
`120 BPM` produced:

```
+--------------------------------------+
| Tempo                                |
| Your song's tempo in beats per       |
| minute. Click to set a BPM or follow |
| a track's own timing.                |
+--------------------------------------+
```

| Property | Value |
|---|---|
| Size | **256 × 105** at (1279, 50) |
| Surface | `#d2d0ce` — *light*, the only light surface in the dark editor |
| Text | `#111111`, 12 px; body at `rgba(17,17,17,0.8)`, line-height 16.2 px (1.35) |
| Title | 12 px / **700** — weight, not size, separates it from the body |
| Radius | 16 px |
| Shadow | `0 8px 24px rgba(0,0,0,0.35)` |
| Padding | 16 px, fixed 256 px width (wraps at a stable measure) |
| Anchor | below the hovered control, left edge shifted so the card stays inside the viewport |

Two behaviours worth copying:

- **Inverted contrast.** Every other floating surface is dark; the help card is
  light. In a dark DAW that is the cheapest possible "this is meta, not content"
  signal, and it survives over any track colour.
- **The intro note is separate.** The `What's This?` card in the bottom-right
  corner is only the *affordance* (§7, F-04). It collapses to a one-line toast
  (`Click "Learn" to turn What's This? off.`) after `Dismiss`, while per-control
  cards keep working — dismissing the note does not disable the feature.

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

#### 18.2.1 Measured (S49)

Capture `screens/S49-export-menu.jpeg`.

| Property | Value |
|---|---|
| Size | **186 × 120** at (1485, 50) — right-aligned under the `Export` button |
| Surface | `#252529`, radius **10 px**, shadow `0 3px 5px rgba(0,0,0,0.3)` |
| Rows | 3 × 40 px, full width |
| Row layout | icon · label · (no accelerators) |
| Separator | none, despite three genuinely different scopes |

Icons are the only differentiator between the three scopes — album/stack for
`Full Song`, a dotted range for `Selected Time Range`, lane bars for `Multitrack`.
The menu closes into a **dialog** for options; it does not export on click.

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

### 19.1 The library has two levels (S52, S53)

Captured at 1689 px, panel pinned right at **360 × 1261** (x 1321 → 1681), surface
`#101012` — one step darker than the editor, so the panel reads as a separate column
rather than a card.

**Level 1 — workspaces** (`S52-library-workspaces.jpeg`):

```
[All Songs ▮][Liked ♥]        ← 2 × 2 tile grid, one colour each
[Stems  ▮][Uploads ▮]

Workspaces                       See all ›
  + New workspace
  ▨ My Workspace      946 songs
  ▨ BDBT50             42 songs
  ▨ BDBT-16-May        67 songs
  ▨ BVBR19-May         20 songs

Studio Projects                  See all ›
  ▤ Drum & Bass Demo   4m ago
  ▤ Untitled Project  14m ago
  ▤ Untitled Project  1h, 41m ago
  ▤ Untitled Project  1h, 28m ago
```

- The four tiles are **filters over the same corpus** (all / liked / stems / uploads),
  each with its own accent colour — blue, purple, green, pink.
- Workspace rows carry a **generated gradient thumbnail** and a song count.
- Studio Projects rows carry a small **mini-timeline thumbnail** and a relative age.
- Both sections end in `See all ›`; the list is truncated at four rows, not scrolled.

**Level 2 — songs in a workspace** (`S53-library-songs.jpeg`): the same panel swaps
to a reverse-chronological list grouped by date header (`Yesterday`, `Oct 24, 2026`,
`Jul 23, 2026`) with a toolbar of `filter ▾ · New ▾ · upload · In Project · Stems`.
Each row: 44 px artwork, title, one-line description, then a tag strip
`V6 COVER · D minor · 128 BPM`.

That tag strip is the load-bearing detail — **key and tempo are visible in the
browser**, before anything is loaded into the DAW. A clone that shows only titles
forces the user to open a project to find out what it is.

Note `In Project` as a filter: the same list can be narrowed to material already
used by the open project, which is how you avoid re-adding the same stem twice.

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

### 24.1 Naming gate runs first (captured)

Screenshots: `S12-share-naming-gate.jpeg`, `S12-share-dialog.jpeg`.

Sharing an unnamed project does **not** open the share dialog. It opens a gate:

```
        Name project before sharing
   Give your project a name before it's shared with others

   [ Untitled Project                          ]

          Skip              (  Save  )
```

| Detail | Value |
|---|---|
| Trigger | `Share Project` while the name is still the default |
| Input | pre-filled with the current name (`Untitled Project`) |
| Actions | `Skip` (ghost) · `Save` (light pill) |
| `Skip` behaviour | proceeds to the share dialog **without** renaming |

`Untitled Project` is treated as *unnamed*, not as a valid name.

### 24.2 Dialog measurements

| Property | Value |
|---|---|
| Dialog | 480 × 322, `#1c1c1f`, radius **24** |
| Title | **28 px `PP Neue Montreal`**, weight 400 |
| Buttons | `Done` and `Copy Link` both 204 × 56, radius 100 |
| Emphasis | `Copy Link` is the light pill (`#f7f4ef`); `Done` is ghost |

The serif is **not** used here — `Studio Settings` titles in `Editorial New` at
24 px (§64.1), while ordinary modals title in the grotesk at 28 px. Two different
title treatments, so don't unify them.

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

### 25.1 Confirmed at 1094 px

Screenshots: `reference/screens/S08-version-history.jpeg` and
`S08-version-history-loading.jpeg`.

| Property | Measured |
|---|---|
| Panel | 300 × 1193 at **(8, 44)** — sits below the header, above the footer |
| Fill | `#101012` (page is `#101012`; panel reads as a separate pane by edge, not by tint) |
| Active entry | **44 px** tall button, 267 wide at x=24, fill `#1c1c1f` |
| Loading state | literal text `Loading...` under the divider, no skeleton |

Two details §25 missed:

1. **The date row is navigable** — `‹ 10/31/2026 ›` with chevrons on both sides,
   so history is paged by day rather than being one flat list.
2. **The newest entry is expanded, the rest collapsed** — the top row is a
   highlighted 44 px button carrying a `⌄`; older rows are plain timestamp + dot
   on a vertical rail. It is a disclosure list, not a flat table.

The panel also **pushes the editor right** rather than overlaying it — the canvas
narrows, the track panel and ruler reflow.

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

### 36.1 Visual spec — the overlay itself (S14)

Capture `screens/S14-keyboard-shortcuts.jpeg`, 1115 × 1245 px at DPR 1, so image
pixels are CSS pixels.

| Element | Observed |
|---|---|
| Panel | ≈ 748 × 874, centred, radius ≈ 16 px, opaque near-black; the arrangement behind stays at **full contrast** — no scrim |
| Header | `Keyboard Shortcuts` 20 px / 600 left; search pill ≈ 206 × 36 with a magnifier and placeholder `Search shortcuts`; 36 px circular close at the right |
| Body | two equal columns, ≈ 28 px gutter, ~33 px row rhythm |
| Section headers | uppercase, ≈ 11 px, letter-spaced, muted — `GENERAL`, `TRACKS`, `EFFECTS CHAIN`, `CLIP EDITOR · AUDIO`, `CLIP EDITOR · MIDI` |
| Row | action label 13 px left; keycaps right-aligned |
| Keycap | each key its own chip: ≈ 11 px uppercase, radius ≈ 4 px, one step lighter than the panel, no border |
| Combos | modifiers are **separate chips** — `CTRL SHIFT Z` is three chips, not one |
| Alternatives | rendered as a second chip group after a gap: `BACKSPACE` `DEL`, `CTRL SHIFT Z` `CTRL Y`, `CTRL SHIFT ,` `CTRL SHIFT <` `CTRL ,` |
| Scroll | content overflows the panel (`Swap Bottom Panels` is clipped at the bottom edge); the list scrolls inside the panel with no visible scrollbar track |
| Trigger state | the `Learn` pill stays in its inverted/active state while the overlay is open |

Two implementation rules fall out of the capture:

1. **Keycap = one chip per physical key.** This is what makes `CTRL SHIFT ,` and
   `CTRL ,` legible as different gestures at a glance.
2. **Search filters the same list in place.** The field sits in the header rather
   than above the columns, so the panel never reflows when the query narrows the
   result set.

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

### 38.1 Visual spec — the popover (S13)

Capture `screens/S13-learn-menu.jpeg`, 1115 × 1245 px at DPR 1.

| Element | Observed |
|---|---|
| Trigger | `Learn` pill, bottom-right of the editor: ≈ 92 × 40, fully rounded, lightbulb glyph + label |
| Trigger active state | pill **inverts** — light fill, dark label — for as long as the menu is open |
| Popover | ≈ 228 px wide, right edge flush with the pill's right edge, ≈ 8 px above it, radius ≈ 12 px, one step lighter than the canvas, no border, no scrim |
| Rows | four, ≈ 44 px tall: `Keyboard Shortcuts`, `YouTube Tutorials`, `Learning Center`, `What's This?` |
| Row anatomy | 20 px leading icon · 13 px label · right-aligned meta |
| Meta column | `shift ?` (plain text) · external-link arrow · `On` (toggle state) · nothing |
| Separators | none — no dividers, no chevrons |

Icons are distinct per row rather than a generic bullet: list glyph (shortcuts),
play-in-square (tutorials), info circle (learning center), lightbulb (what's
this?). The external-link arrow on `YouTube Tutorials` is the only cue that the
item leaves the app, and it is the only row with no keyboard meta — the arrow
occupies that slot instead.

The menu is a **popover, not a dialog**: it does not trap focus, does not dim the
editor, and closes on outside click. Nothing about it blocks the transport.

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

### 44.10 Two matching captures: empty vs loaded (S16, S17)

Both shot at **1689 × 1277** (DPR 1) from the same session, so they diff cleanly:

| | `S16-editor-empty-project.jpeg` | `S17-editor-loaded-project.jpeg` |
|---|---|---|
| Project chip | `Untitled Project` | `Drum & Bass Demo` |
| Undo / redo | both disabled | Undo disabled, redo disabled (fresh load) |
| Time readouts | `00:00.000` / `001.1.1` | `00:00.000` / `001.1.1` |
| Tempo | `120 BPM` `4/4` | **`174 BPM`** `4/4` |
| Tracks | one `Audio Track`, no clips | 12+ named tracks, clips across the full width |
| Ruler | bars every 8 from `1` | bars every 8 from `1` to **`137`** — the ruler rescales to song length |
| Magic Bar | placeholder `Select a spot on the timeline and ask me to add a part` + `Tab` hint | same placeholder, plus a **`Soft Piano` attachment chip** |
| Bottom FX strip | absent | `E.Q` · `Reverb` · `Stereo Utility` · `+` |
| Overlays | none | tooltip `Press play to hear the demo` |

Three details the empty state settles that the loaded state hides:

- An empty project is **not** an empty canvas: it ships with one `Audio Track`
  already created, `Add new track` centred under the track header, and the full
  transport.
- The Magic Bar is present from the first second and shows a **keyboard hint**
  (`Tab`) beside the placeholder — it is a first-class input, not an afterthought.
- `Add new track` is a text button under the gutter, not a `+` in the toolbar.

And one detail the loaded state settles:

- **Clip labels truncate, never shrink.** Short clips read `E...`, `V...`, `M...`,
  `S...`, `B...`; long clips carry the full name. The type size is constant, so
  the timeline keeps an even texture at any zoom.

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

#### 46.1 The exact threshold is 768 px (S65) — this corrects the ~706 px note

Probed by resizing the live page through a range of widths and testing for the gate
copy:

| Width | Renders |
|---|---|
| 740 | **gate** |
| 750 | gate |
| 760 | gate |
| 766 | gate |
| **767** | **gate** |
| **768** | **editor** |
| 770 | editor |
| 780 | editor |
| 800 | editor |

So the boundary is exactly **768 px** — one CSS pixel either side flips it. The
earlier "≈706 px" reading came from measuring a window's outer frame rather than the
layout viewport; treat 768 as the number.

**The gate** (`S65-gate-767px.jpeg`): a single centred card, 380 px wide, radius
20 px, holding a laptop photograph (cropped to the top half), `SUNO Studio` at
24 px / 600, the copy

> Studio is desktop-only for now. Head to suno.com/studio on your computer to start
> creating.

and one `Back to Create` button (40 px tall, pill). No header, no navigation — the
gate replaces the app rather than covering it.

**At 768** (`S65-editor-768px.jpeg`) the editor does render, and it degrades in a
specific order:

| Region | At 768 px |
|---|---|
| Header | drops undo/redo; project chip truncates to `Drum & Bar`; time readout clips to `01:29.` while `174 BPM` survives |
| Track gutter | holds 283 px — the same width as at 1689 px, so the canvas absorbs all the loss |
| Footer | tools collapse to four icons, chain chips stay |
| Dock | still two columns (plugin card + add rail), each narrower |
| Library | opens **over** the canvas rather than shrinking it further |

The order matters for the clone: **the gutter never shrinks, the canvas does.** A
responsive implementation that squeezes the track header first would be wrong even
though it looks tidier.

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

### 47.1 Variant C, measured (S26)

Capture `screens/S26-clip-context-menu.jpeg`, right-clicked on a clip in
`Drum & Bass Demo`. This is the **complete** menu — 13 items, nothing below the
fold:

| Property | Value |
|---|---|
| Size | **171 × 525** at (708, 114) — anchored at the click point, opening down-right |
| Surface | `#252529`, radius **10 px**, border `0`, shadow `0 3px 5px rgba(0,0,0,0.3)` |
| Padding | `0` on the panel; each row carries its own 40 px height |
| Row | 13 × 40 px = 520, + 5 px panel inset |
| Row layout | 16 px icon · 15 px label · right-aligned accelerator in a muted tone |
| Dividers | **none** — grouping is implied by order, not by rules |

Against variant B (§47) this capture has `Delete` **and** `Heal Edits` but **no**
`Create Section`. So `Create Section` is the one item gated on something this clip
lacks (it is an audio stem, not a section-capable arrangement block), while
`Heal Edits` appears here because this clip *does* carry an edit chain. That is
the third independent confirmation that the list is derived from clip state.

Right-click does three things besides opening the menu, and all three are visible
in this single frame:

1. **Selects the clip** — orange 1 px outline drawn inside the clip bounds.
2. **Re-targets the Magic Bar** — the attachment chip flips to `Electric Keyboa…`
   and the placeholder becomes `Add a warm reverb to this track`.
3. **Re-points the footer FX strip** at that track's chain — `Compressor · EQ ·
   EQ · Reverb · +` (duplicate `EQ` entries are real: a clip can carry two EQ
   instances).

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

### 48.1 Measured at 1689 px (S39)

Capture `screens/S39-plugin-catalog.jpeg`.

| Property | Value |
|---|---|
| Panel | **760 × 958** at (465, 160) — vertically centred, radius **32 px** |
| Header | `Add a track plugin` left; `Search plugins` field + `⋯` + `×` right |
| Search | 160 px wide input inside a 207 px pill, **right-aligned in the header**, not spanning |
| Grid | 3 columns × 224 px + 16 px gaps; card **224 × 200** |
| Create card | 224 × 164 **dashed** outline — visibly "empty slot", not a normal card |
| Card content | 96 px live preview → name + `ⓘ Learn` → 2-line clamped description |
| Badges | yellow `NEW` (Delay) / `Improved` chips pinned top-left of the preview |

The preview is a **real render of the plugin's own controls** at reduced scale
(curve, knobs, band chips) — not an illustration. That is why cards from the same
family read as a set without any shared artwork.

The 958 px height against a 1277 px viewport means the grid **scrolls inside the
panel** rather than growing the dialog; the thin scrollbar track is visible on the
right edge and the ninth card is clipped by it.

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

### 50.1 Measured: one slot vs two (S40, S41)

| Property | Value |
|---|---|
| Dock band | **1673 × 224** at (8, 999) — full width minus 8 px margins, above the footer strip |
| Slot card | **448 × 160**, header row on top, controls below |
| Slot gap | ≈ 23 px |
| Empty rail | the remaining width becomes a second panel with a centred `+ Add effect` (123 × 40) and three **ghost tiles** (`Compressor` · `Reverb` · `Delay`) rendered at ~30 % opacity |

`S41` shows two slots (`EQ` + `Distortion`); `S40` shows the single-slot case. The
difference is the whole lesson:

- The dock does **not** centre a lone plugin, and it does not stretch it. The first
  card keeps its 448 px width and the rest of the band becomes the add-affordance.
- The ghost tiles in the empty rail are a **preview of the next three plugins in
  catalog order**, so the empty half of the dock still teaches what can go there.
- Removing the last plugin (the `×` on a header) leaves the add rail alone — the
  dock never collapses, so the layout does not jump when you clear a chain.

Each slot header repeats the same four parts: colour dot · name · preset selector
(`Custom ▾`) · `×`. `EQ` additionally shows a live transfer curve with draggable
points, `Distortion` a drive curve plus mode chips (`Soft · Hard · Fold · Asym ·
Sine · Crush`).

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

### 52.1 The row, confirmed at 1689 px (S18)

Crop `screens/S18-track-row-anatomy.jpeg` — 900 × 250 CSS px at 2× from the loaded
demo, so it is a pixel-accurate diagram of one row.

```
 1   Electric Keyboards              🔊  Ⓢ  Ⓐ  ⌄      ┌ clip band starts at x=283
 └─ colour strip (4 px, full height)
     [═════ volume (172 px) ═════|═]  [━ pan (48 px) ━]|
```

| Element | Position (CSS px) | Note |
|---|---|---|
| Colour strip | x 0–4 | full row height, the track's own colour |
| Track number | x ≈ 18 | muted, right-aligned to a fixed column |
| Name | x ≈ 47 | 13 px, single line, no ellipsis in the gutter |
| Speaker (mute) | x ≈ 162 | outline speaker, filled when muted |
| `S` | x ≈ 192 | bare letter, no button chrome until hover |
| `A` | x ≈ 222 | **round** chip — the only round control in the row |
| `⌄` (track options) | x ≈ 243 | opens S19 |
| Volume | x 24 → 196 | rounded track, vertical handle |
| Pan | x 206 → 254 | half the width of volume, same handle |
| Row height / step | 85 / 86 px | confirms §52 |
| Gutter | 0 → 281 | 1 px divider, then the clip band from 283 |

State cues visible in this one crop:

- **Selected row** → full-width lighter fill (track 1).
- **Focused slider** → 2 px green outline (track 2 `Soft Piano`, volume slider).
- **Mute/solo** carry no fill at rest: they are glyphs, and state is shown by
  inverting the glyph, not by painting a button.
- The playhead's bar-ruler marker is a **filled blue triangle** whose tip sits on
  the ruler line, with the vertical line drawn below it at 1 px.

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

## 54. Magic Bar — captured in context (`/studio`, project reopened)

`/studio` reopens the **last project** rather than showing a chooser, so the first
screen after sign-in is the editor. The Magic Bar floats above the footer, centred,
and is now fully visible.

### Geometry (1104 px window)

| Element | Position / size |
|---|---|
| container | x ≈ 355 → 1010 (655 px wide), y ≈ 815 → 905, rounded 14 px, dark translucent |
| row 1 | `+` attach (28 px) · **clip chip** (`🎤 Long Vocal ×`) · spacer · duplicate icon · close × |
| `BETA` badge | pinned to the container's top-right corner |
| row 2 | placeholder text left · `v6 ▾` model chip · circular submit `↑` right |
| clip chip | rounded pill, tinted with the **track colour** (pink for vocals), mic icon, name, `×` to detach |

### Behaviour captured

1. The chip binds the prompt to the **selected clip**, and its colour matches the
   track family — the prompt is object-scoped, not global.
2. The placeholder changes with context: `Add a warm reverb to this track`.
3. Submit is a circular arrow, **dimmed until the prompt has content**.
4. `+` attaches another object to the prompt.
5. The model chip (`v6`) sits on the prompt row, not in a separate toolbar.
6. The whole bar is a floating card — the timeline is visible behind it.

### Why this matters for the clone

This is the product's creation verb, and it is **object-scoped**: you select a clip or
a spot, then speak about it. Our shell has no Magic Bar at all, and our old editor had
a single-line `studio-ai-bar`. The reference is two rows with an attachment chip, a
model chip and a circular submit.

### Deltas

| Element | Reference | Ours |
|---|---|---|
| Placement | floating, centred, above footer | none in the shell |
| Attachment chip | clip with colour + detach | none |
| Model chip | on the prompt row | dropdown elsewhere |
| Submit | circular arrow, disabled when empty | none |
| BETA badge | on the container | none |

### 54.1 Idle vs attached, measured at 1689 px (S34, S35)

Two captures from the same session, `S34-magicbar-idle.jpeg` and
`S35-magicbar-attachment.jpeg`:

| Property | Value |
|---|---|
| Container | **648 × 99** at (651, 1080) — centred on the arrangement, above the footer |
| Surface | `rgba(20,20,22,0.85)` — translucent, the clip colours read through it |
| Radius | **20 px** (the largest radius in the app outside the settings dialog) |
| Border | `1px solid rgba(255,255,255,0.1)` — the only place a hairline border is used instead of a tone step |
| `BETA` badge | pink pill straddling the **top-right border line**, half outside the card |
| Attach `+` | 32 px circle, left, inside the padding |
| Right icons | `Open conversation` (32 px) and `Collapse` (32 px) on the chip row |
| Model chip | `v6 ▾`, 53 × 32, sits on the **prompt row**, right of the text |
| Submit | 32 px circle, `↑`, dimmed while the prompt is empty |

Attachment chip anatomy (S35):

- 30 px rounded thumbnail whose fill is the **track colour** — so the chip carries
  the same hue as the clips it refers to (yellow for `Drum Kit Main`).
- Track name at 13 px, then a 14 px `×` that detaches it.
- The chip replaces the leading text position; the placeholder stays visible after it.

Placeholder is **generated from the current selection**, and that is the single
most important thing to copy:

| Selection state | Placeholder |
|---|---|
| Nothing selected, empty project | `Select a spot on the timeline and ask me to add a part` |
| Track/clip selected | `Add a warm reverb to this track` |
| Drum track attached | `Generate an 8-bar drum loop and drop it here` |

Copy the rule, not the strings: the prompt is seeded with a *plausible next action
for the selected object*, so the bar teaches the interaction by example.

## 55. Project menu — visual detail `L`

Rendered as a floating card anchored under the project chip, ~220 px wide, 8 rows with
icons and one accelerator:

| Icon | Item | Accelerator |
|---|---|---|
| ＋ | New Project | |
| ▤ | Open Project | |
| ✎ | Rename | |
| ⧉ | Duplicate Project | |
| ◷ | Version History | |
| ↗ | Share Project | |
| ⇱ | Open a copy in v1 | |
| ⚙ | Studio Settings | `ctrl shift ,` |
| ✦ | Show Quick Start again | |

Rows are 30 px tall, left-aligned icon + label, accelerator right-aligned in a muted
colour. No dividers — unlike the clip menu, which does group.

### Magic Bar placeholder varies

With the same clip attached, the placeholder read `Add a warm reverb to this track` in
one capture and `Ask me to generate a project…` in another. So the hint is
**generated per session/context**, not a fixed string per selection. Treat it as
model output, not static copy.

## 56. S04 — "My Projects" chooser `L`

Reached from Project menu → **Open Project**. A centred modal over the editor.

```
┌──────────────────────────────────────────────────────┐
│ My Projects  ⟳                                   ×   │
│ Projects   Recently Deleted                          │
│ ─────────────                                        │
│ [🔍 Search for Project]  [▽ Filters]  [≡ Newest First]│
│ ┌───────────────┐ ┌───────────────┐                  │
│ │      ＋       │ │  thumbnail    │                  │
│ │  New Project  │ │  title / meta │                  │
│ └───────────────┘ └───────────────┘                  │
│ ┌───────────────┐ ┌───────────────┐                  │
│ │  …            │ │  …            │                  │
│ └───────────────┘ └───────────────┘                  │
└──────────────────────────────────────────────────────┘
```

| Element | Detail |
|---|---|
| Title | `My Projects` + a **spinner while loading** |
| Close | `×` top-right |
| Tabs | `Projects` (active, underlined) · `Recently Deleted` |
| Search | full-width pill, placeholder `Search for Project` |
| Filters | funnel icon + `Filters` |
| Sort | `Newest First` dropdown |
| Grid | 2 columns, ~350 px cards |
| New Project card | dashed/tinted, centred `＋` above the label |
| Project card | thumbnail block, title line, meta line (skeleton while loading) |
| Backdrop | dark scrim; the editor stays visible behind |

### Behaviour notes

1. Opening it **does not leave the editor** — it is a modal, not a route.
2. Cards load asynchronously; the grid renders skeletons with a spinner in the title.
3. `Recently Deleted` is a first-class tab — deletion is soft, with recovery.
4. Sort defaults to `Newest First`, with filters available beside it.
5. `New Project` is the first grid cell, not a separate button.

### Delta against our Studio home

| Reference | Ours |
|---|---|
| Modal over the editor | separate `/studio` page |
| 2-column card grid with skeletons | grid of text cards |
| `Recently Deleted` tab | archived toggle |
| Filters + sort dropdowns | search + sort select |
| `New Project` as first cell | header button |

### 56.1 Corrections from the 1094 px capture

Captured with ten projects present — five from this session, older ones tagged
`Legacy`. Screenshot: `reference/screens/S04-my-projects-modal.jpeg`.

| §56 claim | Actual |
|---|---|
| `New Project` card is "dashed/tinted" | **solid** `#1c1c1f`, 350 × 242, no dashed border, no visible stroke |
| Meta line unspecified | the meta line is a **date**: `Oct 31, 2026`, `Oct 25, 2026` |
| No legacy concept mentioned | older projects carry a **`Legacy`** tag (43 × 18) above the title |
| "thumbnail block" | thumbnails are real **mini-timeline renders** — clips drawn at true colours and positions; loading cards show a spinner instead |

Measured at this width: modal body 730 × 718 at (182, 264); grid cells 350 × 242;
2 columns; the grid scrolls (a partial third row is visible).

The `Legacy` tag matters for migration: it marks projects created before the
current Studio generation, which is the same population §59's `Open a copy in v1`
targets.

### 56.2 Still uncaptured

`Recently Deleted` tab contents, the `Filters` dropdown options, and the
`Newest First` sort alternatives.

## 57. S01 — signed-out marketing page `/studio-welcome` `L` (1116 px)

Captured live 2026-10-30 while signed out. This is the **only** public entry to
Studio; there is no separate marketing route at `/studio`.

### 57.1 Route behaviour

| Request | Result |
|---|---|
| `/studio` while signed out | redirect → `/studio-welcome` |
| `/studio-welcome` | renders unauthenticated, no gate |
| `/studio` while signed in | opens the last project (§54) |
| `Open Studio` / `Try it now` | plain `<a href="/studio">`, re-enters the redirect |
| `Log in` | opens the sign-in modal in place (§58) |

Note the dead end: signed out, `Open Studio` and `Try it now` both point at
`/studio`, which bounces straight back to this page. The header CTA only means
something once a session exists.

### 57.2 Page order (measured at 1116 × 1245, document height 6852)

| # | Section | Top | Height |
|---|---|---|---|
| 1 | Hero — `Studio 2.0: Be a control freak.` | 0 | 1369 |
| 2 | Made in Suno Studio (10 track cards) | 1369 | 790 |
| 3 | Play it how you mean it. | 2159 | 634 |
| 4 | Plugins you can design yourself. | 2793 | 634 |
| 5 | Say the word, build your sound. | 3427 | 634 |
| 6 | Let your work flow (5 feature rows) | 4061 | 741 |
| 7 | Dive deeper (tutorials) | 4802 | 647 |
| 8 | Frequently asked questions (10 items) | 5449 | 1017 |
| 9 | Final CTA — `Be a control freak. Try Studio now.` | 6466 | 386 |

### 57.3 Header

```
[SUNO]   Products ⌄  Resources ⌄  Pricing  Careers        (Log in)  (Open Studio)
```

| Element | Metric |
|---|---|
| Band | ~76 px, transparent over black, not sticky in this capture |
| Wordmark | `SUNO` wordmark, white, all caps, tight tracking |
| Nav links | 16 px / 400, 36 px tall, items start at x=139 |
| `Log in` | ghost pill 71 × 40, 15 px / 500, 1 px light border, transparent fill |
| `Open Studio` | solid pill 130 × 40, 15 px / 500, `#fff` fill, `#000` text |

### 57.4 Hero metrics

| Element | Metric |
|---|---|
| H1 | **96 px / 104 px**, weight **300**, `Editorial New` (display serif), tracking **−2.88 px** (−0.03 em), `#f7f4ef`, centred, 2 lines (`Studio 2.0:` ⌙ `Be a control freak.`), box 615 × 208 |
| Subtitle | 18 px / 28 px, `Neue Montreal Book` 400, `#a3a3a3`, max-width 520 |
| CTA `Try it now` | 192 × 56 pill (radius 9999), `#fff` fill, `#000` text, 17 px / 500 |
| Vertical rhythm | H1 bottom 336 → subtitle 360 → CTA 412 (24 px gaps) |
| Hero media | full-bleed dark 3D render of the timeline (grid, orange clip, cursor) below the CTA, no border |

### 57.5 Design tokens observed

| Token | Value |
|---|---|
| Page background | `#000000` |
| Primary text | `#f7f4ef` |
| Muted text | `#a3a3a3` |
| Solid action | `#ffffff` on `#000000` |
| Display face | `Editorial New` (serif, 300) |
| UI face | `Neue Montreal` / `Neue Montreal Book` (grotesk) |
| Shape language | full pills for every button, 0 px radius on type blocks |

Two families only: serif for headlines, grotesk for everything else. There is no
third accent colour anywhere in the page — colour enters only through the hero
render and the track-card artwork.

### 57.6 Copy inventory (verbatim)

- H1: `Studio 2.0:` / `Be a control freak.`
- Sub: `Own every note, knob and detail in our powerful browser-based DAW.`
- Hero CTA: `Try it now`
- `Made in Suno Studio` — `Tracks produced start to finish in Studio, from the first idea to the final mix.`
- `Play it how you mean it.` — MIDI controller, musical typing, arpeggiator, chord mode.
- `Plugins you can design yourself.` — sidechain, convolution reverb, custom effects.
- `Say the word, build your sound.` — describe a synth/plugin in words; batch-rename tracks via chat.
- `Let your work flow` — five rows: `Start from anywhere` · `Edit anything and everything` · `Automate any parameter` · `Advanced stem separation` · `Take your work with you`.
- Final CTA: `Be a control freak. Try Studio now.` + `Try it now`

### 57.7 Delta against ours

| Reference | Ours |
|---|---|
| Public page at a dedicated `/studio-welcome` | public variant rendered inside `/studio` (`(site)/studio/page.tsx` → `StudioMarketing`) |
| Signed-out `/studio` **redirects** out | `/studio` renders the marketing view in place, no redirect |
| Serif display + grotesk UI, two families | single UI family |
| Track evidence social proof (real songs, plays, likes) | no social proof block |
| 9 sections, 6852 px | shorter page |

**Product decision this informs (open #4):** Suno keeps the marketing page *out*
of `/studio` so that `/studio` can answer one question only — "which project?".
If we adopt the redirect, `/studio` becomes signed-in-only and the marketing
story moves to `/studio-welcome`, which is the shape the rest of the spec assumes.

## 58. S02 — sign-in gate `L`

There is **no standalone sign-in route**. Sign-in is a modal raised over the
marketing page, and it is reached only from the header `Log in` button.

### 58.1 Gate behaviour (verified)

| Step | Observed |
|---|---|
| `GET /studio` signed out | server redirect → `/studio-welcome` |
| `GET /studio-welcome` signed out | marketing page renders, no gate, no flash |
| Click `Log in` | modal appears in place, URL unchanged |
| Modal dismiss | `Close` returns to the page, no navigation |

Redirect rather than an interstitial: the guard is a route rule, not a client
check, so there is no "protected route flicker".

### 58.2 Modal anatomy

| Element | Detail |
|---|---|
| Title | `Welcome to Suno` |
| Provider buttons | `Continue with Google` · `Continue with Apple` · `Continue with Phone` |
| Divider | the word `or` between the two groups |
| Secondary providers | `Discord` · `Facebook` · `Microsoft` |
| Close | `Close` button, top-right |

- No email + password fields. Identity is provider-first; phone replaces the
  classic email form entirely.
- The modal is a single step — no email-verification interstitial was shown
  before the provider handoff.

### 58.3 Error state (captured verbatim)

```
Welcome to Suno
Log in failed. Please try again.
```

The failure banner sits inside the modal above the provider list and does not
dismiss itself; the provider buttons stay enabled so the user retries in place.
This is the **auth-failure** member of the error taxonomy in §16 and the concrete
answer for matrix row `Q3` (error states) on the entry path.

### 58.4 Delta against ours

| Reference | Ours |
|---|---|
| Modal over the marketing page, URL unchanged | routes at `(auth)/login`, `(auth)/signup` |
| Provider-only: Google / Apple / Phone | provider buttons plus email form |
| One modal for sign-in and sign-up | separate login and signup pages |
| Failure shown inline, retry in place | route-level error handling |

### 58.5 Visual metrics (measured, `S02-sign-in-modal.jpeg`)

Screenshot `screens/S02-sign-in-modal.jpeg` — 1250 × 1245 px at DPR 1.12, i.e. a
1115 px viewport. Values below are CSS px read from the live dialog.

| Property | Value |
|---|---|
| Dialog box | **400 × 366** at (425, 440) — horizontally centred, vertically centred |
| Dialog surface | `#1c1c1f`, radius **32 px**, no border, no shadow |
| Dialog padding | outer `0`; content inset comes from the child stack |
| Overflow | `auto`, `max-height: 1120.5px` (viewport-bound, not content-bound) |
| Scrim | fixed, full viewport, `z-index: 1000`, dims the page behind |
| Title | `Welcome to Suno` — 24 px / 500, `#fcfbf9`, tracking −0.6 px, centred |
| Close | 40 × 40 circle, radius 9999 px, 15 px / 500, `aria-label="Close"` |

Buttons, all 12 px radius, all `#252529`:

| Group | Size | Type | Note |
|---|---|---|---|
| Google / Apple / Phone | 350 × 48 each | 15 px / 500 | full-width stack, brand glyph left-aligned inside |
| Discord / Facebook / Microsoft | 111 × 48 each | 13 px / 500 | three-up row, equal width, same height as the primary stack |
| `or` divider | — | 12 px, `#a3a3a3` | hairline rule either side, sits between the two groups |

Two details worth copying exactly:

- The secondary row is **the same 48 px height** as the primary row. It reads as
  smaller only because the type drops from 15 → 13 px. Do not shrink the target.
- Every button is `#252529` on a `#1c1c1f` dialog — a 9-value lift, not a
  border. There is no 1 px outline anywhere in the modal; separation is tone
  only.

## 59. S05 — new empty project `L` (1094 px)

Captured live on a fresh sign-in. Three entry paths all land on this one screen:
`New Project` in the My Projects modal (§56), the `Empty Project` card in the
onboarding overlay (§10), or the post-signup redirect.

### 59.1 Defaults on creation

| Property | Value |
|---|---|
| Project name | `Untitled Project` (inline-editable, `⋯` menu beside it) |
| Tempo | `120 BPM` |
| Time signature | `4/4` |
| Tracks | **exactly one**, named `Audio Track` |
| Clips | none — no placeholder, no drop hint |
| Playhead | `00:00.000` / `001.1.1`, at the left edge |
| Transport | stopped |
| Master | `Main` bus present, level bar at zero |

The track is created for you. You never face a zero-track arrangement.

### 59.2 Measured layout (1094 × 1245)

| Region | Geometry |
|---|---|
| Header band | y 0–52; controls at y=8, 36 px tall |
| Canvas | 1078 × 1141 at (8, 52) |
| Track panel | 260 × 1141 at x=8, `rgba(20,20,22,0.85)` |
| First track row | 85 px tall, top y=82 |
| `Add new track` | 133 × 36 centred, 12 px / 500, white at **20 %** |
| Panel hit target | the add button's enclosing `button` is 260 × **941** — it fills the whole empty panel below the last track |
| `Main` row | 232 × 32 at (24, 1124) |
| Prompt container | 648 × 99 at (353, 1048) |
| Prompt text | 14 px / 500, `#c2c2c1`, at y=1116 |
| `Learn` pill | bottom-right, 12 px / 600, dark text on a light pill |

### 59.3 Header readouts

All four are **10 px / 500 at white 50 %** — the smallest type in the editor:

```
00:00.000    001.1.1    120 BPM    4/4
```

`Export` is 16 px solid white; `Library` is 13 px at white 50 %. So the only
full-contrast item in the right cluster is Export, which is the one action that
leaves the editor.

### 59.4 Rulers on an empty project

| Ruler | Labels |
|---|---|
| Bars (top) | `1 · 3 · 5 · 7 · 9 · 11 · 13` — odd numbers, every **2** bars |
| Time (bottom) | `00:00 · 00:30 · 01:00 · …` every 30 s |

**Correction to §44.3.** The loaded demo was recorded as labelling every 8 bars
(`1 · 9 · 17 · 25 …`). At default zoom on an empty project it is every 2 bars.
Label cadence is therefore **zoom-dependent**, not a fixed project-wide step —
pick the label interval from pixels-per-bar at render time.

### 59.5 Prompt placeholder is the empty-project variant

Captured verbatim:

```
Select a spot on the timeline and ask me to add a part
```

This is the evidence §26 lacked. The placeholder is context-sensitive:

| Context | Placeholder |
|---|---|
| Empty project | `Select a spot on the timeline and ask me to add a part` |
| Clip attached | `Add a warm reverb to this track` |
| Session-dependent | `Ask me to generate a project…` |

The empty-project string is **instructional** — it teaches the interaction
(place the playhead, then ask) rather than describing the field.

### 59.6 Behaviour notes

1. `Add new track` is a full-panel target, not a small row — the entire empty
   area under the last track adds a track when clicked.
2. The onboarding overlay's dismiss control is `Skip to the empty project`
   (`aria-label`, §10). Dismissing lands on exactly this state, so S06 → S05 is
   a one-click transition.
3. The `What's This?` card persists over the empty project on first run (§15).
4. Nothing in the empty state suggests dragging audio in; upload lives in the
   add-track menu and the onboarding card, not on the canvas.

### 59.7 Delta against ours

| Reference | Ours |
|---|---|
| One `Audio Track` created with the project | **zero** tracks — `derivedTracks` rebuilds from clips, so an empty project has no rows until one is added |
| `Untitled Project` | `Untitled project` (capitalisation differs) |
| 120 BPM / 4/4 | 120 BPM / 4/4 — matches |
| Ruler label cadence scales with zoom | single fixed ruler |
| Full-panel `Add new track` target | small add-track control |
| `Select a spot on the timeline…` empty prompt | static placeholder |

The track-creation gap is the behavioural one: on the reference the first row
always exists, so track-targeted actions (plugins, arm, solo) are immediately
available; ours starts with an empty panel.

## 60. Responsive floor — Studio refuses narrow viewports `L`

Captured by accident when the browser pane shrank to **319 × 468** CSS px (DPR 3)
while a project was open. The editor does not reflow. It is **replaced** by a
gate:

```
┌────────────────────────────┐
│   [ photo: laptop running   │
│     the Studio editor ]     │
│                             │
│        SUNO Studio          │
│  Studio is desktop-only     │
│  for now. Head to           │
│  suno.com/studio on your    │
│  computer to start creating.│
│                             │
│      ( Back to Create )     │
└────────────────────────────┘
```

| Evidence | Value |
|---|---|
| Viewport | 319 × 468, DPR 3 |
| `document.querySelectorAll('canvas').length` | **0** — the editor never mounts |
| Message | 14 px, `#a3a3a3`, 253 px wide, centred |
| Action | `Back to Create` (rendered after the message) |
| Card | inset, large radius, dark surface over a photographic hero |

### 60.1 The floor sits between 319 and 706 px

| Width | Result | Source |
|---|---|---|
| 706 px | full editor, compressed | §46 |
| 319 px | **hard gate**, no editor | this capture |

So there is a minimum-width threshold somewhere in `(319, 706]`, and above it
Studio still compresses rather than hiding panels (§46). Below it there is no
responsive variant at all — no stacked panels, no mobile layout, no horizontal
scroll.

### 60.2 What this means for us

1. **Do not build a mobile Studio.** The reference explicitly declines; a
   responsive editor would be work the product has decided against.
2. **Ship a gate with a minimum width** instead of letting panels collapse into
   an unusable state. A CSS-only `@media (max-width: …)` gate is enough; the
   editor chunk should not be needed to render it (`hasCanvas: 0` shows the
   reference does not mount the renderer).
3. Copy the honest framing — it names the constraint, gives the URL, and offers
   one way out. It does not apologise or promise an app.

**Correction to matrix row `R1`**, which recorded responsive capture as `BLOCK`
(no viewport resize available): the viewport could not be *resized by us*, but
the pane did resize, which is what produced this. R1 is now `PART` — the gate is
captured, the 1280 / 1024 / 768 editor states are not.

## 61. S19 — track options menu `L`

**Trigger: right-click the track NAME.** Not the row, and not the level bar —
those give different results (§61.3). There is no options button on the row.

### 61.1 Geometry

| Property | Value |
|---|---|
| Container | 166 × 240 at (98, 114) |
| Fill | `#252529` |
| Radius | 10 px |
| Items | **6 × 40 px**, no dividers |
| Item text | 14 px / 500, `#f7f4ef` |
| Icon column | starts 16 px from the menu edge |
| Label inset | 40 px — all six labels align on one column |
| Anchor | opens at the pointer, over the track panel |

### 61.2 Items (verbatim, in order)

| # | Icon | Item | Note |
|---|---|---|---|
| 1 | pencil | `Rename track` | |
| 2 | colour dot + `▸` | `Color` | the dot shows the track's **current** colour; the only row with a **submenu** |
| 3 | collapse glyph | `Collapse controls` | |
| 4 | two overlapping squares | `Duplicate` | |
| 5 | eye with slash | `Hide & Mute Track` | hide and mute are one command, not two |
| 6 | trash | `Delete` | plain text — **not** red |

Every row carries an icon; none carries an accelerator hint. `Delete` has no
danger colour, so the destructive action is indistinguishable from the rest.

### 61.3 Three different right-click targets, three different results

| Target | Result |
|---|---|
| Track **name** | this menu — 6 items (§61.2) |
| Track **level bar** | `Automate` · `MIDI Learn` — a parameter menu |
| Track **row body** | nothing (previous sessions saw a *clip* menu here) |

That last row explains matrix note `D3` ("right-click returns clip menu") — the
clip menu was being reached because the pointer was not on the name.

### 61.4 Correction to §44.4 — there is no chevron or options button

§44.4 read the trailing glyphs as `[⌄] [◉]` = "row extend / options". The row's
actual control set, measured:

| Control | Size | `aria-label` / text |
|---|---|---|
| Colour strip | 10 × 85 | `Change track color` |
| Collapse | 16 × 32 | `Collapse Track` (renders the track **number**) |
| Name | — | track name |
| Mute | 28 × 32 | — |
| Solo | 28 × 32 | `S` |
| Arm | 28 × 32 | `A` |
| **Record** | 16 × 32 | — |

The final control is **record/arm**, not options. Clicking it raises
`Error accessing audio inputs. You may need to grant microphone permission to
suno.com through your browser settings.` — so there is no options affordance at
all; the menu is right-click-only.

### 61.5 Evidence

Screenshot: `reference/screens/S19-track-options-menu.jpeg`. Everything else is
DOM-measured (rects, computed styles, verbatim `innerText`).

Visible in the capture: the menu opens over the track panel at the pointer, the
track row behind it shows its colour strip and the armed `A` state, and the
`What's This?` card is still docked bottom-right.

Still unverified: the `Color` submenu contents (the `▸` was not opened), and
hover/active styling per row.

### 61.6 Bonus: four placeholder variants observed

| Placeholder | Context |
|---|---|
| `Select a spot on the timeline and ask me to add a part` | new project, no track |
| `Generate an 8-bar drum loop and drop it here` | audio track created |
| `Ask me to generate or add something here` | after arming a track |
| `Add a warm reverb to this track` | clip attached (§54) |

This strengthens §26: the hint is generated per context and per session, and it
is never a fixed string.

## 62. S03 — signed-in entry `L`

`GET /studio` while signed in **reopens the last project in place**. There is no
project chooser, no landing page and no redirect — the URL stays `/studio`.

### 62.1 Entry sequence

| Step | What happens |
|---|---|
| 1 | Blank dark frame, `canvas` count **0**, `innerText` empty (§57) |
| 2 | Renderer mounts, one `canvas`, chrome appears |
| 3 | Last project restored by name — `Untitled Project` survives a reload |
| 4 | Track state restored too: colour strip, solo/arm state, level |
| 5 | Onboarding overlay **re-appears** on a fresh load, over the restored project |

Step 5 is the surprise: restoring an existing project does **not** suppress
`How do you want to start?`. The overlay is tied to the load, not to whether the
project is empty.

### 62.2 Control names exposed by tooltips

The What's This? system gives every header control a name, readable even though
the canvas exposes no accessibility tree:

| Control | Tooltip |
|---|---|
| Bar/section icon | `Metronome` |
| Time readout | `Time` |
| Bar.beat readout | `Beats` |
| Tempo field | `Tempo` |
| Signature field | `Time Signature` |
| `S` | `Solo track` |
| `A` (armed) | `Disarm track` |

This is the cheapest way to enumerate the header: enable What's This?, then read
`innerText`.

### 62.3 Track attachment chip

When the prompt is aimed at a track, a **pill** appears inside it:

```
[+]  ( ● Audio Track ✕ )                    [▤] [✕]
     Build a gritty delay and put it on this track      v6 ▾  (↑)
```

The pill carries the track colour dot and the track name, with `✕` to detach.
The placeholder switches to a task phrasing (`Build a gritty delay and put it on
this track`) — a fifth variant of the §26 set.

### 62.4 Correction to §59's track persistence

§59 recorded one `Audio Track` on creation, and a later remount showed **zero**
(`S05-zero-tracks-after-remount.jpeg`). After this reload the track came back.

So the zero-track frame was **not** a persistence rule — it was a frame captured
before autosave committed the new track. The track does persist; the initial
creation just isn't durable until the next save tick.

## 63. S57 — project loading `L`

Captured on a cold load of `/studio` (signed in), immediately after navigation.

| Signal | Value |
|---|---|
| Frame | **uniform dark, no skeleton, no spinner, no logo** |
| `canvas` elements | 0 |
| `innerText` | empty string |
| Duration | until the renderer mounts (§62.1 step 2) |

There is **no loading UI at all**. The editor does not paint a skeleton, a
progress bar or a wordmark — the window is simply blank until the canvas mounts.
Anything the user sees before that is chrome-free emptiness.

Consequence for us: a blank frame is the reference behaviour, so a spinner would
be a deviation. If we want to improve on it, do it deliberately rather than
assuming a loader was missed.

## 64. Studio Settings — S09 / S10 / S11 `L` (1115 px)

One dialog, three tabs. Screenshots: `S09-settings-performance.jpeg`,
`S10-settings-window-management.jpeg`, `S11-settings-content.jpeg`.

### 64.1 Frame

| Property | Value |
|---|---|
| Dialog | 760 × 512, centred, over the editor (scrim behind) |
| Title | `Studio Settings` — **24 px `Editorial New`** |
| Tab rail | vertical, 160 × 36 per item, 13 px / 400 |
| Active tab | `#f7f4ef` label on a subtle raised pill |
| Inactive tab | `#c2c2c1` |
| Setting card | 524 × 72, `rgba(255,255,255,0.04)`, radius **12** |
| Close | circular `×`, top-right |

The title is the notable detail: **the marketing serif (`Editorial New`) is reused
in-product**, not just on `/studio-welcome`. The display face is a product token,
not a landing-page decoration.

### 64.2 S09 — Performance

One card: `Ghost drag for arrangement moves`, toggle **on** (green).

> On, a move holds DSP applies for the whole gesture: audio keeps playing the
> pre-drag arrangement and one apply lands at drop. Off, move frames stream to
> the engine live. Read at gesture start.

This is a latency-vs-fidelity switch, and the copy says the value is **read once
at gesture start** — so changing it mid-drag has no effect.

### 64.3 S10 — Window management

One card: `Keyboard & plugin windows`.

> Docked, with a Pop out control on each surface's header. Popping one out is
> remembered for next time.

Right side carries a **three-way segmented control**: `Panels` · `Windows` ·
`Show toggle` — each segment 88 × 26, active segment `rgba(255,255,255,0.15)`.

Not a switch or a checkbox: three mutually exclusive placements. `Show toggle`
means show the pop-out control itself.

### 64.4 S11 — Content

Two cards.

| Setting | Default | Copy |
|---|---|---|
| `Auto-stretch added audio` | **on** | Audio added from the library or uploads is stretched to project tempo when it has a steady beat; clips without a steady beat, and stems uploaded together, keep original timing. Off: always keeps original timing and does not set project tempo. Generated clips unaffected. |
| `Advanced content features` | **off** | Sound-design tools like the Wavetable Designer and Impulse Response Designer. Off, the menu items that open them are hidden. |

**This settles open decision #3.** The Wavetable and IR Designers are not core
surfaces — they sit behind a default-off preference that removes their menu
entries. Implement the setting first; keep the designers optional.

Note the asymmetry that matters for our defaults: auto-stretch is **on** by
default (audio conforms to the project), advanced tools are **off** by default.

## 65. S21 — hidden tracks `L`

Capture `screens/S21-hidden-track.jpeg`.

Hiding is **per track** and reversible from two places. Right-clicking a track name
opens the track menu:

```
Rename track
Color            ▸
Collapse controls
Duplicate
Hide & Mute Track
Delete
```

`Hide & Mute Track` does exactly what it says: the row leaves the arrangement **and**
is muted. On the demo that turned `Electric Keyboards` into a gap and renumbered the
remaining rows (`Soft Piano` became `1`).

### 65.1 The hidden-tracks affordance

| Element | Observed |
|---|---|
| Trigger | a pill at the right end of the `Add new track` row: `aria-label="1 hidden track"`, 53 × 28, showing just the **count** |
| Popover | opens **upward-left** from the pill, ≈ 220 px wide, radius 12 |
| Header | `Hidden tracks` + `×` |
| Row | colour swatch · track name · two icon buttons (reveal, unmute) |
| Bulk | `Unmute all` with a speaker glyph |
| Footer action | `Show All Hidden Tracks` with `shift alt H` |

Three things to copy:

1. **The count is the label.** There is no "Hidden tracks" text button eating space in
   the gutter — a single number appears only when the count is non-zero.
2. **Hide ≠ mute, but they are paired by default.** The menu entry is `Hide & Mute
   Track`; the popover then offers reveal and unmute separately, so the user can put
   the row back while it stays muted.
3. **The restore is discoverable without the menu.** The pill lives next to
   `Add new track`, i.e. exactly where a user looks after a row disappears.

## 66. S22 — the bar ruler `L`

Capture `screens/S22-ruler-zoom-levels.jpeg`.

```
┌ 1 ────── 9 ────── 17 ────── 25 ────── 33 ────── 41 ────── 49 ────── 57 ▲ 65 …┐
                                        ▲ section marker   ● playhead
```

| Property | Value |
|---|---|
| Ruler height | ≈ 20 px, above the clip band, full canvas width |
| Labels | bar number **every 8 bars** (`1, 9, 17, 25, …`) in a small muted chip |
| Ticks | one short tick at the midpoint of each 8-bar span (bar +4), full-height 1 px gridlines follow it down the canvas |
| Grid | every 4 bars, 1 px, rgba white ≈ 0.06 — barely visible, which is the point |
| Playhead | 10 px circular handle **plus** a downward triangle, and a 1 px vertical line through the whole canvas |
| Section marker | triangle only, no handle |
| Scrollbar | a thin horizontal track sits **below** the canvas, one step lighter |

Two densities were observed on the same timeline: ≈ 157 px per 8 bars (labels
`1…73` across the canvas) and ≈ 84 px per 8 bars (`1…137`). So zoom does change the
label density while keeping the 8-bar label rule constant.

**Zoom controls** live in the bottom-right cluster as `Zoom out` · `Fit to content` ·
`Zoom in`. Caveat for the next session: in this Chrome session, repeated synthetic
clicks on `Zoom in` sometimes left the timeline canvas painting **no fills and no
ruler text** until a reload. Treat that as a capture-environment risk to re-verify,
not as a product bug — it never reproduced on the first click.

## 67. S23 — section markers `L`

Capture `screens/S23-section-markers.jpeg`.

A section marker is a **blue triangle sitting on the ruler line**, distinguished from
the playhead by the absence of the round grab handle:

| | Playhead | Section marker |
|---|---|---|
| Handle | 10 px grey circle | none |
| Shape | triangle + vertical line | triangle only |
| Line through canvas | yes, 1 px | only at the marker's own column |

Between two markers the ruler shows a **subtle lighter band**, so a section reads as a
region rather than a point. That is the whole value of the element: the playhead is a
position, a section is an interval.

We currently draw markers as text chips in the ruler. The reference's version costs
less space and stays legible at every zoom because it carries no label — the name, if
any, is not drawn on the ruler.

## 68. S24 — loop region `L`

Capture `screens/S24-loop-region.jpeg`, 1250 × 1298 at DPR 1, taken in the OpenCode
browser pane.

Pressing `Loop` in the transport does two things at once:

1. the button turns **pink/red** (its only coloured state in the transport), and
2. the arrangement gains a **tinted band** spanning the loop, with a drag handle at
   its right edge sitting on the ruler line.

| Element | Observed |
|---|---|
| Loop button | 32 × 32, circular, glyph is a rounded-rectangle loop arrow |
| Active state | fill switches from neutral to the accent pink; the glyph stays the same shape |
| Region band | full-height tint over every track lane, low alpha, same hue as the button |
| Right handle | small square grip on the ruler line at the loop end, same pink |
| Edges | the region's boundaries are drawn as thin vertical lines through the whole canvas |

Dragging the right handle left from the song end to ≈ bar 55 shortened the region and
the tint followed live — the loop is a **ruler-level object**, not a clip property.

Notes that matter for the clone:

- The band tints **all lanes**, which is what makes it readable as a time range rather
  than a per-track selection. A per-row highlight would be ambiguous with clip
  selection (§47.1), which is also an outline.
- Loop state is persistent and orthogonal to playback: `Loop` stayed armed across
  selections, track changes and dock changes in the same session.
- No numeric readout of the loop length is shown anywhere — the region is read
  graphically off the bar ruler.

S25 (`clip selected with trim handles`) is still **OPEN**: a selected clip renders a
light 1 px outline and a brightened interior (see §47.1), but the trim grips only
appear under a real pointer hover, which the pane browser cannot synthesise — it
needs a pass in the CDP-driven Chrome.

## 69. S25 — clip selected, with trim grips `L`

Two captures: `screens/S25-clip-selected.jpeg` (full frame) and
`screens/S25-trim-grips-detail.jpeg` (3× crop of the selected clip).

Selecting a clip changes four things at once, and they are all visible in one frame:

| What | State when selected |
|---|---|
| Clip body | fill saturates; the waveform stays, the surround darkens |
| Outline | 1.5–2 px **light** border, inset from the clip bounds, all four sides |
| Trim grips | a narrow vertical bar flush against **each** end, same light tone as the outline |
| Header band | clip name at 13 px, top-left, unchanged by selection |
| Fade handle | a diagonal stub anchored to the **top-left** corner, drawn over the clip |
| Track row | the whole row takes a lighter fill — selection is echoed in the gutter |
| Magic Bar | chip switches to the clip (`Vocal Cuts`, swatch in the track colour) and the placeholder becomes clip-specific: `Sing a verse that calls back to the intro` |

Measured from the 3× crop: the clip is ≈ 170 × 59 px, the grips are ≈ 4 × 40 px
sitting ~3 px inside each end, and the outline sits ~1 px outside the body.

Notes:

- **Trim and fade are separate handles in different corners** — vertical grips on
  the ends, diagonal on the top-left. That is the whole reason the fade control does
  not need a menu entry of its own; `SHIFT F` (§36) is just the keyboard shortcut for
  the handle.
- The selection outline is **light on purpose**. Every track colour is a saturated
  fill, so a coloured outline would disappear on some tracks; white survives all of
  them. Compare §47.1, where the *right-click* selection is drawn in orange because
  it has to survive the clip menu on top of it.
- Hovering the clip header raises the help card shown in the frame — `Clip header`:
  "Drag to move the clip, double-click to open its editor, or right-click for more
  options — split, rename, recolor, and more." The three verbs are the entire clip
  interaction model.

## 70. S27 — clip info panel `L`

Capture `screens/S27-clip-info-panel.jpeg`, 1920 × 1277 — the panel needs ≈ 1550 px of
window or it opens past the right edge.

`Clip Info` in the clip menu (§47.1) swaps the right rail from the library to a
**song inspector** for the selected clip:

```
‹ Vocal Cuts                    ← back to the arrangement
[art]  13-Audio 0001 2024-07-08 121202_7 (Lead Vocal)
       4:29 · Aug 5, 2026
       Remix            ♡  ⊘  ⋯
[▶]  ▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮  ← waveform, green
──────────────────────────────────
        Info      |     Stems
Styles     [no styles]
Lyrics     No Lyrics
Comments and notes      ⌄
       [ Write a comment        ↗ ]
```

| Element | Detail |
|---|---|
| Rail width | ≈ 370 px, same column as the library (§19.1) — one rail, two panels |
| Title | the **source song** name, not the clip name — `… (Lead Vocal)` names the stem |
| Meta | duration `4:29` · date `Aug 5, 2026` |
| Primary action | `Remix` with a refresh glyph, above the artwork-adjacent icon row |
| Tabs | `Info` / `Stems` — the same split the library uses for songs vs parts |
| Sections | `Styles`, `Lyrics`, `Comments and notes`, each a flat card, not a table |

What this settles for the clone: a clip is not a dumb audio blob with a name — it
remembers the **generation it came from** (source song, date, duration, styles,
lyrics) and exposes that as first-class metadata. `Stems` on the second tab is the
same operation as `Get Stems` in the clip menu, surfaced again because the user
arrives here from a different direction.

## 71. S28 — clip colour submenu `L`

Capture `screens/S28-clip-color-submenu.jpeg` — 460 × 520 at 2×, showing the parent
row in its hover state with the submenu beside it.

| Property | Value |
|---|---|
| Panel | **196 × 350** at (817, 618) — opens to the **right** of `Clip Color`, top-aligned |
| Surface | same `#252529` as the parent menu, radius 10, same shadow |
| Header row | 40 px: current-colour dot · `Auto` · a **check** at the right |
| Grid | **5 × 8 = 40 swatches**, 36 × 36 circles, 4 px gaps |
| Ordering | five shades of one hue per row — the row *is* the hue family |
| Submenu arrow | `▸` on the parent row, and the parent row brightens while the child is open |

Three behaviours worth copying:

1. **`Auto` is the first row, not a swatch.** The default is "inherit the track
   colour", and it is drawn with the same dot-plus-check grammar as the colours, so
   "no explicit choice" reads as a choice.
2. **The palette is shades, not a colour picker.** Five steps per hue means a clip
   colour always stays in the same family as the track palette — no arbitrary hex,
   which is exactly what keeps the arrangement legible at a glance.
3. **The submenu is a child of the item, not of the menu.** It opens beside the row
   you hovered and closes when you leave that row, so the rest of the clip menu stays
   reachable with one small pointer move.

## 72. S29 — take lanes `PART` (empty state only)

Capture `screens/S29-take-lanes-empty.jpeg`.

`Take lanes` in the footer opens a strip **below the canvas** rather than a panel in
the right rail:

| Property | Value |
|---|---|
| Placement | full-width band under the arrangement, above the footer |
| Height | ≈ 90 px in the empty state (one line tall) |
| Empty copy | `Create a clip to see alternate takes here`, centred, muted 13 px |
| Close | `×` at the right end of the strip |

The strip is **state-driven by the selected clip**, not by a toggle alone: with the
strip open I selected six different clips in the demo (audio, MIDI, drum kit, string)
and every one reported the same empty copy. So this project was never re-generated
over itself — takes only exist where a clip was generated more than once.

That is worth recording as a **gap, not a finding**: the empty state proves the
feature and its placement, but we still have nothing on how takes render, stack, or
get auditioned. To finish S29 we need a clip that has been regenerated at least once
(use the Magic Bar to generate over an existing clip in the same region).

Also captured by accident and worth noting: selecting a **MIDI** clip changes the
Magic Bar placeholder to `Make a variation of this MIDI clip`, the third distinct
placeholder family after track-scoped (§54.1) and audio-clip-scoped.






