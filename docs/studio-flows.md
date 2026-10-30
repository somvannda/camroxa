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
| Project list source | `GET /api/project/me` returns workspaces, not Studio projects | B | ⚠️ still our own project table, but each row now stores its Suno `suno_project_id` (migration 174), so resume cards open real Suno projects; rows without one are hidden |

**Gap:** project list should come from Suno; key/BPM/likes columns missing.

## F2 — Create empty project

`POST /api/studio/create-project?title=` → `{id,title}` — `B`, `C` (verified 201).

## F3 — Open project for a clip

`POST /api/studio/create-or-load-project-for-clip/{clip_id}` → `{id}` — `B`, `C`.

## F4 — Project document / arrangement

`GET /api/studio/project/{id}` → `{state, title, latest_version_id, …}` — `B`, `L`.
Arrangement lives in versions: `GET /api/studio/{project_id}/version/{version_id}`
and `GET /api/studio/project_revision/{revision_id}` — `B`.
The `state` schema is captured in [studio-state-schema.md](studio-state-schema.md):
`timing` (bps, default 2 = 120 BPM), `tracks[]` (`amplitude`, `balance`, `solo`,
`mute`, `clips[]`), audio clips with `startBeats`/`endBeats`/`readStartBeats`
and `asset: {type:"clip", id}`.

Camxora: `C` — the project document hydrates the timeline (tracks, mixer values,
clip positions in beats). Clips whose provider id cannot be mapped to one of our
songs are left on Suno untouched.

## F5 — Save / autosave / versions

`POST /api/studio/save-project {project_id, state, title, base_version_id}`
→ `{version_id}`; `409` + `latest_version_id`; `429` too many saves — `B`.
No Save button; versions restorable via `project_revision/{id}/clone` — `H`, `B`.

Camxora: `C` — autosave 3 s after the last change, only once a real `state`
document has been read (never a synthesised one). `409` adopts
`latest_version_id` and retries once; `429` waits `retry_after` and retries.
Version restore (`project_revision/{id}/clone`) is not surfaced yet.

## F6 — Tracks

Left panel: numbered track, name, volume, S, M, arm, "+ Add new track" — `H`.
Camxora: `C` — volume, S and M drive the track's gain node (audible), arm is
visual only.

## F7 — Clips on the timeline

Drag from library onto a lane; drag along lane; trim; split; delete — `H`.
Camxora: add (click/drag) `C`, move `C`, trim `C` (edge handles adjust
`startBeats` / `endBeats` / `readStartBeats`), split `C` (context menu, at the
playhead, two arrangements sharing one source), duplicate `C` (context menu,
placed after the original), delete `C`, fades `C` (drag the selected clip's top
corners to set `fadeInBeats` / `fadeOutBeats`). Context menu: Duplicate, Split at
playhead, Delete. The ruler and empty lanes move the playhead `C`.

Clips live in the project `state`: an audio clip is
`{ asset: { type: "clip", id: <provider clip id> }, startBeats, endBeats,
readStartBeats, amplitude, mute, … }` and is persisted by `save-project` — `B`,
`C`. `POST /api/project/{id}/clips` is **not** the timeline: verified live, it
returns `404 Project not found` for a Studio project id, and Suno's Studio client
never calls it. Removing a clip here must not delete the song from the library.

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
gain, so faders, S, M and Main change the mix in real time. The same values are
written back as `track.amplitude` / `balance` / `solo` / `mute` and
`state.amplitude` by autosave.

## F11 — Export

`POST /api/studio/render-state` (full song / range) and
`render-state-multitrack` (multitrack download) — `B`, `H`.
Camxora: button disabled.

## F12 — Project menu

Rename (`/api/project/{id}/metadata`), versions, archive, delete — `B`/`H`.
Camxora: not surfaced. Verified live 2026-10-30: `POST /api/project/{id}/metadata`
returns `404 Project not found` for a Studio project id (same as the clip list),
so the Studio rename path is still unknown and must not be shipped as a guess.
The version **list** endpoint is also uncaptured; candidate read-only probes
(`/api/studio/project/{id}/versions`, `/api/studio/{id}/versions`,
`/api/studio/project_versions`, `/api/project/{id}/versions`) all returned
404/401.

## F13 — Collaborators

`/api/project/{id}/collaborators`, `/invite`, share links — `B`, `H`.
Camxora: none.

## F14 — Studio library dock

All songs / Liked / Stems / Uploads / Workspaces / Projects — `H`.
Camxora: library drawer with **Songs** and **Liked** tabs `C` (liked uses the
same `clipTrackKey` flags as the library). Stems, Uploads and Workspaces are not
surfaced yet. A Projects tab was built and removed: the project list returns
Camxora `studio_projects` ids, which are not Suno Studio project ids, so opening
one hydrated an empty editor — it must wait until the project ids can be mapped.

## F15 — Shortcuts

Space play/pause, undo/redo, delete — `H`.
Camxora: Space (play/pause), Delete (remove selected clip), Ctrl/Cmd+Z (undo),
Ctrl/Cmd+Shift+Z or Ctrl+Y (redo) `C`; the header carries Undo/Redo buttons with
the same history. Shortcuts are ignored while typing in an input.

## Next audit actions

1. Capture a **real non-empty version** (`state`) — one save from Suno Studio.
2. Capture the **prompt bar** request when Suno adds a part.
3. Capture the **export** request/response for full song and multitrack.
4. Confirm the **landing project list** endpoint (`/api/project/me` semantics).
