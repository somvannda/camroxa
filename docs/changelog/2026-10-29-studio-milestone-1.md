# Studio clone — milestone 1 (project surface)

**Date:** 2026-10-29
**Branch:** `feat/studio-shell`
**Surface:** musicapi (Suno Studio wrappers)

## Goal

Rebuild Camxora Studio as a 1:1 clone of Suno Studio's structure and flow, keeping
Camxora colours/components. Milestone 1 is the project layer everything else
sits on: create a project, open the project for a clip, read it back, attach or
detach clips, rename it.

## Contracts captured from Suno's bundle

Extracted the same way as the editor calls (literal `/api/...` strings in the
shipped chunks):

| Suno call | Shape |
|---|---|
| `POST /api/studio/create-project` | query `title`, `major_version`, `trigger`, `extract_mode`, `num_stems_sent`, `entry_source` → `{ id, title }` |
| `POST /api/studio/create-or-load-project-for-clip/{clip_id}` | path only → `{ id, … }` |
| `GET /api/studio/project/{project_id}` | project document |
| `GET /api/studio/project_revision/{revision_id}` | revision document |
| `POST /api/project/{project_id}/clips` | `{ update_type: "add" \| "remove", metadata: { clip_ids } }` |
| `POST /api/project/{project_id}/metadata` | `{ name, description }` |
| `POST /api/studio/render-state` | `{ title, lyrics, state, project_id, export_mode, start_beats, end_beats, downbeats, render_engine, encode_latents }` |
| `POST /api/studio/render-state-multitrack` | opaque body → `{ download_url }` |
| `POST /api/studio/project_revision/{revision_id}/clone` | `{ title, major_version }` |

Full inventory (259 endpoints) lives in `docs/suno-studio-api-surface.md`.

## What landed

`musicapi/src/client.ts`:

- `createStudioProject`, `projectForClip`, `getStudioProject`,
  `getStudioProjectRevision`, `updateProjectClips`, `renameStudioProject`.

`musicapi/src/server.ts`:

- `POST /internal/studio/projects`
- `POST /internal/studio/projects/for-clip/:clip_id` (pinned to the account that
  owns the clip)
- `GET  /internal/studio/projects/:project_id`
- `POST /internal/studio/projects/:project_id/clips`
- `POST /internal/studio/projects/:project_id/metadata`

`npm run typecheck` clean.

## Next in this milestone

1. Platform proxy (`/web-music/studio/sessions/...`) so the web app never talks to
   musicapi directly, mirroring the existing `studio_operations` pattern.
2. Replace `app/(site)/studio/page.tsx` + `StudioEditorView.tsx` with the shell:
   left library dock (All songs, Liked, Stems, Uploads, Workspaces, Projects),
   centre timeline, right details, bottom transport.
3. Verify project create/load against a re-authenticated Suno pool account —
   Suno Studio is a paid surface, so this is the gating check.
