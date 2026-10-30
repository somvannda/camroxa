# Studio clone — project index links to Suno

**Date:** 2026-10-30
**Branch:** `feat/studio-shell`
**Surfaces:** `platform_api`, `camxora.com`

## Problem

The landing page's "Pick up where you left off" card pushed
`/studio/editor?project=<studio_projects.id>`, but `studio_projects` is
Camxora's own table. That id does not exist on Suno, so the editor hydrated to an
empty project — the resume card never actually resumed anything. The library
dock hit the same wall, which is why its Projects tab was removed earlier.

## What landed

- **Migration `174_studio_project_suno_id`** — `studio_projects.suno_project_id`
  (nullable, indexed with `user_id`).
- **`create_studio_project`** now creates the Suno project first
  (`POST /api/studio/create-project` through musicapi), stores its id, then
  inserts the local index row. If Suno is unreachable the row is still created
  without an id, so nothing is lost.
- The project payload (and therefore `/web-music/studio/projects`) exposes
  `suno_project_id`; `WebMusicStudioProject` carries it too.
- **Landing** maps each card to `suno_project_id` and drops rows that do not have
  one, so a resume card can only point at a project the editor can open.

## Verified live

- `POST /web-music/studio/projects` → `201` with
  `suno_project_id: 06767aec-…` for local row `982b57dd-…`.
- `GET /web-music/studio/projects` → local row + Suno id; the legacy row
  ("Untitled session") comes back with `suno_project_id: null`.
- `GET /web-music/studio/sessions/06767aec-…` → `200`, matching title (no
  `state` until the first save, as recorded in the persistence changelog).
- Browser: `/studio` shows the new project under resume; clicking it lands on
  `/studio/editor?project=06767aec-…` and the header hydrates the title.

`npx tsc --noEmit` and `py_compile` pass. `check:ui` unaffected.

## Still open

- Suno's own project list is still not captured; our table remains an index of
  projects created from Camxora, not the full Suno list.
- Rows created before this migration keep `suno_project_id = null` and are
  hidden from the resume column.
