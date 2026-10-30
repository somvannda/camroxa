# Live Studio layout + token capture

Measured in an authenticated `suno.com/studio` session on 2026-10-30 via
`getBoundingClientRect()` / `getComputedStyle()` at a 1958×1245 viewport (DPR 1).

This is the first **measured** layout artifact for the programme. Treat every number
as a checkpoint, not a constant: capture again at 1280, 1024 and 768 before
implementing responsive rules.

## Design tokens

| Token | Value |
|---|---|
| `--color-background-primary` | `#101012` |
| `--color-background-secondary` | `#1c1c1f` |
| app shell background | `rgb(10, 10, 10)` |
| `--color-foreground-primary` | `#f7f4ef` |
| `--color-foreground-secondary` | `#c2c2c1` |
| `--font-sans` | `"Neue Montreal", ui-sans-serif, system-ui, …` |
| `--spacing` | `.25rem` (4 px base) |
| body font-size | 16 px |

> **Licensing:** Neue Montreal is a commercial typeface. We do **not** ship it.
> Our equivalent is a geometric grotesque from our own stack (see DESIGN_SYSTEM).

## Global frame

| Region | Geometry |
|---|---|
| Viewport | 1958 × 1245 |
| App shell | 1958 × 1245 at (0,0) |
| Header bar | height **52 px**; controls vertically centred with `y=10`, `height=32` |
| Main row | starts `y=52`, height 1141 |
| Track panel | width **260 px** (x 0→260) |
| Timeline | x 260 → 1958 |
| Transport/footer | bottom band, controls at `y≈1124–1157` |

## Header controls (left → right)

| Control | x | Size | Font |
|---|---|---|---|
| Project menu | 115 | 126×32 | 16 px |
| Undo | 254 | 36×32 | 13 px |
| Redo | 292 | 36×32 | 13 px |
| (spacer) | — | — | — |
| Loop toggle | 781 | 34×32 | 15 px |
| Back to Start | 817 | 32×32 | 15 px |
| Record | 851 | 32×32 | 16 px |
| Play | 885 | 32×32 | 16 px |
| Stop / forward | 919 | 32×32 | 15 px |
| Metronome | 963 | 32×32 | 15 px |
| Time `00:00.000` | 997 | 87×32 | 15 px |
| Bar.beat `001.1.1` | 1090 | 87×32 | 15 px |
| BPM `120 BPM` | 1641 | 70×32 | 15 px |
| Time signature `4/4` | 1713 | 50×32 | 15 px |
| Export menu | 1775 | 80×32 | 13 px |
| Open library | 1866 | 82×32 | 13 px |

Reading: transport is **centred**, while BPM/signature/export/library are
**right-aligned**. BPM and signature sit ~550 px right of the clock — a deliberate
gap separating "transport" from "session settings".

## Track panel

| Element | Geometry |
|---|---|
| Panel header toggles (`Collapse tracks`, `Collapse controls`) | 28×28 at `y=53` |
| Colour strip | 10×85 at `x=8` |
| Collapse-chevron | 16×32 at `x=24` |
| Track name | 89×17 at `x=48, y=98`, **11 px** |
| Mute (blank glyph) | 28×32 at `x=150` |
| Solo `S` | 28×32 at `x=179` |
| Arm `A` | 28×32 at `x=208` |
| Row extend control | 16×32 at `x=236` |
| Track row vertical rhythm | row starts `y=90`, next control band `y=126` |
| `Add new track` | full 260 px width column, from `y=174` to bottom |
| Master mute | 28×32 at `y=1124` and `y=1157` (two rows) |

## Prompt / Studio AI bar

| Element | Geometry |
|---|---|
| Prompt field | 335×38 at (941, 844) — horizontally centred, sits above the transport |
| `Ask Studio` submit | 42×42 at (1088, 842) |
| `Add to prompt` (+) | 32×32 at (798, 799) |
| Conversation toggle | 32×32 at (1352, 800) |
| Collapse | 32×32 at (1388, 800) |
| Model selector | 53×32 at (1331, 840) |
| Send | 32×32 at (1388, 840) |

## Onboarding overlay ("How do you want to start?")

Four cards, ~212–238 px wide and 204–232 px tall, around `y≈438–447`, spanning
`x≈544 → 1215`:

1. **Edit Your Song** — "Open a song from your library" (238×232)
2. **Drum & Bass Demo** — "A finished track to play, poke at and pull apart" (226×218)
3. **Upload Audio** — "Bring in a file from your computer" (212×204)
4. **Video Tutorial** — "Learn all the basics"

Plus `Empty Project` and `Browse Studio projects` entry points and a `Learn` link.

## Pillars (from the public landing page, tagline-level)

Recording · MIDI · Plugins · Instruments · Editing · Getting started — each has an
editorial section on `/studio-welcome`.
