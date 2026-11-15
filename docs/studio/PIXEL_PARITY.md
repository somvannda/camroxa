# Pixel parity log (D-022)

> **Palette override (D-025, 2026-11-10):** the surfaces and interactive accents now use
> the CAMXORA palette — navy background/cards, product purple for controls — instead of
> the captured grays and pink/yellow. Geometry, spacing and type remain the captured
> values, and the pixel gate asserts the brand tokens.


Reference captures: `reference/screens/*.jpeg` at **1689×1277, DPR 1** (S52 for the
editor frame, S05 for the empty project, EXTRA-library-uploads for level-2 rows).
Targets live in `reference/METRICS.json`; the runtime probe reads
`public/studio-metrics.json`, which must stay identical.

Rule (D-022): **layout, spacing, control geometry, palette and type scale match the
capture.** The wordmark/logo and our copy are the only allowed differences, plus the
functional controls the capture does not show (listed below).

## Measured and matched

| Region | Captured | Ours |
|---|---|---|
| App body | `#111111`, text `#f7f4ef` | same |
| Header band | 52 px `#0a0a0a`, pills 36 px at y8, radius 999 | same |
| Narrow widths | 1024 keeps undo/redo and the centred prompt bar; 768 keeps the 260 px panel and transport, drops undo and secondary readouts and hides the Magic Bar | same |
| Under 768 | desktop-only gate card with Back to Create (S65) | same; our art, no photo asset |
| Project chip | x115, 36 px, `#1c1c1e` | x110 (brand wordmark is wider) |
| Transport/time/tempo | grouped pills, 36 px | same grouping |
| Track panel | 260 px canvas `#141416`, head 29 px | same |
| Track row | 85 px, name x48 y100 11 px, controls 24×24, fader capsule 167 px + the captured half-circle pan knob (pointer rotates with the value) at x28 y126 | same geometry; brand surface colours |
| Colour strip | x8, 10 px wide | same |
| Ruler | 30 px `#101012`, labels 11 px centred, pitch 96 px at the captured zoom, labels thin 1/2/4/8 bars as it drops | same |
| Time ruler | 22 px `#1e1e20` band with dim labels (labels kept at AA contrast) | same |
| Prompt bar | 645×97 card centred over the arrangement (x=652), 16 px above the shell body: attach +, panel/close tools, prompt line with a Tab hint, floating BETA at the top-right, model picker and send | same geometry; a removable track/clip chip and the v6 / v6-wild / v6-mini picker feed the assistant panel, where the take is auditioned or committed to the track (spends credits) |
| Conversation dock (S36) | 315 px bar docked bottom-left, chip row with a panel glyph, one-line prompt, attach +, model and send; invitation copy in the empty conversation area | same: the panel glyph opens the assistant and docks the bar at x=16/315 px; expanding returns it to the centre |
| Assistant panel | 360 px column inset 8 px under the header; the prompt, progress and per-take Commit/Audition actions (S37) | same; the shell reflows (tracks hidden, arrangement starts at 392 px) and the composer docks inside the column (24 px inset, 328 px wide, bottom 101) |
| Playhead | 1 px `#4c4c4c` line with a cyan `#3dafff` ruler flag | same |
| Lane | 86 px, starts y82 | same |
| Clip | starts y84, 82 px tall, radius 10, label at +17 | same; waveform painted from the decoded clip audio (peaks cached per URL) |
| Footer band | 52 px `#0a0a0a`, control pills 36 px | same |
| Footer groups | tools and view icons grouped in pills, white Learn pill | same |
| Library rail | floating 360 px card, inset 8 px top/right/bottom, radius 12, `#101012` | same |
| Shell shrink | the arrangement body stops at the rail edge (x1321 at 1689); header/footer stay full width and paint above it | same |
| Library head | 34 px: panel icon + title left, magnifier right | same: the title stays "Library" at every level, no close X (the header Library pill toggles the rail) |
| Library tiles | 64 px cards, 40 px icon squares (blue/purple/green/pink), first row at y=97 | same |
| Library rows | 56 px art, title 15 px, meta 13 px, filter chips 30 px | same; the Stems view reuses the upload row with a layer glyph, Play and Add |
| Songs toolbar | Filter ▾ / New / thumbs-up / In Project / Stems | same; the funnel opens All/Liked/In project and Stems opens the list |
| Empty library | centred “No songs found.” + 38 px Reset all filters pill | same (only when filters/search caused it) |
| Master strip | Main + fader + mute pinned at the panel bottom | same; clicking Main selects the master chain (S48) |
| History drawer | 300 px panel under the header, inset 8 px, on #101012, ‹ date › stepper | same; our version list/restore inside |
| Take lanes (S29) | footer control opens a 90 px band; empty copy Create a clip to see alternate takes here; takes stack 55 px, newest on top, active outlined with a green tick | same; regenerating over an existing audio clip stacks takes and clicking one makes it active (the clip audio follows) |
| Master chain (S48) | Limiter card with Lookahead / Pre Gain / Attack / Release / Link; the spare rail suggests EQ, Compressor and Reverb | same card geometry; the limiter controls drive the real master compressor (lookahead delay + pre-gain), EQ/Compressor add as Amount links, Reverb is disabled because the master bus does not render it |
| Plugin dock | full-width band above the footer, 448 px slot cards, preset pill | same; the compressor card has the captured transfer curve beside six knobs, EQ puts its curve left of the band controls, the pill opens the captured menu (Clear all settings, Save preset…, Default, starter sets and saved presets), and the spare rail shows Add effect plus three 30%-opacity ghost tiles (Compressor/Reverb/Delay) |
| EQ card | 450 px card: Band selector + switch, six shape buttons, curve with per-band handles, Freq/Q/Gain knobs | same two-column geometry (curve left, band controls right); controls/curve use the CAMXORA accent instead of the captured pink/yellow (user request) |
| Convolution card (S44) | IR slot with a 0–3 s impulse preview (1 s ticks), Halls › New England Hall breadcrumb, Mix/Gain/Pre/Width knobs | same two-column layout; 11 IRs in six groups, the picked impulse drives the real convolver (pre-delay and gain included) |
| Compressor sidechain (S43) | Sidechain menu lists None and every track twice: — Pre-fx / — Post-fader | same options; the key is stored on the slot and playback ducks the target from a control-rate analyser of the chosen tap |
| Popped-out plugin | large floating card from the external-link control | same: fixed 460 px (520 for EQ) at the bottom-right |
| Footer chain | plugins as pills plus a compact add control; full Add Track Effects pill when empty | same |
| Plugin catalog | 760 px dialog on #171717, #1c1c1e cards, 88 px device previews, 14 px names, Learn chips, uppercase section label | same; previews are our own traces/knobs per plugin family, not copied art, with a MY PLUGINS section above Audio effects |
| Plugin designer entry (S45) | dashed `Create new plugin` card closes the catalog; the bar takes a warm tint, seeds `Make me a new plugin…`, sends in its active state and keeps the current object as a chip | same geometry; the tint/send/chip use the CAMXORA accent (D-025) |
| Plugin designer result (S45) | three beats: restate + `Build it` / `Change something…`, completion copy, then a draggable `Warm Tape — Audio effect · Drag onto a track` card | same; the card is saved to MY PLUGINS, never auto-inserted, and can be dropped on a track row |
| Track head | 29 px strip with an all-controls toggle left and a panel-collapse control right | both wired; collapse folds the panel to a 44 px rail (own layout, never captured) |
| Learn popover | 206 px, 44 px rows, 11 px hints | same |
| Track options menu | 164 px, 33 px icon rows inside the panel; Color opens a flyout | same |
| Add-track menu | 208 px, 50 px rows, 24 px colour icon squares | same |
| Project menu | 212 px, 34 px icon rows, settings accelerator | same |
| My Projects modal | 786 px: tabs, pill search, Filters/sort, two-column cards, New Project first | same; card preview art is a generated placeholder |
| Clip menu | 158 px, 38 px icon rows, 11 px shortcuts, 13 captured rows; Clip Color opens the S28 flyout | same; unbuilt rows disabled |
| Dialogs | 480 px, radius 24, padding 32, centred 24 px title, bold lead, 44 px pills | same |
| Export toast | bottom-left 888 px banner on #1c1c1e, radius 16 | same |
| Selected track | tints the gutter row and its lane | same |
| Selected clip | white outline only; trim/fade grips on hover | same |
| Time selection (N-01) | not captured as its own frame; the strings (`Delete Time`, `Duplicate Time`, `Extend Selection Left/Right`) and the shortcut map describe it | accent-tinted band over the ruler and lanes with edge grips; right-click the ruler for loop, duplicate/delete time (all tracks or the focused one), range export and clear; `Shift ←/→` extends by a beat, `Esc` clears |
| Audio clip editor (S30, §81) | bottom band: `Clip Settings` column (280 px) beside a zoomed waveform with a bar ruler and the playhead; settings read Volume, Loop/Reverse, Pitch, Auto Stretch (On Beat / Transients / Start and End / Formant), Speed and Quantize | same band geometry as the MIDI editor; the whole column is live — Volume (signed dB, −24…+12), Loop and Reverse toggles, Pitch stepper (−12…+12), Stretch switch + modes + Formant, Speed ×½/×2 with a % readout, and Quantize with 1/2…1/32 chips, Triplets and a Quantize button — all persisted on the clip |
| Warp markers (S30) | white pennant heads on the waveform's top edge, one per marker, hairline stems, clipped to the clip bounds, density following the audio | same pennants and stems; `Transients` detects onsets from the decoded peaks, `On Beat` marks every beat, `Start and End` keeps the bounds; heads drag, click selects, `Ctrl A` selects all, `Shift Q` quantizes |
| Clip hover card | light 256 px card explaining drag/double-click/right-click | same |
| Clip info rail | 360 px card: hero, Remix, waveform, underlined tabs, section cards | same (facts kept in a Details card) |
| Song detail rail | 360 px card: hero + meta, actions, icon-only play, underlined tabs, cards, sticky mini-player | same (mini-player built per D-023; the More menu is ours, D-027) |
| Comments | collapsible “Comments and notes” card with a list and send arrow | same; posts project comments (new POST endpoint) |
| Remix | header pill that starts a variation generation | same; generates from the song style, adds the result to the library, disabled while running |

## Intentional divergences (recorded, not defects)

| Divergence | Why |
|---|---|
| CAMXORA wordmark and our copy | D-022 boundary: brand/copy stay ours |
| Save status, master meter, audition speed | wired status controls the capture does not show; meter and speed leave below 1600 px, save only when the rail is open below 1400 px |
| Record-input picker, count-in, metronome, Stop | wired recording/transport features (D-020/D-021) |
| Library close `X` | explicit close affordance in addition to the header toggle |
| Search collapses to the magnifier | matches the capture; it expands on focus/typing |
| Add is an icon button in rows | D-016 keeps Add next to drag without widening the measured row |
| Heal Edits / Get MIDI / Remove FX | present in the captured order but disabled with reasons; the behaviours are not built |
| Clip label colour | dark on pastel fills, white on the saturated reference fills (contrast-safe; the capture only shows white on purple) |
| Bounce row in the track menu | the reference strings name `Bounce` / `Exporting on track #` but the menu itself was never captured row by row; the action renders the track and downloads the mixdown until storage allows render-in-place (D-031) |
| Download MIDI row in the clip menu | N-05's strings name the action but the captured clip menu only shows `Get MIDI` (conversion); the row sits after Download WAV and keeps the 158 px menu width by carrying no hint text |
| Generate rows in the clip menu | Extend / Cover… / Remaster / Vocals… / Instrumental… / Mashup… / Replace… come from the reference's operation strings (GEN-014…GEN-019), but its clip menu was never captured; they follow our take model instead (D-033) and stay disabled when the required source or range is missing |

## Still to measure

- Song row subtitle copy (the capture shows a description line; we show tags).
- Generation prompt bar, history drawer and plugin dock cards — reference surfaces
  whose behaviour is not built, so they stay out of the chrome pass.
