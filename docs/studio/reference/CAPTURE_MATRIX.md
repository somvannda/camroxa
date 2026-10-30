# CAPTURE MATRIX — A→Z

Capture-only tracker. **No implementation until every `DONE`/`N/A` line is settled.**
Status: `DONE` captured with evidence · `PART` partial · `OPEN` not captured ·
`BLOCK` environment prevents capture.

Evidence codes: `M` measured geometry · `L` live observation · `B` bundle · `P` screenshot/pixel.

| # | Surface | What must be captured | Status | Evidence |
|---|---|---|---|---|
| **A** | **Entry** | | | |
| A1 | Signed-out marketing page | sections, CTAs, copy | DONE | L |
| A2 | Sign-in gate into Studio | redirect, query params | DONE | L |
| A3 | Signed-in entry | lands on project or welcome dialog | DONE | L |
| **B** | **Studio home** | | | |
| B1 | Project list layout | cards/table, sort, search, archive | OPEN | — |
| B2 | Resume / recent | card contents | OPEN | — |
| B3 | New project paths | empty / demo / upload / from song / video | PART | L (labels only) |
| B4 | Empty state | copy, CTAs | DONE | L |
| **C** | **Editor shell** | | | |
| C1 | Header controls | 15 controls + geometry + grouping | DONE | M §2 |
| C2 | Panel toggles | arrangement/library/lanes/bottom/chat/automation | PART | L §36 |
| C3 | Footer/transport | master, mute, learn, what's-this | DONE | M §7 |
| C4 | Panel widths | 260 track / 368 library / canvas resize | DONE | M §40 |
| C5 | Canvas surface | 1942×1141 renderer, DnD layer, anchor | DONE | M §28 |
| **D** | **Track panel** | | | |
| D1 | Row anatomy | colour, name, M/S/A, extend, meter | DONE | M §3 |
| D2 | Row metrics | 85 px row, 86 px step | DONE | M §28 |
| D3 | Track options menu | full item list | OPEN | right-click returns clip menu |
| D4 | Add-track menu | Audio/MIDI/Upload + accelerators | DONE | L §18.3 |
| D5 | Track types | audio, MIDI, instrument, bus? | PART | L |
| D6 | 17-track real project | structure evidence | DONE | L §41 |
| D7 | Hidden tracks | `SHIFT H`, `SHIFT ALT H` behaviour | PART | L (keys only) |
| **E** | **Timeline** | | | |
| E1 | Ruler | height, tick spacing, labels, loop bracket | BLOCK | canvas-drawn, needs pixels |
| E2 | Zoom steps | pixel-per-beat at each level | BLOCK | canvas-drawn |
| E3 | Lane geometry | lane height, clip height, gaps | OPEN | needs pixels |
| E4 | Playhead | style, drag, snap | OPEN | — |
| E5 | Grid density | `SHIFT 1/2` behaviour | OPEN | — |
| E6 | Markers | create/rename/colour | OPEN | — |
| E7 | Loop region | bracket, drag, `CTRL L` | OPEN | — |
| E8 | Selection | clip vs range vs takes | PART | L (shortcuts) |
| **F** | **Clip editing** | | | |
| F1 | Clip context menu | 13 items + accelerators | DONE | L §31 |
| F2 | Trim handles | affordance, cursors, min length | OPEN | — |
| F3 | Fade interaction | `SHIFT F`, handles | OPEN | — |
| F4 | Split | `CTRL E` semantics | OPEN | — |
| F5 | Warp markers | editor, quantize `SHIFT Q` | OPEN | — |
| F6 | Take lanes | select/promote (`ENTER`), preview | OPEN | — |
| F7 | Heal Edits | what collapses | OPEN | — |
| F8 | Clip FX | `Remove FX` chain UI | OPEN | — |
| F9 | Clip Info | panel fields | OPEN | item exists, panel not opened |
| **G** | **Magic Bar** | | | |
| G1 | Bar geometry | input, submit, model, conversation | DONE | M §5 |
| G2 | Placeholder states | empty vs loaded project | DONE | L §26 |
| G3 | Conversation panel | history UI | OPEN | — |
| G4 | Model picker | 4 entries + credits | DONE | L §6 |
| G5 | Generation result | pending/success/failure affordances | OPEN | needs paid run |
| **H** | **Inspector** | | | |
| H1 | Plugins section | list, add effect, presets | OPEN | — |
| H2 | Automation | CC + velocity lanes, point editing | PART | L §36 |
| H3 | Clip editor (audio) | waveform, warp markers | OPEN | — |
| H4 | Clip editor (MIDI) | piano roll, velocity | PART | L §36 |
| H5 | Take lanes panel | stack UI | OPEN | — |
| **I** | **Mixer / master** | | | |
| I1 | Master bus | fader, meter, limiter lookahead | PART | B |
| I2 | Per-track strips | layout | OPEN | — |
| I3 | Effects chain panel | select all/clear | PART | L §36 |
| **J** | **Library** | | | |
| J1 | Workspace list | 5 entries + counts | DONE | L §19 |
| J2 | Per-workspace view | song rows, actions | OPEN | click did not change panel |
| J3 | Search / liked / more | controls | PART | L |
| J4 | Audition keys | `↓ ↑ →` | DONE | L §36 |
| J5 | Uploads / stems tabs | presence | OPEN | — |
| **K** | **Project menu** | | | |
| K1 | Menu items | 9 items + accelerator | DONE | L §18.1 |
| K2 | Version History | panel + entries + actions | PART | L §25 |
| K3 | Share | copy + semantics | DONE | L §24 |
| K4 | Open copy in v1 Studio | behaviour | OPEN | — |
| K5 | Quick Start again | re-opens onboarding | DONE | L |
| **L** | **Export** | | | |
| L1 | Menu scopes | full / range / multitrack | DONE | L §18.2 |
| L2 | Export dialog | format, options, progress | OPEN | — |
| L3 | Multitrack output | file list/format | OPEN | paid |
| **M** | **Stems / MIDI / Personas** | | | |
| M1 | Get Stems flow | dialog, cost, result tracks | OPEN | paid |
| M2 | Get MIDI flow | dialog, result | OPEN | paid |
| M3 | Persona creation | UI, fields | OPEN | paid |
| **N** | **Settings** | | | |
| N1 | Performance | ghost drag semantics | DONE | L §22 |
| N2 | Window management | dock/popout | DONE | L §39 |
| N3 | Content | tempo policy, advanced features | DONE | L §29 |
| N4 | Remaining subsections | any others | OPEN | — |
| **O** | **Help & onboarding** | | | |
| O1 | Onboarding dialog | 4 cards + entries | DONE | L §10 |
| O2 | Learn menu | items + toggle | DONE | L §38 |
| O3 | What's This? | hover-help behaviour | PART | L |
| O4 | Keyboard overlay | full map | DONE | L §36 |
| O5 | Video tutorials | destinations | OPEN | — |
| **P** | **Collaboration** | | | |
| P1 | Share link semantics | view + fork | DONE | L §24 |
| P2 | Comments | presence, threading | OPEN | — |
| P3 | Presence/cursors | realtime (Ably) | OPEN | — |
| **Q** | **States** | | | |
| Q1 | Loading | skeletons/spinners per panel | OPEN | — |
| Q2 | Empty | captured for project + library | PART | L |
| Q3 | Error | network, moderation, credits | OPEN | needs induction |
| Q4 | Offline | banner/behaviour | OPEN | — |
| Q5 | Credits exhausted | blocking UI | OPEN | — |
| **R** | **Responsive** | | | |
| R1 | 1280 / 1024 / 768 | collapse rules, panel behaviour | BLOCK | no viewport resize |
| **S** | **Accessibility** | | | |
| S1 | aria labels | 38 controls | DONE | M §17 |
| S2 | Canvas semantics | how timeline is exposed | OPEN | — |
| S3 | Focus order | tab sequence | OPEN | — |
| **T** | **Contracts** | | | |
| T1 | Endpoints | 322 (81 studio) | DONE | B §12 |
| T2 | Request/response shapes | field-level | PART | B |
| T3 | State document shape | project JSON | PART | P (prior capture) |
| T4 | Error taxonomy | 827 strings | DONE | B §16 |
| T5 | UI strings | 9,679 | DONE | B |
| **U** | **Data model** | | | |
| U1 | Clip model | edits/takes/fx | DONE | L §33 |
| U2 | Track model | single instrument + plugins | PART | L |
| U3 | Project document | full schema | PART | P |
| U4 | Version cadence | seconds-level autosave | DONE | L §25 |

## Totals

| Status | Count |
|---|---|
| DONE | 33 |
| PART | 12 |
| OPEN | 30 |
| BLOCK | 3 |

## Capture order for the remainder

1. **Pixel pass** (unblocks E1–E3, R1): screenshots at each zoom level and each
   viewport; measure ruler band, lane/clip heights, tick spacing.
2. **Inspector pass** (H1–H5, F2–F9): open each per-track surface and each clip
   sub-surface, record structure.
3. **Dialog pass** (L2, N4, K4, J2): open every remaining dialog and record contents.
4. **Paid/state pass** (G5, M1–M3, Q3–Q5): requires credits and deliberate failure
   induction — needs owner approval.
5. **Collaboration pass** (P2, P3): needs a second account/session.

Steps 1–3 need no decisions. Steps 4–5 need approval or resources.
