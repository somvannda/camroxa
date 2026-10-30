# Suno Studio — complete A→Z audit (v2)

Second pass: every button, link, icon, menu, panel, shortcut, state and edge
case. Nothing is implemented until its row has evidence.

**Ev:** `B` bundle contract · `H` help centre/release notes · `L` live Studio ·
`?` not captured yet (do not build).

**Cam:** `done` · `part` · `miss` · `blk` (blocked on evidence) · `n/a`

---

## A. Landing — `/studio`

### A1 Header
| # | Element | Type | Suno behaviour | Ev | Cam |
|---|---|---|---|---|---|
| A1 | SUNO wordmark | link | home | H | done |
| A2 | "No project loaded ⋯" | pill + menu | project switcher | H | part |
| A3 | Undo arrow | icon button | undo loaded project | H | miss |
| A4 | Redo arrow | icon button | redo | H | miss |
| A5 | Export | button | disabled without project | H | done (disabled) |
| A6 | Library | button + icon | right drawer | H | done |

### A2 Resume column
| # | Element | Behaviour | Ev | Cam |
|---|---|---|---|---|
| A7 | "New empty project" card | create + open | H | done |
| A8 | Recent project cards | open project | H | part (latest only) |
| A9 | Project thumbnail | artwork of latest version | H | miss |
| A10 | Project meta line | name + `3d. 8h ago` | H | part (name/group) |
| A11 | "See all projects ›" | projects list | H | part |
| A12 | Empty state | no projects yet | H | done |

### A3 Songs column
| # | Element | Behaviour | Ev | Cam |
|---|---|---|---|---|
| A13 | Section title | "Or start from one of your songs" | H | done |
| A14 | Search field | filter list | H | done |
| A15 | Filters chip | count + filter menu (model/date/liked) | H | part |
| A16 | New dropdown | blank project / from upload / from sample | H | part |
| A17 | Day headers | Today / Yesterday / date | H | done |
| A18 | Song artwork | thumbnail | H | done |
| A19 | Song title | opens details? | ? | part |
| A20 | Style summary | one line, truncated | H | done |
| A21 | Key + BPM | `C minor · 143 BPM` | H | miss (no data) |
| A22 | Like count / heart | social proof | H | miss |
| A23 | "Edit in Studio" | opens project for clip | B L | done |
| A24 | Row hover | highlight + actions | H | part |
| A25 | List scrolling | virtualised? | ? | n/a |
| A26 | Project list source | `/api/project/me` = workspaces | B | blk |

---

## B. Project view — header

| # | Element | Behaviour | Ev | Cam |
|---|---|---|---|---|
| B1 | Project title | inline rename | B | part |
| B2 | Title `⋯` | project menu (H1) | H | miss |
| B3 | Undo | history | H | miss |
| B4 | Redo | history | H | miss |
| B5 | Skip to start | playhead → 0 | H | done |
| B6 | Rewind | step back | H | miss |
| B7 | Play / Pause | transport | H | done |
| B8 | Metronome | click track | H | miss |
| B9 | Time display | `00:00.000` | H | done |
| B10 | Bar:beat | `001.1.1` | H | done |
| B11 | BPM | `120 BPM`, editable | H | part |
| B12 | Time signature | `4/4` | H | part |
| B13 | Export | dialog (H3) | B H | blk |
| B14 | Library | drawer toggle | H | done |
| B15 | Credits indicator | remaining credits | ? | miss |

---

## C. Track panel

| # | Element | Behaviour | Ev | Cam |
|---|---|---|---|---|
| C1 | Track number | index | H | done |
| C2 | Track name | double-click rename | H | part |
| C3 | Volume control | fader/knob | H | part |
| C4 | S | solo | H | part |
| C5 | M | mute | H | part |
| C6 | Arm | record-enable | H | miss |
| C7 | FX / sliders icon | insert effects | ? | miss |
| C8 | `＋ Add new track` | audio/MIDI menu | H | part |
| C9 | Track row select | highlights lane | H | done |
| C10 | Track context menu | duplicate/delete/colour | ? | miss |
| C11 | Reorder | drag track | ? | miss |
| C12 | Collapse track | height toggle | ? | miss |

---

## D. Timeline

| # | Element | Behaviour | Ev | Cam |
|---|---|---|---|---|
| D1 | Bar ruler | numbers + ticks | H | done |
| D2 | Grid lines | bar subdivisions | H | done |
| D3 | Playhead | follows transport, draggable | H | part |
| D4 | Clip block | shows title, colour | H | done |
| D5 | Clip waveform | audio peaks | H | miss |
| D6 | Clip drag | move along lane | H | done |
| D7 | Clip trim | handles at edges | H | miss |
| D8 | Clip split | at playhead | ? | miss |
| D9 | Clip delete | Delete key | H | done |
| D10 | Clip duplicate | ⌘D | ? | miss |
| D11 | Clip context menu | split/duplicate/delete | ? | miss |
| D12 | Drop from library | drag onto lane | H | done |
| D13 | Drop position | starts where dropped | H | part (appends) |
| D14 | Snap | grid snapping | H | miss |
| D15 | Zoom | slider/buttons | H | part |
| D16 | Section markers | verse/chorus | ? | miss |
| D17 | Loop region | loop bracket | H | miss |
| D18 | Selection box | multi-select clips | ? | miss |

---

## E. Prompt bar

| # | Element | Behaviour | Ev | Cam |
|---|---|---|---|---|
| E1 | Prompt input | "Select a spot…" | H | miss |
| E2 | `+` | attach reference | ? | miss |
| E3 | Model selector | `v6` dropdown | H | part |
| E4 | Send | generate into timeline | ? | blk |
| E5 | Expand / collapse | full prompt editor | H | miss |
| E6 | Close | hide bar | H | miss |
| E7 | Placement hint | "Select a spot on the timeline" | H | miss |

---

## F. Bottom toolbar

| # | Element | Behaviour | Ev | Cam |
|---|---|---|---|---|
| F1 | Master `Main` | volume + meter | H | part |
| F2 | Tool: select | pointer mode | ? | miss |
| F3 | Tool: pencil | draw clips/notes | ? | miss |
| F4 | Tool: waveform | audio edit mode | ? | miss |
| F5 | Tool: more | additional modes | ? | miss |
| F6 | Folder icon | open library/projects | H | miss |
| F7 | Search icon | timeline search | H | miss |
| F8 | Zoom icons | in/out | H | miss |
| F9 | Learn | tour / help | H | miss |
| F10 | "What's This?" card | onboarding, Dismiss / Turn off | H | miss |

---

## G. Library drawer

| # | Element | Behaviour | Ev | Cam |
|---|---|---|---|---|
| G1 | Tabs: All songs / Liked / Stems / Uploads / Workspaces / Projects | switch source | H | part (songs) |
| G2 | Search | filter drawer | H | miss |
| G3 | Sort | date/name | H | miss |
| G4 | Row drag | drag into timeline | H | done |
| G5 | Row click | add to selected track | H | done |
| G6 | Empty state | per tab | H | part |
| G7 | Close | hides drawer | H | done |

---

## H. Menus & dialogs

| # | Dialog | Contents | Ev | Cam |
|---|---|---|---|---|
| H1 | Project menu | rename, versions, duplicate, archive, delete, share | B H | part |
| H2 | Version history | list, preview, restore, clone | B H | miss |
| H3 | Export | full song / selected range / multitracks | B H | miss |
| H4 | Share & collaborators | invite link, members, roles | B H | miss |
| H5 | Add track | audio / MIDI / stems | H | miss |
| H6 | Clip menu | split, duplicate, delete, reverse | ? | miss |
| H7 | Delete project confirm | destructive confirm | H | miss |
| H8 | Restore version confirm | destructive-ish | H | miss |
| H9 | Onboarding | "What's This?" | H | miss |
| H10 | Moderation error | `moderation_error_message` | B | miss |

---

## I. Song menu → Edit (13 items)

Extend · Crop · Remove Section · Reverse · Adjust Speed · Find a Collaborator ·
Fade In · Fade Out · Replace Section · Get Stems / MIDI ▸ · Remaster ·
Open in Studio · Open in Editor — contracts in `docs/studio-1to1.md`; Cam: all
`part` (Replace Section not wired, Crop/Remove/Fade/Speed use Suno endpoints with
local fallback).

---

## J. Keyboard & pointer

| # | Shortcut | Action | Ev | Cam |
|---|---|---|---|---|
| J1 | Space | play/pause | H | miss |
| J2 | ⌘/Ctrl+Z | undo | H | miss |
| J3 | ⌘/Ctrl+Shift+Z | redo | H | miss |
| J4 | Delete/Backspace | delete clip | H | done |
| J5 | ⌘/Ctrl+D | duplicate clip | ? | miss |
| J6 | `S` / `M` | solo/mute focused track | ? | miss |
| J7 | Arrow keys | nudge clip | ? | miss |
| J8 | Drag threshold | move only after N px | ? | miss |
| J9 | Double-click clip | open editor/rename | ? | miss |
| J10 | Right-click | context menu | H | miss |

---

## K. States & edge cases

| # | State | Suno behaviour | Ev | Cam |
|---|---|---|---|---|
| K1 | Loading project | skeleton/spinner | H | part |
| K2 | Empty project | "Add new track" | H | done |
| K3 | Empty library tab | per-tab message | H | part |
| K4 | Signed out | gate to sign-in | H | done |
| K5 | Zero credits | generation refused with message | B L | done |
| K6 | Save conflict (409) | reload latest version | B | blk |
| K7 | Save throttle (429) | back off | B | blk |
| K8 | Autosave indicator | subtle saved state | H | blk |
| K9 | Unsaved changes on leave | warning | ? | miss |
| K10 | Render moderation error | message on export | B | miss |
| K11 | Network failure | retry/notice | ? | part |
| K12 | Long project | virtualised timeline | ? | miss |

---

## L. UX details

| # | Detail | Expectation | Ev | Cam |
|---|---|---|---|---|
| L1 | Hover states | buttons, rows, clips | H | part |
| L2 | Focus ring | keyboard visible | H | part |
| L3 | Cursor changes | grab/col-resize on clips | ? | miss |
| L4 | Drag ghost | translucent clip while dragging | H | miss |
| L5 | Snap feedback | guideline when snapping | ? | miss |
| L6 | Toast feedback | save/add/delete | H | part |
| L7 | Reduced motion | honour preference | H | miss |
| L8 | Screen reader labels | icon buttons labelled | H | part (`aria-label` on controls) |
| L9 | Contrast | text ≥ 4.5:1 | H | done (tokens) |
| L10 | Touch targets | ≥ 44 px on touch | H | miss (desktop sizes) |

---

## M. Data model

| # | Item | Source | Ev | Cam |
|---|---|---|---|---|
| M1 | Project | `/api/studio/project/{id}` (metadata) | B | done |
| M2 | Arrangement | `/api/studio/{project_id}/version/{version_id}` | B | blk |
| M3 | Save | `POST /api/studio/save-project` | B | blk |
| M4 | Versions | `project_revision/{id}` + `/clone` | B | miss |
| M5 | Clips in project | `/api/project/{id}/clips` | B | done |
| M6 | Render | `POST /api/studio/render-state` | B | blk |
| M7 | Multitrack | `POST /api/studio/render-state-multitrack` | B | blk |
| M8 | Collaborators | `/api/project/{id}/collaborators`, `/invite` | B | miss |
| M9 | Clip download | `/api/studio/clip/{id}/download` | B | miss |

---

## Coverage summary

| Area | Total | done | part | miss | blk |
|---|---|---|---|---|---|
| A Landing (26) | 26 | 9 | 6 | 3 | 1 |
| B Header (15) | 15 | 6 | 3 | 4 | 1 |
| C Tracks (12) | 12 | 2 | 4 | 6 | 0 |
| D Timeline (18) | 18 | 5 | 3 | 8 | 0 |
| E Prompt (7) | 7 | 0 | 1 | 5 | 1 |
| F Toolbar (10) | 10 | 0 | 1 | 9 | 0 |
| G Library (7) | 7 | 3 | 1 | 2 | 0 |
| H Dialogs (10) | 10 | 0 | 1 | 7 | 0 |
| I Edit (13) | 13 | 0 | 13 | 0 | 0 |
| J Shortcuts (10) | 10 | 1 | 0 | 9 | 0 |
| K States (12) | 12 | 3 | 3 | 3 | 3 |
| L UX (10) | 10 | 1 | 4 | 5 | 0 |
| M Data (9) | 9 | 2 | 0 | 2 | 5 |

## Evidence gaps (blocking)

1. `state` for `save-project` + version read (M2/M3, K6–K8, B13/H3).
2. Prompt-bar request (E4).
3. `render-state` + multitrack payloads (M6/M7).
4. Clip context menu, duplicate/split semantics (D8/D10/D11/H6).
5. Studio project list source (A26).
6. Track context menu / MIDI tracks (C8/C10/H5).
7. Toolbar modes and icons (F2–F5).
