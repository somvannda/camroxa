# Pixel parity log (D-022)

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
| Project chip | x115, 36 px, `#1c1c1e` | x110 (brand wordmark is wider) |
| Transport/time/tempo | grouped pills, 36 px | same grouping |
| Track panel | 260 px canvas `#141416`, head 29 px | same |
| Track row | 85 px, name x48 y100 11 px, controls 24×24, fader capsules `#1c1c1e` 167 px + 50 px pan arch at x28 y126, selected `#262628` | same |
| Colour strip | x8, 10 px wide | same |
| Ruler | 30 px `#101012`, labels 11 px centred, pitch 96 px at the captured zoom, labels thin 1/2/4/8 bars as it drops | same |
| Time ruler | 22 px `#1e1e20` band with dim labels (labels kept at AA contrast) | same |
| Playhead | 1 px `#4c4c4c` line with a cyan `#3dafff` ruler flag | same |
| Lane | 86 px, starts y82 | same |
| Clip | starts y84, 82 px tall, radius 10, label at +17 | same; waveform painted from the decoded clip audio (peaks cached per URL) |
| Footer band | 52 px `#0a0a0a`, control pills 36 px | same |
| Footer groups | tools and view icons grouped in pills, white Learn pill | same |
| Library rail | floating 360 px card, inset 8 px top/right/bottom, radius 12, `#101012` | same |
| Shell shrink | header/footer/timeline stop at the rail edge (x1321 at 1689) | same |
| Library head | 34 px: panel icon + title left, magnifier right | same (close X kept) |
| Library tiles | 64 px cards, 40 px icon squares (blue/purple/green/pink) | same |
| Library rows | 56 px art, title 15 px, meta 13 px, filter chips 30 px | same |
| Uploads level | Filter / New / liked / In Project / Stems chips | same; Filter and Stems disabled |
| Master strip | Main + fader + mute pinned at the panel bottom | same |
| Plugin dock | full-width band above the footer, slot cards on #141416 | same |
| EQ card | 450 px card: Band selector + switch, six shape buttons, yellow curve with per-band handles, Freq/Q/Gain knobs | same; four bands, real cascaded biquads |
| Footer chain | plugins as pills plus a compact add control; full Add Track Effects pill when empty | same |
| Plugin catalog | 760 px dialog on #171717, #1c1c1e cards, 14 px names, uppercase section label | same; preview art and Learn chips omitted (no assets/entries) |
| Track head | 29 px strip with an all-controls toggle left and a panel-collapse control right | left wired, right disabled (not built) |
| Learn popover | 206 px, 44 px rows, 11 px hints | same |
| Track options menu | 164 px, 33 px icon rows inside the panel; Color opens a flyout | same |
| Add-track menu | 208 px, 50 px rows, 24 px colour icon squares | same |
| Project menu | 212 px, 34 px icon rows, settings accelerator | same |
| Clip menu | 158 px, 38 px icon rows, 11 px shortcuts, 13 captured rows; Clip Color opens the S28 flyout | same; unbuilt rows disabled |
| Dialogs | 480 px, radius 24, padding 32, 24 px title, 44 px pills | same |
| Export toast | bottom-left 888 px banner on #1c1c1e, radius 16 | same |
| Selected track | tints the gutter row and its lane | same |
| Selected clip | white outline only; trim/fade grips on hover | same |
| Clip hover card | light 256 px card explaining drag/double-click/right-click | same |
| Clip info rail | 360 px card: hero, Remix, waveform, underlined tabs, section cards | same (facts kept in a Details card) |
| Song detail rail | 360 px card: hero + meta, actions, icon-only play, underlined tabs, cards | same (sticky mini-player still omitted, D-018) |

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

## Still to measure

- Song row subtitle copy (the capture shows a description line; we show tags).
- Generation prompt bar, history drawer and plugin dock cards — reference surfaces
  whose behaviour is not built, so they stay out of the chrome pass.
- Track panel panel-collapse control — captured, its collapsed layout is not.
