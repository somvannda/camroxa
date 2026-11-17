# Agent B — Studio parity audit (screens + strings vs the captured Suno Studio)

Date: 2026-11-16 · Branch: `qa/studio-parity-audit` · Base: `origin/main` @ `46f68025`

Scope: **parity only**. This audit asks "does our web Studio match the captured Suno
Studio, screen by screen and control by control?" It does not fix code, does not run
servers, and does not open the app.

Method:

- Sources of truth: `docs/studio/reference/screens/*.jpeg` (85 frames), `PAIRING.json`
  (73 entries), `docs/studio/compare/*.png` (46 of our captures), `FUNCTIONAL_STRINGS.json`
  (70 strings), `METRICS.json`, `CLONE_DEFINITION.md`.
- Every paired screen: both frames opened and compared by eye (reference frame vs ours),
  then the claim checked against the shipped component that renders it
  (`camxora.com/components/studio/**`, `lib/studio-*.ts`).
- Spec-only screens: the named spec opened and read; verdict reflects whether the spec
  asserts the *captured anatomy* or only behaviour.
- `node scripts/check-clone-parity.mjs` (read-only) reports 73/73 screens, 8/8 metrics,
  70/70 strings. The gate's limits are documented in §7 — it proves *presence*, never
  *placement*, and two of its passes are accidents (see §7).

---

## 1. Verdict summary

| Verdict | Count |
|---|---|
| MATCH | 15 |
| DELTA | 44 |
| CANNOT JUDGE | 14 |
| **Total** | **73** |

Of the 44 DELTAs, **13 are true control/order/string defects** (ranked in §9) and 31 are
capture-state problems (the paired frame shows a different state, a different surface, or
predates the component that renders it — §5). That split matters: a capture that shows
the wrong state is not evidence either way.

---

## 2. Screen-by-screen (73 rows, PAIRING order)

Evidence key: **C** = paired capture in `docs/studio/compare/`, **S** = named spec,
**N** = negative (surface must be absent).

| # | Screen | Surface | Ev | Verdict | Delta notes |
|---|---|---|---|---|---|
| 1 | S01 | Marketing signed out | S `navigation-smoke` | CANNOT JUDGE | Spec is behavioural (route/link smoke). No frame of our marketing page vs the reference hero, so visual parity is unproven. |
| 2 | S02 | Sign-in modal | S `navigation-smoke` | CANNOT JUDGE | No reference modal frame to diff. PAIRING's own note records a structural change (modal → `/login` route); that is outside the four allowed divergence classes, so it needs an explicit decision, not a silent pass. |
| 3 | S03 | Signed-in entry reopened | C `ours-editor-1689.png` | DELTA | Paired frame shows the *loaded demo editor*, not the reopened-entry overlay. Reference shows "How do you want to start?" with **5 tiles** (Edit Your Song · Drum & Bass Demo · Upload Audio · Video Tutorial · Empty Project) fanned/tilted, a **✕ at top-right** and a **"Browse Studio projects ›"** pill. Ours (`StudioOnboarding.tsx:81-105`) ships **3 flat tiles** (Empty arrangement / Create a song / Open a project), **no ✕**, **no Browse pill**, no demo/upload/video entry. |
| 4 | S04 | My Projects chooser | C `ours-my-projects.png` | DELTA | Our dialog is **translucent** — track rows and clips are legible through the panel (reference surface is opaque). Title is ~32 px (reference ~19 px). Close is a bare ✕ glyph; reference uses a 36 px filled circular button. Card avatar is a letter chip; reference uses cover art. Tabs/search/`Filters`/`Newest First` order matches. |
| 5 | S05 | Empty project | C `ours-empty-project.png` | DELTA | Our frame is the **start-chooser modal over a dimmed editor**, so the captured empty project (1 × "Audio Track" row + "Add new track" + idle Magic Bar) is never visible. Ours also shows 0 tracks where the reference has one Audio Track. |
| 6 | S06 | Onboarding overlay | C `ours-onboarding.png` | DELTA | **Evidence defect:** `ours-onboarding.png` is byte-identical to `ours-empty-project.png` (same sha256), so the pairing is wrong; the overlay is only visible in the empty-project frame. Content compared there: 3 tiles vs 5, no ✕, no Browse pill (see S03). |
| 7 | S07 | Project menu | C `ours-project-menu.png` | DELTA | (a) A "Project" **What's This card covers the menu's first three rows** (New Project / Open Project / Rename) — those rows cannot be verified at all and the card steals clicks. (b) Captured order is New Project · Open Project · Rename · Duplicate Project · Version History · Share Project · Open a copy in v1 · Studio Settings · Show Quick Start again; ours inserts **"Import project…"** (after Duplicate) and **"Send to Suno Sync"** (after Share) *inside* the captured sequence — additive rows that move captured rows. (c) `ctrl shift ,` wraps to two lines ("ctrl shift" / ","). |
| 8 | S08 | Version history | C `ours-version-history.png` | DELTA | Reference is a dot-and-rail list: newest entry as a highlighted row with a chevron ("09:00 AM"), older entries as dot + hairline ("09:42:06 AM", "09:41:26 AM"). Ours renders a single **pill row with a permanent "Restore" button** at its right plus explanatory prose. Timestamp format differs: ours always `h:mm:ss AM` (5:03:20 PM) where the reference's newest row is `hh:mm AM`. Subtitle has a trailing period ours-only. |
| 9 | S09 | Settings · Performance | C `ours-settings-performance.png` | DELTA | Same card and green toggle; deltas are chrome: title reads **"Studio settings"** (reference "Studio Settings") in a bold sans (reference uses a display serif), and the close is a bare ✕ instead of the reference's circular outlined button. The extra "Count-in before recording" card is additive (allowed). |
| 10 | S10 | Settings · Window management | C `ours-settings-window-management.png` | MATCH | "Keyboard & plugin windows" card, copy, and the `Panels · Windows · Show toggle` segmented control match control-for-control. Only the §9 chrome notes apply. |
| 11 | S11 | Settings · Content | C `ours-settings-content.png` | MATCH | Both captured cards present, same order, same toggles (auto-stretch On, advanced content Off). Copy is verbatim. |
| 12 | S12 | Share dialog + naming gate | C `ours-share-dialog.png` + S `studio-project-menu` | DELTA | Permission copy is **reworded**: reference "…create their own editable copy." / "Your original project will remain unchanged — others can't edit or affect your version."; ours "…**make** their own editable copy." / "Your project stays as it is — they cannot edit or change your version." (`StudioProjectMenu.tsx:971-976`). Ours adds a **raw URL input** (shows `http://localhost:3103/studio/shared/…` — a dev origin in a user-facing dialog) and a new claim "It expires in 7 days." "Done" is a bordered pill (reference: plain text). The **naming gate** (`Name project before sharing`, `Skip`/`Save`) is not in the paired frame; code shows it exists but with "before it is shared" vs the captured "before it's shared". |
| 13 | S13 | Learn menu | C `ours-learn-menu.png` | DELTA | Menu is too narrow (`globals.css` `.se-learn-menu{min-width:206px}`): **"Keyboard Shortcuts" wraps to two lines and "shift ?" wraps to two lines**, doubling row height. Reference is one line per row. YouTube Tutorials absent — sanctioned (see §8). |
| 14 | S14 | Keyboard shortcuts | C `ours-shortcuts.png` | DELTA | **Capture is stale** (7 rows) — code now ships 57 rows (`lib/studio-help.ts:163+`). Structural deltas remain and are what the reference settles: reference is a **two-column panel with a "Search shortcuts" field**, group headers (GENERAL / TRACKS / EFFECTS CHAIN / CLIP EDITOR · AUDIO / CLIP EDITOR · MIDI) and a header ✕; ours is a single centred column titled "Keyboard shortcuts" with **no search, no groups, no header ✕**, closing via a bottom "Close" pill. Key-cap chips are plain text in ours (reference: light rounded caps). |
| 15 | S15 | What's This? card | C `ours-editor-1689.png` | DELTA | Paired frame shows **no help card at all**, so the hovered-control card is unevidenced. Reference anchors a contextual card to the control (title "Tempo", control-specific body) with **no buttons**, plus a one-line "Click Learn to turn What's This? off." toast. Ours ships a contextual card too (`.se-help-card`, `StudioLearn.tsx:185`) but every capture instead shows the **first-run explainer** ("What's This?" + Dismiss/Turn off) parked bottom-right, where the reference has only the one-line toast. |
| 16 | S16 | Empty editor | C `ours-empty-project.png` | DELTA | Start-chooser modal blocks the captured empty editor (S05). Independently: reference empty state shows **no footer centre control** and only "Learn" at footer right; ours shows a permanent "+ Add Track Effects" and a 4-icon right cluster even with nothing loaded. |
| 17 | S17 | Loaded editor | C `ours-editor-1689.png` | DELTA | (a) **Transport is centred** in our header (`StudioHeader.tsx:190 .se-head-center`); reference flows undo/redo → transport at far left then time/BPM/sig rightwards. (b) Ours adds a Stop button and a record-input chevron; reference has `<<` (rewind) which we lack. (c) **Clip bodies show no waveform** in our frame although `StudioTimeline.tsx:330` renders one → stale capture. (d) Footer centre: reference shows the **master FX chips** ("EQ · Reverb · Stereo Utility · +"); ours shows a permanently **disabled "+ Add Track Effects"** (see §6). (e) Our demo project is missing the 13th track ("Drum Kit Main") visible in the reference. (f) Zoom/scroll differ wildly (ours 1–15 bars, reference 9–137). |
| 18 | S18 | Track row anatomy | S `studio-pixel` + METRICS | MATCH | Metrics are the reference's byte-for-byte (`studio-metrics.json` sha256 identical to `METRICS.json`: 85 row / 86 lane / 260 gutter / 96 bar / 36 pill / 52 footer) and asserted at 0 tolerance. No frame to diff corners/icons. |
| 19 | S19 | Track options menu | C `ours-track-options.png` | DELTA | Captured order: Rename track · Color ▸ · Collapse controls · Duplicate · Hide & Mute Track · Delete. Ours inserts **"Bounce track"** between Collapse controls and Duplicate (moves two captured rows). **Delete is red**; reference Delete is the same neutral colour as the rest (colour-role change, not just palette). Row layout (icons left, labels) matches. |
| 20 | S20 | Add track menu | C `ours-add-track.png` | DELTA | Rows and order match (Audio/MIDI/Upload). Icons differ (reference: download-into-tray for Audio, a piano/graphic for MIDI; ours: waveform glyph, letter "M"). Reference shows **accelerator key caps (A/M/U) as dark rounded chips** at the row's right edge; ours shows plain muted letters with no chip. Menu also opens **below** the "Add new track" row; reference opens upward over the trigger. |
| 21 | S21 | Hidden tracks | C `ours-hidden-tracks.png` | DELTA | Capture predates the current popover (`.se-hidden-pop{min-width:280px}`, with a close ✕ at `StudioTrackPanel.tsx:622`) — the frame shows a 245 px inline panel with **no ✕**. Content deltas that survive: reference bulk action reads **"Mute all"**, ours **"Unmute all"**; reference row actions are **two icons** (speaker + eye), ours two text pills ("Show" / "Mute"); reference shows the **`shift alt H` hint** next to "Show All Hidden Tracks", ours shows none (the binding itself exists, `lib/studio-help.ts` "Shift Alt H"). |
| 22 | S22 | Ruler zoom levels | C `ours-ruler-zoom.png` | DELTA | Our ruler draws labels and major gridlines only; the reference shows a **minor tick per bar** under the numbered ticks. Reference frame also shows a **grey circular marker handle** and the blue loop caret in the ruler; ours renders neither at this zoom. Label cadence can't be compared (different zoom: 1–29 vs 1–137). |
| 23 | S23 | Section markers | C `ours-section-marker.png` + S `studio-new-features` | MATCH (spec) | Paired frame shows **no section marker anywhere**, so the capture proves nothing; the spec stamps and re-reads `.se-section-marker` (`studio-new-features.spec.ts:219-240`). Capture needs refresh. |
| 24 | S24 | Loop region | C `ours-loop-region.png` | DELTA | Reference marks the range with pink flags at **both** ends in the ruler and tints the canvas; ours shows one purple flag at the end only, and the tint washes over the clips inside the range (reference tints empty canvas behind clips). Loop icon in our transport is boxed rather than a bare glyph. Help copy says "drag the **round** handle" while `.se-loop-handle` is an 8×16 rounded rect. |
| 25 | S25 | Clip selected / trim grips | C `ours-clip-selected.png` + S `studio-trim` | DELTA | Selected-clip white outline matches. But our frame shows an **empty plugin dock** ("No effects on this track yet." + Add effect) where the reference shows the dock populated with the master chain cards; and the clip body has no waveform (stale). Trim grips are hover-only by code and are not visible in either frame. |
| 26 | S26 | Clip context menu | C `ours-clip-menu.png` | DELTA | Captured rows all present **in the right relative order**, but **11 additive rows are interleaved** (Copy settings, Paste settings, Split on Transients, Make Beat 1, Create Section, Extend, Cover…, Remaster, Vocals…, Instrumental…, Mashup…, Replace…, Add FX…) so the menu is 25 rows / ~1000 px tall vs the reference's 13 rows / 435 px — several captured rows fall below the fold. Accelerators are capitalised ("Ctrl C", "Backspace") vs the captured lowercase ("ctrl C", "backspace"). Label defect: ours says **"Download WAV"**, the capture and `FUNCTIONAL_STRINGS.json` say **"Download .WAV"**. |
| 27 | S27 | Clip info rail | C `ours-clip-info.png` + S `studio-clip-info` | DELTA | Our rail header ("‹ Electric Keyboards") sits **on a second row under the 52 px header**; the reference puts it **inside the top bar**. Reference hero = cover art + full clip title + "4:29 · Aug 5, 2026" + heart/dislike/overflow cluster + **Remix** + a **play button with a green preview waveform**; ours = colour swatch + name + Remix + a bare green line, no art, no date, no like/overflow, no preview player. Rail width 340 px vs 300 px. "No Lyrics" vs captured "/no styles/" and "No Lyrics" casing. Our added Source/Details cards are additive. |
| 28 | S28 | Clip colour submenu | C `ours-clip-color.png` | DELTA | **The paired frame does not show the submenu** — Clip Color is merely hovered in the parent menu. Reference: "Auto" header with a check, then a 4×3 swatch grid (magenta / blue / orange ramps). Parity of the palette grid is therefore unevidenced. Accelerator casing and "Download WAV" deltas as S26. |
| 29 | S29 | Take lanes | C `ours-take-lanes.png` + S `studio-takes` | CANNOT JUDGE | Paired frame shows the **empty take-lane band** ("Create a clip to see alternate takes here"), not take lanes. Reference shows numbered take rows (2, 1) with per-take clips, an active row with a green edge, a delete ✕ in the gutter, and a floating promotion cluster (‹, ✕, ⌃⌄). Nothing of that is evidenced. |
| 30 | S30 | Stretch modes / warp markers | C `ours-warp-markers.png` + S `studio-warp` | DELTA | The subject of the screen is absent from our frame: the clip editor pane renders a **black canvas with one green line — no waveform, no warp pennants**, though `StudioAudioEditor.tsx` draws both. Reference "Clip Settings" header has a **collapse chevron + minus**; ours has only a ✕. Reference stretch modes are **stacked full-width rows with a selected highlight and ⓘ icons**; ours are three inline pills with no ⓘ. Reference pitch readout is two digits ("00"), ours "0". Our Formant/Speed/Quantize controls are additive. |
| 31 | S31 | MIDI clip editor | C `ours-midi-editor.png` | DELTA | Tabs (Velocity · Pitch Bend · Modulation) and order match. Reference has a **mini piano-roll overview strip** above the lanes with zoom ±; ours has none. Control bar: reference is `Loop · Quantize 1/2 · Key C Maj · Scale Off · View All` with **View All inline in the left group**; ours puts View All at the far right after a long run of added controls (Instrument, Chord, Arp, −12/+12, Clear, Import MIDI, Keys Off). Quantize default 1/8 vs 1/2 (state). |
| 32 | S32 | Modulation lane | C `ours-modulation-lane.png` | DELTA | Ours keeps the **piano key grid** (black/white note rows + keyboard ruler) inside an automation lane; the reference lane is a plain vertical-bar grid with a horizontal baseline and no note rows. Missing overview strip as S31. |
| 33 | S33 | Velocity lane | C `ours-midi-velocity.png` | DELTA | Same lane-chrome delta (note rows + keyboard ruler in ours, not in the reference). Velocity stems themselves are data-dependent and absent in both paired frames. |
| 34 | S34 | Prompt bar idle | C `ours-magicbar.png` | DELTA | **Capture is cluttered**: the track-options menu is open over the bar and the MIDI editor is docked, so the idle bar is only partly visible. Where visible it matches (609 px pill, ⊕, context chip row, ⧉/✕, v6 ▾, send). Ours adds a "Tab" hint; placeholder copy is ours (allowed). |
| 35 | S35 | Prompt bar attachment | C `ours-editor-1689.png` | DELTA | Same frame as S17, so the attachment state is unevidenced (no attachment chip in the frame). All S17 editor deltas apply. |
| 36 | S36 | Prompt conversation dock | C `ours-prompt-conversation.png` + S `studio-pixel` | DELTA | Left dock width, "Chat is powered by AI…" pill and the empty-state prose match. Composer deltas: reference has a **synthesiser/dock icon *and* an ✕** at the composer's top-right and an **enabled orange send**; ours has only an expand ↗, no ✕, and a disabled grey send. Reference also shows the Clip Settings pane below (state). |
| 37 | S37 | Generation result | S `studio-pixel` | MATCH (spec) | Spec asserts the result lands as a take and the chip reads the selected track (`studio-pixel.spec.ts:1377-1439`). No frame to diff the result styling. |
| 38 | S38 | Model picker | S `studio-pixel` | DELTA | Reference popover has a **"Create Custom Model" card (BETA, "Create a model based on your uploads (100 Credits)", ⊕)** above `ALL MODELS`, then v6 Pro · v6-wild Pro · v6-mini. Ours has 3 models only — the custom-model row was deliberately deleted (`3f96ba1d`), which removes a captured entry; that is not in the allowed-divergence list. |
| 39 | S39 | Plugin catalog | C `ours-plugin-catalog.png` + S `studio-pixel` | DELTA | Grid, section headers and 9 plugins match. Deltas: our header is missing the **⋯ overflow** button next to ✕; the "Create new plugin" tile is a **compact row** (reference: large dashed tile with ✦ and 140 px of height); every tile's preview art is the **same generic curve + 3 knobs** (reference previews are per-plugin, e.g. compressor curve, IR display); and the catalog ends with a **tenth, untitled blank tile**. |
| 40 | S40 | Plugin dock · one slot | C `ours-plugin-dock-eq-convolution.png` | DELTA | One EQ card renders, but our dock is the **selected track's** chain and our footer chips are track-scoped; the reference dock is the **master chain** and its footer chips are master-scoped (see §6). Card header adds a ⧉ expand (additive) and a second pink dot (modified marker). |
| 41 | S41 | Plugin dock · multiple | C `ours-plugin-dock-eq-convolution.png` | MATCH | Two cards side by side with the synthetic "Add effect" rail to the right — structure matches the captured multi-slot dock. (Card-internal deltas under S42/S44.) |
| 42 | S42 | EQ card | C `ours-plugin-dock-eq-convolution.png` | DELTA | Band select + toggle + 6 filter shapes + Freq/Q/Gain match. Ours adds **numeric readouts** under each knob ("1.0khz", "1", "0db") where the reference shows labels only, and the preset pill reads **"Default"** where the captured card reads "Custom". |
| 43 | S43 | Compressor sidechain | C `ours-compressor-sidechain.png` | CANNOT JUDGE | **No S43 reference frame exists** in `reference/screens` (the series jumps S42 → S44). The closest evidence is `S46-compressor-routing-list.jpeg`, and against that our list matches exactly: "None", then per-track `X — Pre-fx` / `X — Post-fader` pairs. Nothing to diff for the card itself. |
| 44 | S44 | Convolution card | C `ours-plugin-dock-eq-convolution.png` | DELTA | Reference body shows an IR display with `0s/1s/2s/3s` and the empty state **"NO ASSET LOADED"** in caps; ours shows the same ruler but a **select labelled "No impulse response"** and adds Gain/Pre/Width knobs. Header, preset stepper ‹ Default › and Mix knob match. |
| 45 | S45 | Plugin designer | S `studio-designer` | MATCH (spec) | Spec authors through the provider and saves a draggable plugin. Reference frames are entry + result crops; no paired visual. |
| 46 | S46 | Preset menu / stepper | C `ours-plugin-dock-eq-convolution.png` | DELTA | Stepper matches (‹ Default › with arrows, per `S44`/`S46-preset-menu`). **The menu itself is not open in our frame**; reference menu is "Clear all settings" · "Save preset…" · "Default". Code has both strings (`StudioPluginDock.tsx:845,856`) but ordering/placement inside the popover is unevidenced. |
| 47 | S47 | No mixer tool cluster | N | MATCH | Footer tool cluster is exactly 4 icons (Plugins, Automation, Clip editor, Take lanes) — no mixer (`StudioFooter.tsx:63-103`). Negative satisfied. |
| 48 | S48 | Master chain with limiter | C `ours-master-chain.png` + S `studio-master` | DELTA | Paired frame shows the **empty** master chain (Add effect + two grey placeholder tiles) — the Limiter card the screen is about is not in frame, although it is implemented with the captured five knobs (`LIMITER_PARAMS`: Lookahead, Pre Gain, Attack, Release, Link). Placeholder rail is also short of the reference's three (EQ / Compressor / Reverb — ours shows EQ + Compressor only). |
| 49 | S49 | Export menu | C `ours-export-menu.png` | DELTA | Captured three rows exist in order, but ours **prepends a WAV/MP3 format group and a "Normalise mix to −1 dBFS" row above them** (`StudioHeader.tsx:369-405`), moving every captured row down two slots. The What's This card also covers our first row ("Full Song") in the frame. `Project (JSON)` appended last = additive. Row icons differ from the captured ones. |
| 50 | S50 | Export scopes, no dialog | S `studio-export` | MATCH (spec) | Spec asserts a scope export starts with no dialog. | 
| 51 | S51 | Export result toast | C `ours-export-toast.png` + S `studio-export` | MATCH | Same banner, same bottom-left position, same ✕; only the scope word differs ("Full Song" vs captured "Multitrack"), which is state. |
| 52 | S52 | Library workspaces | C `ours-editor-library-1689.png` | DELTA | Tile grid (All Songs · Liked · Stems · Uploads) and order match. Deltas: **missing "See all ›" on Workspaces** (present on Studio Projects); workspace rows use a **letter avatar** instead of a cover image; project rows use a **☰ placeholder** instead of the captured mini-arrangement thumbnail; our tiles/glyphs are visibly smaller than the captured ones. |
| 53 | S53 | Library songs | C `ours-library-songs.png` | DELTA | **Capture predates the tag strip.** Reference rows read `V6 COVER · ● D minor · 128 BPM`; our frame reads `V6 PRO OK` and `V6 PRO OK · 0:04` (status + duration), while current code renders model+variant → `SongKey` → `SongTempo` (`StudioLibrary.tsx:739-746`). Code-side deltas the capture can't show: the key tag renders **"≈ D minor"** (estimated) where the reference shows a colour dot + key, and both tags render nothing when the client-side estimate is not confident → rows can lose key **and** tempo. |
| 54 | S54 | Share permission copy | C `ours-share-dialog.png` | DELTA | Same as S12: the permission sentence and the "unchanged" guarantee are reworded, and "expires in 7 days" is added. This screen's whole purpose is that copy, so it cannot pass on the current frame. |
| 55 | S55 | Comments and notes | S `studio-clip-info` | MATCH (spec) | Spec covers anonymous notes that survive a reload. Reference thread frame not paired. |
| 56 | S56 | Shared link logged out | C `ours-share-page-logged-out.png` + S `studio-share-page` | DELTA | The reference frame is the **marketing hero** ("Studio 2.0: Be a control freak." + an empty rounded panel) — it contains no share UI at all, so the surface cannot be compared. Ours renders the full site chrome plus a "READ-ONLY STUDIO SHARE" pill and is **stuck on "Loading project…"** in the frame. |
| 57 | S57 | Project loading blank | S `studio-smoke` | CANNOT JUDGE | Spec is a smoke path (move/undo/export) and does not assert the captured blank loading frame. |
| 58 | S58 | Empty library | C `ours-library-empty.png` | MATCH | "No songs found." with "Reset all filters" below, in the same panel position and order. |
| 59 | S59 | No conflict UI | N | MATCH | Reference has no conflict surface; our 409 reload/overwrite UI is additive per CLONE_DEFINITION §4 (and `studio-conflict.spec.ts`). |
| 60 | S60 | Moderation refusal | S `create-sample` | CANNOT JUDGE | Behaviour spec; the captured orange toast copy ("Couldn't generate that. / Your lyrics contain copyrighted material…") is not asserted by a paired frame. |
| 61 | S61 | Insufficient credits | S `studio-transforms` | CANNOT JUDGE | Spec covers a refused charge showing a credits card; the captured "You're out of credits" modal + auto-reload copy is not visually asserted. |
| 62 | S62 | Offline cold load | S `studio-offline` | CANNOT JUDGE | Spec covers draft replay and failed-write recovery, not the captured cold-load screen. |
| 63 | S63 | 1280 px | C `ours-editor-1280-audit.png` | DELTA | Both fit at 1280 and the 260 px gutter holds. But the frames compare **different surfaces**: the reference has the MIDI editor docked plus populated master chips; ours shows an undocked empty editor, so nothing below the arrangement was compared. Our footer right cluster has 6 icons (folder, zoom−, zoom+, fit, trash, link) vs the captured 4. |
| 64 | S64 | 1024 px | C `ours-editor-1024.png` | DELTA | Ours **drops the bar/beat readout ("001.1.1")** at 1024; the reference keeps both time and bar/beat at this width. Again a different bottom surface (no MIDI editor / no master chips). |
| 65 | S65 | 768 px / desktop gate | C `ours-gate-767.png` + S `studio-pixel` | MATCH | Same card structure (image block, title, prose, "Back to Create" pill) and the same 768 gate. Brand name, prose and the illustration are allowed divergences. |
| 66 | EXTRA-generation-refused | Generation refused (legacy copy) | S `studio-transforms` | CANNOT JUDGE | No reference frame exists for this entry at all (only `EXTRA-generation-refused-legacy.jpeg` is on disk), and the spec is behavioural. |
| 67 | EXTRA-generation-refused-legacy | Generation refused (legacy copy) | S `studio-transforms` | CANNOT JUDGE | Reference frame is a toast crop; no paired capture and the spec does not assert the toast copy. |
| 68 | EXTRA-library-uploads | Library uploads | C `ours-library-songs.png` + S `studio-library` | CANNOT JUDGE | **Wrong capture**: ours shows the Library root (workspace tiles + songs), not the Uploads view. Reference shows "‹ Uploads", per-row `↑ UPLOAD` tags (one with `135 BPM`) and the date groups. Toolbar order does match the reference (filter · New · liked · In Project · Stems). |
| 69 | EXTRA-library-song-detail | Library song detail | S `studio-components.test.tsx` | CANNOT JUDGE | Evidence is a component test, not a captured frame — it can prove behaviour, not layout. |
| 70 | EXTRA-project-load-error | Project load error | S `studio-smoke` | CANNOT JUDGE | Behavioural spec only; the captured error frame is not asserted. |
| 71 | EXTRA-restoring-last-project | Restoring last project | S `studio-smoke` | CANNOT JUDGE | Same — no frame, no anatomy assertion. |
| 72 | EXTRA-take-lanes-empty | Take lanes empty | C `ours-take-lanes.png` | DELTA | Copy and centring match, but ours renders a **close ✕ at the band's far right** that both reference frames (`S29-take-lanes-empty`, `EXTRA-take-lanes-empty`) lack — `StudioTakeLanes.tsx:37` always renders it, even with nothing open. |
| 73 | RESPONSIVE-gate-319px | 319 px gate | S `studio-pixel` | MATCH (spec) | Spec asserts the desktop notice below 768; the 767 capture confirms the same card at the boundary. |

---

## 3. Functional strings — placement, not presence

`FUNCTIONAL_STRINGS.json` has 70 strings; the parity gate finds all 70 in source. Below are
the ones where **placement, casing, order or the exact glyph** does not match the capture,
or where the gate's hit is not the visible control at all.

| String | Where the capture shows it | Where ours renders it | Delta |
|---|---|---|---|
| `Download .WAV` | Clip menu, row 11, between "Get Stems" and "Get MIDI" | `StudioEditorShell.tsx:6726` renders **"Download WAV"** (no dot) | **Visible label differs.** The gate passes only because line 3591 is a *comment* containing "Download .WAV". |
| `Mute all` (as captured; list says `Unmute all`) | Hidden-tracks popover, bulk action under the list | `StudioTrackPanel.tsx:651` renders **"Unmute all"** | Captured label is "Mute all"; ours is the inverse action name, and `FUNCTIONAL_STRINGS.json` records "Unmute all", so the string list itself disagrees with the capture. |
| `Show All Hidden Tracks` | Hidden-tracks popover, last row, with `shift alt H` at right | `StudioTrackPanel.tsx:655` — label right, **no accelerator hint** | Hint missing; binding exists. |
| `Studio Settings` | Project menu, row 8, with `ctrl shift ,` on one line | `StudioProjectMenu.tsx:115` label correct; the accelerator **wraps onto two lines** in the rendered menu (captured S07) | Wrapping defect in the menu width. |
| `Download MIDI` | Not in the captured clip menu (captured has `Get MIDI` only) | `StudioEditorShell.tsx:6739` adds a row after "Download WAV" | Additive row placed between two captured rows (`Download .WAV` and `Get MIDI`). |
| `Add FX` | Not in the captured clip menu | `StudioEditorShell.tsx:6762` ("Add FX…") sits **after** `Get MIDI`, before `Remove FX` | Additive row interleaved; captured `Remove FX` stays last, which is correct. |
| `Add a track` | A control/empty-state label in the reference (S20 area / empty surfaces) | Only appears inside onboarding prose: `StudioOnboarding.tsx:85` "Add a track and build from bar one." | **No control renders this label.** The gate's substring hit is prose. Placement unverified; likely missing. |
| `Hide & Mute Track` | Track options menu, row 5 | `StudioTrackPanel.tsx:361` (entity-encoded `&amp;`) | Renders correctly; position correct. No action. |
| `Duplicate` | Track options menu (row 4) **and** clip menu (row 3) | `StudioTrackPanel.tsx` / `StudioEditorShell.tsx:1045` | Correct in both. Additive "Bounce track" sits before the track-menu `Duplicate`, shifting it down one row. |
| `Clear all settings` / `Save preset` | Plugin card preset menu, rows 1 and 2 | `StudioPluginDock.tsx:845,856` | Present, but the popover is **not open in any capture** and the captured third row ("Default") is the current preset name — order/placement unverified. |
| `Normalise mix to` | Somewhere in the export flow (no frame shows it) | `StudioHeader.tsx:392` as a row **above** `Full Song` in the Export dropdown, reading "Normalise mix to −1 dBFS" | Captured three-row export menu has no such row; ours puts a captured string in a place the reference never shows, and pushes the captured rows down. |
| `Full Song` / `Selected Time Range` / `Multitrack` | Export menu rows 1–3, in that order, at the top | `StudioHeader.tsx:394-402` — same order but **below** the format group and normalise row | Order preserved, position moved (rule 4). |
| `Import project` | Reference project menu has no such row | `StudioProjectMenu.tsx:465` between `Duplicate Project` and `Version History` | Additive row inserted **inside** the captured sequence. |
| `New Project` / `Open Project` / `Rename` | Project menu rows 1–3 | Rendered, but **covered by the What's This card** in the only capture | Cannot be verified visually; card overlap is a defect in its own right. |
| `Keyboard Shortcuts` | Learn menu row 1, one line, `shift ?` at right; **and** the overlay title (capital S) | `StudioLearn.tsx:233` (Learn row, wraps to 2 lines) and `:298` h2 **"Keyboard shortcuts"** (lower-case s) | Casing differs on the dialog title; the Learn row wraps. |
| `What's This?` | Learn menu row 4 with `On` at right | `StudioLearn.tsx:255` | Correct row/order; the `On` reads `On`/`Off` — matches. |
| `No impulse response` | Reference convolution empty state reads **"NO ASSET LOADED"** | `StudioPluginDock.tsx:292` | Our string is in `FUNCTIONAL_STRINGS.json`, but the captured card uses different copy in the same slot. |
| `Search plugins` | Catalog search placeholder | `StudioPluginDock.tsx:1238` | Correct, same position. |
| `Create new plugin` | Catalog "MY PLUGINS" tile, large dashed tile with ✦ | `StudioPluginDock.tsx:1268` compact row with ⊕ and a "BETA" badge | Same place, different control shape. |
| `Comments and notes` | Clip info rail, collapsible card | `StudioClipInfo.tsx:248` | Correct place/order. |
| `Hidden tracks` | Popover title | `StudioTrackPanel.tsx:619` | Correct. |
| `Get Stems` / `Download .WAV` / `Get MIDI` / `Remove FX` | Clip menu tail, in that order | Same order (with additive rows between) | Order preserved. |
| `Extend` / `Cover` / `Remaster` / `Vocals` / `Instrumental` / `Mashup` / `Replace` | Not in the captured clip menu; these are transform actions reached elsewhere | Clip menu, rows 15–22, each with an ellipsis | Seven additive rows packed **into** the captured menu, which is the main reason the menu overflows. |

Strings verified present in the **same control, same order** as the capture: `New Project`,
`Open Project`, `Rename`, `Duplicate Project`, `Version History`, `Share Project`,
`Show Quick Start again`, `Name project before sharing`, `Copy Link`,
`Add effect`, `Audio`, `MIDI`, `Upload`, `Add new track`,
`Rename track`, `Collapse controls`, `Expand controls`, `Copy`, `Paste`, `Heal Edits`,
`Split`, `Clip Info`, `Clip Color`, `All Songs`, `Liked`, `Stems`, `Uploads`,
`New workspace`, `Search library`, `No songs found.`, `Reset all filters`, `Learn`,
`Learning Center`, `Sends`, `Wavetable Designer`.

Missing entirely: `Search shortcuts` (the reference's shortcut-search placeholder; our
dialog has no search field at all).

Strings present only as prose/comment (gate pass is accidental): `Download .WAV`,
`Add a track`.

---

## 4. Additional string/role deltas the capture settles

- Accelerator chips: the reference prints lowercase (`ctrl C`, `ctrl V`, `ctrl D`,
  `backspace`, `ctrl E`); ours prints title case (`Ctrl C`, `Backspace`).
- Delete colour: ours paints Delete red in the track menu; the reference does not
  (destructive colour is a *role* change, not a palette token).
- Dialog titles: "Studio settings" / "Keyboard shortcuts" vs captured "Studio Settings" /
  "Keyboard Shortcuts"; the settings title also loses the captured display-serif face.
- Hidden-track rows: text pills ("Show", "Mute") vs captured icon buttons (speaker, eye).

---

## 5. Captures that need refreshing

Every capture below either shows a different state than the screen it is paired to, or was
taken before the component that now renders the surface. Timestamps are useless here — all
46 files share mtime 2026-11-16 12:28 (checkout time); staleness is established from content
vs code.

**Wrong surface / wrong state (pairing cannot evidence the screen):**

| Capture | Paired to | Why it fails |
|---|---|---|
| `ours-onboarding.png` | S06 | Byte-identical to `ours-empty-project.png`; onboarding is not in it. |
| `ours-section-marker.png` | S23 | No section marker on the ruler at all. |
| `ours-take-lanes.png` | S29, EXTRA-take-lanes-empty | Shows the empty band, never the take rows. |
| `ours-clip-color.png` | S28 | Submenu closed; only the parent row is hovered. |
| `ours-master-chain.png` | S48 | Empty chain; the Limiter card is absent. |
| `ours-plugin-dock-eq-convolution.png` | S46 (preset menu) | Preset popover closed. |
| `ours-library-songs.png` | EXTRA-library-uploads | Shows the Library root, not Uploads. |
| `ours-share-page-logged-out.png` | S56 | Stuck on "Loading project…". |
| `ours-editor-1280-audit.png`, `ours-editor-1024.png` | S63, S64 | Compare different bottom surfaces (no docked MIDI editor, no master chips) at those widths. |
| `ours-magicbar.png` | S34 | Track menu open over the bar + MIDI editor docked. |
| `ours-editor-1689.png` | S03, S15, S17, S35 | Reused for four screens; evidences none of the four states (no overlay, no help card, no attachment chip). |

**Predates current code (content drift):**

| Capture | Screen | Drift |
|---|---|---|
| all arrangement frames (`ours-editor-1689`, `ours-clip-selected`, `ours-clip-menu`, `ours-loop-region`, `ours-ruler-zoom`, `ours-track-options`, `ours-add-track`, `ours-project-menu`, `ours-export-menu`, `ours-compressor-sidechain`, `ours-plugin-dock-*`, `ours-clip-info`, `ours-empty-project`) | S07, S17, S19, S20, S22, S24, S25, S26, S27, S40–S42, S44, S49 | Clip bodies render **no waveform** although `StudioTimeline.tsx:330` draws one; the frames were taken before peaks resolved. |
| `ours-hidden-tracks.png` | S21 | Shows the old 245 px inline panel; code now renders a 280 px floating popover with a close ✕. |
| `ours-library-songs.png` | S53 | Shows `V6 PRO OK` / `V6 PRO OK · 0:04`; code now renders model+variant → key → BPM. |
| `ours-shortcuts.png` | S14 | Shows 7 shortcut rows; code ships 57. |
| `ours-warp-markers.png` | S30 | Shows an undecoded clip pane; code draws the waveform + warp pennants. |
| `ours-project-menu.png`, `ours-export-menu.png`, `ours-clip-selected.png`, `ours-editor-1689.png` | S07, S49, S25, S17 | The first-run What's This card is parked over the menu/panel because `helpPaused` does not cover those menus (§6.2). |

---

## 6. Behaviour risks provable statically

These are things no capture can settle. Each has a file and line.

1. **Permanently disabled footer button** — `StudioFooter.tsx:119-128`: the centre
   "Add Track Effects" button carries `disabled` with the aria-label
   "Add Track Effects (use the dock above)". In every editor state where the chain is
   empty, the captured control slot holds a dead control. It also fires a tooltip that
   tells the user the control is not the one to use.
2. **Help card blocks menus** — `StudioEditorShell.tsx` (footer invocation):
   `helpPaused={Boolean(clipMenu || menuTrackId)}`. The project menu and the export menu
   are not in that condition, so the first-run card overlays them (visible in
   `ours-project-menu.png` and `ours-export-menu.png`) and eats the first rows' clicks.
3. **Footer chain is selection-dependent** — `StudioEditorShell.tsx:7314-7321`: the footer
   chips are the **master** chain only while the master strip is selected, otherwise the
   **selected track's** chain. The reference's footer row is always the master chain, so
   the same slot shows a different object depending on selection.
4. **Take-lane band always offers a close** — `StudioTakeLanes.tsx:37`: the ✕ renders even
   with no takes (`:41` empty copy), so the empty band carries an affordance the reference
   does not have and that closes nothing the user opened.
5. **Loop help text vs geometry** — `lib/studio-help.ts` (`loop`) says "drag the round
   handle"; `globals.css` `.se-loop-handle` is `8×16`, `border-radius:3px` — a rectangular
   flag. Copy and affordance disagree.
6. **Share copy asserts fixed terms** — `StudioProjectMenu.tsx:986-989` claims
   "…not live collaboration. It expires in 7 days." The API accepts `expires_days` 1–90
   and `permission: "view" | "edit"` (`platform_api/services/web_music_service.py:4060-4069`,
   `camxora.com/lib/studio-api.ts:602-610`). The dialog never surfaces the permission and
   hard-codes both claims; a share created with `edit` or a non-default expiry makes the
   dialog lie.
7. **Share link is rendered from `window.location.origin`** —
   `StudioProjectMenu.tsx:140-141`. The captured frame shows `http://localhost:3103/...`
   inside a user-facing dialog; any host mismatch leaks into what the user copies.
8. **Library tag strip can silently lose both tags** — `StudioSongKey.tsx:34` and
   `StudioSongTempo.tsx:40` return `null` when the client-side estimate is not confident.
   The captured row always shows key **and** BPM; ours is best-effort, and the key is
   prefixed "≈" (`StudioSongKey.tsx:37`) where the reference shows a coloured dot.
9. **Model picker lost a captured entry** — 3 options in `studio-pixel.spec.ts:1368-1375`;
   the captured "Create Custom Model" row was removed in `3f96ba1d`. Not in the
   allowed-divergence list.
10. **Clip menu overflow** — 25 rows in `StudioEditorShell.tsx:6719-6790`; captured rows
    `Download .WAV` / `Get MIDI` / `Remove FX` sit below the fold on a 1277 px-tall
    viewport once the additive transform rows are present.

---

## 7. Evidence integrity (meta)

- `PAIRING.json` has 73 entries, 53 captures, 32 specs, 2 negatives (some overlap), and the
  gate reports 100% coverage. Coverage is not parity: 14 rows above are covered but
  **cannot be judged**.
- **Duplicate file:** `ours-onboarding.png` ≡ `ours-empty-project.png` (sha256
  `928A7A81…`), so S06's evidence is a copy of S05/S16's.
- **Missing reference frames:** there is no `S43-compressor-sidechain.jpeg`;
  `EXTRA-generation-refused` has no frame (only `…-legacy`).
- **Gate holes** (`camxora.com/scripts/check-clone-parity.mjs:141-147`): it matches against
  raw file text, so (a) a **comment** satisfies `Download .WAV` while the button says
  "Download WAV", and (b) onboarding **prose** satisfies `Add a track` while no control
  uses that label. It also cannot see placement, order or casing — the whole of §3.
- `docs/studio/compare` has 3 captures nothing in `PAIRING.json` uses
  (`ours-wavetable-designer.png`, `ours-stems-live.png`, `ours-clip-menu-state.png`,
  `ours-editor-1280.png`), and `METRICS.json` is byte-identical to
  `public/studio-metrics.json` (verified).

---

## 8. Allowed divergences (not defects)

Listed once, so they are not counted again above:

- **Brand wordmark / logo / artwork:** SUNO → CAMXORA; the gate card's laptop photo →
  our bar-mark illustration; "SUNO Studio" → "CAMXORA Studio".
- **Palette:** pink/magenta accents → our accent, purple loop tint, clip fills, knob arcs,
  dialog surfaces. (Colour *roles* are not palette: see Delete-red and the master/Limiter
  dot under the deltas.)
- **Our prose:** onboarding copy, Magic Bar placeholders ("Describe a part to generate",
  "Add a warm reverb to this track"), settings descriptions, gate copy, "READ-ONLY STUDIO
  SHARE", empty-dock prose ("No effects on this track yet.").
- **Additive features:** save status + retry, 409 conflict UI, offline draft/replay, project
  JSON export/import, Wavetable/IR designers, FX sends, track groups A–D, master spectrum,
  MP3 export, clip comments, presence, audition speed pill, Suno sync, Bounce track,
  "Tab" hint in the prompt bar, per-clip transforms (Extend/Cover/Remaster/…), the
  first-run What's This explainer, "Fit to content" zoom.
- **Sanctioned absence:** the Learn menu's **YouTube Tutorials** row (product decision,
  `d7e356e4`).

Everything else — a moved or renamed captured control, a captured row deleted, a captured
string in a different menu — is reported as a delta above even where it is an addition,
because rule 4 allows additions that *add* surfaces, not additions that shift captured ones.

---

## 9. Deltas ranked by severity

| # | Severity | Screen(s) | Defect |
|---|---|---|---|
| 1 | High | S14 | Keyboard Shortcuts overlay is a single centred column with **no search, no group headers, no header ✕**, and a lower-case title; the reference is a two-column searchable panel with five groups and key-cap chips. (Row count is now 57 v ~60 — the paired capture is stale and must be retaken.) |
| 2 | High | S03, S06 (and S05/S16 by occlusion) | The start overlay ships 3 tiles instead of 5 (missing Edit Your Song · Drum & Bass Demo · Upload Audio · Video Tutorial), no ✕, no "Browse Studio projects ›", and it covers the empty editor so S05/S16 are unverifiable. |
| 3 | High | S17, S40, S48 | Editor chrome diverges: transport **centred** instead of in the left flow (with an extra Stop, missing `<<`), and the footer centre is a **disabled "Add Track Effects"** where the reference shows the master FX chips; the master chain ships empty on the demo project, so the captured chips and the captured Limiter card never render. |
| 4 | High | S12, S54 | Share dialog rewords the captured permission guarantee, adds a raw origin URL (localhost in the frame) and a fixed expiry claim, and offers no permission choice although the API supports `view`/`edit` and 1–90 days. |
| 5 | Medium-High | S07, S19, S26, S49 | Additive rows are interleaved **inside** captured menu sequences (Import project / Send to Suno Sync / Bounce track / 11 clip-menu rows / format toggle + Normalise above the export scopes), moving captured rows; plus `Download WAV` ≠ captured `Download .WAV`, title-cased accelerators, and a red Delete. |
| 6 | Medium | S27 | Clip info rail: header below the top bar instead of inside it, no cover art/date/like/overflow, no Remix-adjacent preview player, 340 px vs 300 px. |
| 7 | Medium | S21 | Hidden-tracks popover: "Unmute all" vs captured "Mute all", text pills instead of speaker/eye icons, missing `shift alt H` hint, and the closing ✕ of the current implementation is untested by any frame. |
| 8 | Medium | S13 | Learn menu is 16 px too narrow → "Keyboard Shortcuts" and its accelerator wrap onto two lines each. |
| 9 | Medium | S39, S44, S48 | Plugin surfaces: blank tenth catalog tile, generic per-tile previews, missing ⋯ in the catalog header, "No impulse response" where the captured card says "NO ASSET LOADED", two placeholder tiles instead of three. |
| 10 | Medium | S30, S31, S32, S33 | Clip editor / MIDI lanes: no overview strip, note-grid rows drawn inside automation lanes, stretch modes as inline pills instead of stacked rows with ⓘ, no collapse control in the Clip Settings header. |
| 11 | Low-Medium | S53, S52 | Library: key tag is an "≈" estimate (or absent) where the reference shows a dot + key, BPM is best-effort, project thumbnails are a ☰ placeholder, Workspaces has no "See all", workspace avatars are letters. |
| 12 | Low-Medium | S04, S08, S09, S32 | Chrome consistency: translucent My Projects panel, letter avatars, circular-vs-bare close buttons, `h:mm:ss` timestamps with a permanent Restore button, "Studio settings" casing and lost display-serif title. |
| 13 | Low | EXTRA-take-lanes-empty, S24, S38 | Empty take band carries an extra ✕; loop range marks one end and lacks the ruler handles; model picker dropped the captured custom-model row. |

---

## 10. Sign-off

- Screens audited: **73 / 73** (every entry in `PAIRING.json`), plus 12 reference frames
  read for context (`S05-zero-tracks`, `S12-share-naming-gate`, `S25-trim-grips-detail`,
  `S29-take-lanes-detail`, `S29-take-lanes-empty`, `S30-stretch-modes`, `S42`, `S44`,
  `S46-compressor-routing-list`, `S48-master-limiter`, `S59`, `S05`).
- MATCH **15** · DELTA **44** · CANNOT JUDGE **14**.
- Top 5 parity defects: §9 rows 1–5 (shortcuts overlay · onboarding tiles · transport +
  master-chain footer · share permission copy · captured-row displacement in menus).
- Report only: no code, CSS, spec or capture was modified; no server, browser or port was
  used; `G:\Developments\Projects\Camxora` untouched.
