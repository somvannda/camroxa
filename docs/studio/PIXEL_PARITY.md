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
| Track panel | 260 px `#1c1c1e`, head 29 px | same |
| Track row | 85 px, name x48 y100 11 px, controls 24×24, faders 167+50 at x28 y126 | same (y125) |
| Colour strip | x8, 10 px wide | same |
| Ruler | 30 px `#101012`, labels 11 px centred, pitch 96 px at the captured zoom | same |
| Lane | 86 px, starts y82 | same |
| Clip | starts y84, 82 px tall, radius 10, label at +17 | same; waveform painted from the decoded clip audio (peaks cached per URL) |
| Footer band | 52 px `#0a0a0a`, control pills 36 px | same |
| Footer groups | tools and view icons grouped in pills, white Learn pill | same |
| Library rail | floating 360 px card, inset 8 px top/right/bottom, radius 12, `#101012` | same |
| Shell shrink | header/footer/timeline stop at the rail edge (x1321 at 1689) | same |
| Library head | 34 px: panel icon + title left, magnifier right | same (close X kept) |
| Library tiles | 64 px cards, 40 px icon squares (blue/purple/green/pink) | same |
| Library rows | 56 px art, title 15 px, meta 13 px, filter chips 30 px | same |
| Master strip | Main + fader + mute pinned at the panel bottom | same |
| Learn popover | 206 px, 44 px rows, 11 px hints | same |
| Track options menu | 164 px, 33 px icon rows inside the panel | same (inline colour swatches) |
| Add-track menu | 208 px, 50 px rows, 24 px colour icon squares | same |
| Project menu | 212 px, 34 px icon rows, settings accelerator | same |
| Clip menu | 158 px, 38 px icon rows, 11 px shortcuts | same (fewer rows, see below) |
| Dialogs | 480 px, radius 24, padding 32, 24 px title, 44 px pills | same |

## Intentional divergences (recorded, not defects)

| Divergence | Why |
|---|---|
| CAMXORA wordmark and our copy | D-022 boundary: brand/copy stay ours |
| Save status, master meter, audition speed | wired status controls the capture does not show; hidden below 1600 px |
| Record-input picker, count-in, metronome, Stop | wired recording/transport features (D-020/D-021) |
| Library close `X` | explicit close affordance in addition to the header toggle |
| Search collapses to the magnifier | matches the capture; it expands on focus/typing |
| Add is an icon button in rows | D-016 keeps Add next to drag without widening the measured row |
| Clip menu omits Heal Edits / Get MIDI / Remove FX | those behaviours are not built; the captured rows we ship keep their order |
| Clip label colour | dark on pastel fills, white on the saturated reference fills (contrast-safe; the capture only shows white on purple) |

## Still to measure

- Track panel head icons (sort left, expand right) — captured, not wired.
- Song row subtitle copy (the capture shows a description line; we show tags).
- Menus, dialogs and the export sheet geometry (not yet re-measured after D-022).
