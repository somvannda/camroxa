# Suno Studio — flow audit

Audit first, document, then implement. Each flow is only "done" when it matches
Suno's real behaviour and the evidence is recorded here.

**Evidence key:** `B` = shipped bundle (endpoint/body captured), `H` = help centre
or release notes, `L` = live Studio session, `C` = Camxora already implemented.

## F1 — Studio landing (`/studio`)

| Step | Suno behaviour | Evidence | Camxora |
|---|---|---|---|
| Header | SUNO logo, "No project loaded ⋯", Export, Library | H | `C` (brand in app header, project pill, Export, Library) |
| Resume column | "Pick up where you left off": New empty project + recent projects, "See all projects" | H | `C` (new card, latest project, link) |
| Songs column | "Or start from one of your songs": search, Filters, New, grouped by day, per-row title/style/key/BPM/likes, "Edit in Studio" | H | `C` minus key/BPM/likes |
| Project list source | `GET /api/project/me` returns workspaces, not Studio projects | B | ⚠️ uses our own project table |

**Gap:** project list should come from Suno; key/BPM/likes columns missing.

## F2 — Create empty project

`POST /api/studio/create-project?title=` → `{id,title}` — `B`, `C` (verified 201).

## F3 — Open project for a clip

`POST /api/studio/create-or-load-project-for-clip/{clip_id}` → `{id}` — `B`, `C`.

## F4 — Project document / arrangement

`GET /api/studio/project/{id}` → metadata only (`owner_user_id`, `title`,
`created_at`, `updated_at`, `archived`) — `B`, `L`.
Arrangement lives in versions: `GET /api/studio/{project_id}/version/{version_id}`
and `GET /api/studio/project_revision/{revision_id}` — `B`.

**Gap:** not hydrated; `state` schema unknown.

## F5 — Save / autosave / versions

`POST /api/studio/save-project {project_id, state, title, base_version_id}`
→ `{version_id}`; `409` + `latest_version_id`; `429` too many saves — `B`.
No Save button in the UI; versions restorable via `project_revision/{id}/clone` — `H`, `B`.

**Gap:** not implemented (blocked on `state`).

## F6 — Tracks

Left panel: numbered track, name, volume, S, M, arm, "+ Add new track" — `H`.
Camxora: `C` — volume, S and M drive the track's gain node (audible), arm is
visual only.

## F7 — Clips on the timeline

Drag from library onto a lane; drag along lane; trim; split; delete — `H`.
Camxora: add (click/drag) `C`, move `C`, delete `C`; trim/split missing.
Add/remove persist to the project via `/api/project/{id}/clips` — `B`, `C`.

## F8 — Transport

Header: rewind, play, metronome, `00:00.000`, bar:beat, BPM, time signature — `H`.
Camxora: play/pause + clock + bar:beat `C` (driven by one audio clock, Space
toggles it); metronome no-op; BPM static 120.

## F9 — Prompt bar

"Select a spot on the timeline and ask me to add a part", `+`, model picker, send — `H`.
Camxora: visual only. **Do not ship until the endpoint is captured.**

## F10 — Mixer / master

Master strip, per-track faders — `H`.
Camxora: `C` — per-clip streams play through per-track gain nodes into a Main
gain, so faders, S, M and Main change the mix in real time. Gains are local
playback state; Suno stores them in the uncaptured `state` document.

## F11 — Export

`POST /api/studio/render-state` (full song / range) and
`render-state-multitrack` (multitrack download) — `B`, `H`.
Camxora: button disabled.

## F12 — Project menu

Rename (`/api/project/{id}/metadata`), versions, archive, delete — `B`/`H`.
Camxora: rename wrapped, not surfaced.

## F13 — Collaborators

`/api/project/{id}/collaborators`, `/invite`, share links — `B`, `H`.
Camxora: none.

## F14 — Studio library dock

All songs / Liked / Stems / Uploads / Workspaces / Projects — `H`.
Camxora: library drawer with songs only.

## F15 — Shortcuts

Space play/pause, undo/redo, delete — `H`.
Camxora: Space (play/pause) and Delete (remove selected clip) `C`; undo/redo
missing.

## Next audit actions

1. Capture a **real non-empty version** (`state`) — one save from Suno Studio.
2. Capture the **prompt bar** request when Suno adds a part.
3. Capture the **export** request/response for full song and multitrack.
4. Confirm the **landing project list** endpoint (`/api/project/me` semantics).
