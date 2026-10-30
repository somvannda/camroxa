# Suno Studio — A to Z control audit

Every button, link, menu, panel and behaviour in Suno Studio, with its evidence
source and Camxora status.

**Evidence:** `B` bundle contract captured · `H` help centre / release notes ·
`L` live Studio · `?` not yet captured (do not implement).

**Status:** `done` · `partial` · `missing` · `blocked`

---

## A. Landing — `suno.com/studio`

| # | Control | Suno behaviour | Ev | Camxora |
|---|---|---|---|---|
| A1 | SUNO logo | link to home | H | done (app header) |
| A2 | "No project loaded ⋯" pill | project switcher / recent list | H | partial (static pill) |
| A3 | Undo / redo arrows | history for the loaded project | H | missing |
| A4 | Export | disabled with no project | H | partial (disabled) |
| A5 | Library toggle | opens the right drawer | H | done |
| A6 | "New empty project" card | creates a project, opens editor | H | done |
| A7 | Recent project card | opens that project | H | done (latest only) |
| A8 | "See all projects ›" | projects list page | H | partial (opens latest) |
| A9 | Song search | filters the song list | H | done |
| A10 | Filters chip (count) | filter by model/date/liked | H | partial (kind filter) |
| A11 | "New" dropdown | start from blank / upload / sample | H | partial (blank only) |
| A12 | Day group headers | Today / Yesterday / date | H | done |
| A13 | Song row — artwork, title, style | summary | H | done |
| A14 | Song row — key + BPM | e.g. `C minor · 143 BPM` | H | missing (not in our data) |
| A15 | Song row — likes | play count / like count | H | missing |
| A16 | "Edit in Studio" | opens project for that clip | B L | done |
| A17 | Project list source | `/api/project/me` returns workspaces, not Studio projects | B | blocked (`?` for real source) |

---

## B. Project view — header

| # | Control | Suno behaviour | Ev | Camxora |
|---|---|---|---|---|
| B1 | Project title ··· | rename, versions, archive, delete, share | B H | partial (rename wrapped) |
| B2 | Undo / redo | project history | H | missing |
| B3 | Skip to start | playhead to bar 1 | H | done |
| B4 | Rewind | nudge back | H | missing |
| B5 | Play / pause | transport | H | done (real audio) |
| B6 | Metronome | click track on/off | H | missing (no-op) |
| B7 | Time `00:00.000` | absolute time | H | done |
| B8 | Bar:beat `001.1.1` | musical position | H | done (derived) |
| B9 | `120 BPM` | project tempo, editable | H | partial (static) |
| B10 | `4/4` | time signature | H | partial (static) |
| B11 | Export | full song / range / multitracks | B H | blocked (`render-state`) |
| B12 | Library | opens drawer | H | done |

---

## C. Track panel (left)

| # | Control | Suno behaviour | Ev | Camxora |
|---|---|---|---|---|
| C1 | Track number + name | rename by double-click | H | partial (number only) |
| C2 | Volume | per-track gain | H | partial (visual) |
| C3 | S (solo) | mutes others | H | partial (visual) |
| C4 | M (mute) | silences track | H | partial (visual) |
| C5 | Arm / record | record into track | H | missing (no-op) |
| C6 | "＋ Add new track" | adds audio/MIDI track | H | done (audio only) |
| C7 | Track context menu | duplicate, delete, colour | ? | missing |
| C8 | Drag to reorder | reorder tracks | ? | missing |

---

## D. Timeline (centre)

| # | Control | Suno behaviour | Ev | Camxora |
|---|---|---|---|---|
| D1 | Bar ruler | numbered bars 1…n | H | done |
| D2 | Playhead | follows transport | H | done |
| D3 | Clip block | drag along lane | H | done |
| D4 | Clip trim handles | shorten from either edge | H | missing |
| D5 | Clip split | split at playhead | ? | missing |
| D6 | Clip delete | Delete / context menu | H | done |
| D7 | Clip context menu | duplicate, reverse, separate | ? | missing |
| D8 | Drop from library | drag a song onto a lane | H | done |
| D9 | Snap / zoom | grid snapping, zoom controls | H | partial (zoom slider) |
| D10 | Waveform in clip | audio preview | H | missing |
| D11 | Section labels | verse/chorus markers | ? | missing |

---

## E. Prompt bar (bottom centre)

| # | Control | Suno behaviour | Ev | Camxora |
|---|---|---|---|---|
| E1 | Prompt field | "Select a spot on the timeline and ask me to add a part" | H | blocked (`?` endpoint) |
| E2 | `+` | attach reference / clip | ? | missing |
| E3 | Model picker (`v6`) | choose generation model | H | partial (static) |
| E4 | Send | generates into the timeline | ? | blocked |
| E5 | Collapse / close | hides the bar | H | missing |

---

## F. Bottom bar / tools

| # | Control | Suno behaviour | Ev | Camxora |
|---|---|---|---|---|
| F1 | Master strip (`Main`) | master volume + meter | H | partial (volume only) |
| F2 | Tool icons (select / pencil / waveform) | editing modes | ? | missing |
| F3 | Folder / search / zoom icons | library, timeline search, zoom | H | missing |
| F4 | "Learn" + "What's This?" | onboarding tour | H | missing |
| F5 | Credit / plan notice | remaining credits | ? | missing |

---

## G. Library drawer

| # | Control | Suno behaviour | Ev | Camxora |
|---|---|---|---|---|
| G1 | All songs | your library | H | done |
| G2 | Liked | liked filter | H | missing |
| G3 | Stems | stem library | H | missing |
| G4 | Uploads | uploaded audio | H | missing |
| G5 | Workspaces | workspace list | H | missing |
| G6 | Projects | studio projects | H | missing |
| G7 | Drawer search / sort | filter inside drawer | H | missing |

---

## H. Menus & dialogs

| # | Control | Suno behaviour | Ev | Camxora |
|---|---|---|---|---|
| H1 | Project menu | rename, versions, duplicate, archive, delete | B H | partial (rename only) |
| H2 | Version history | list versions, restore / clone | B H | missing |
| H3 | Export dialog | full song / selected range / multitracks | B H | missing |
| H4 | Share / collaborators | invite, links, presence | B H | missing |
| H5 | Add-track menu | audio / MIDI / stems | H | missing |
| H6 | Clip menu | split, delete, duplicate | ? | missing |
| H7 | Onboarding card | "What's This?" | H | missing |

---

## I. Song menu → Edit actions (already audited)

Extend · Crop · Remove Section · Reverse · Adjust Speed · Find a Collaborator ·
Fade In · Fade Out · Replace Section · Get Stems / MIDI · Remaster · Open in
Studio · Open in Editor — contracts in `docs/studio-1to1.md`; Camxora has all
except Replace Section wiring and the section editor (`partial`).

---

## J. Behaviour & states

| # | Behaviour | Suno | Ev | Camxora |
|---|---|---|---|---|
| J1 | Autosave | no Save button, versioned writes | B | blocked (`state`) |
| J2 | Save conflict | `409` + `latest_version_id` | B | blocked |
| J3 | Save throttle | `429 too many saves` | B | blocked |
| J4 | Project != arrangement | `GET project` is metadata only | B L | done (documented) |
| J5 | Empty project state | "Add new track" prompt | H | done |
| J6 | Moderation error | `moderation_error_message` on render | B | missing |
| J7 | Credits gate | refuses when balance is 0 | B L | done (surfaced) |

---

## Open evidence gaps (must not be implemented until captured)

1. `state` document for `save-project` / version read.
2. Prompt-bar request when Suno adds a part.
3. `render-state` request/response (full + multitrack).
4. Clip context menu actions and keyboard map.
5. `/api/project/me` vs Studio project list.
6. Track context menu, MIDI track creation.
7. Toolbar icon set and modes.
