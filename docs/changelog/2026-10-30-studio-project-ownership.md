# Studio projects — ownership enforcement

**Date:** 2026-10-30
**Branch:** `feat/studio-shell`
**Surface:** `platform_api`

## Problem

Every `/web-music/studio/sessions/*` route accepted **any authenticated user** for
**any** Suno project id (`user_id` was discarded with `del user_id`). Since those
routes now write real arrangements through `save-project`, a user who learned
another user's project id could read or overwrite it.

## What changed

`platform_api/services/web_music_service.py`

- `_studio_project_owner(suno_project_id)` — looks up the owner in
  `studio_projects` (migration 174 stores `suno_project_id`).
- `_assert_studio_project_access(user_id, project_id)` — raises `ForbiddenError`
  when the project is indexed under a different user.
- `_ensure_studio_project_index(...)` — when a clip opens/creates its project
  (`create-or-load-project-for-clip`), a row is inserted with that Suno id and
  the song's title, so the project becomes checkable.
- Applied to: get session, save, read version, add/remove clips, rename.

**Compatibility:** a project that no row references (anything created before the
index existed) is still allowed, so legacy clip projects keep working. Projects
created or opened from now on are indexed and therefore checked.

## Verified live

With two real accounts (`somvannda@gmail.com` owner, `admin@mgfaceless.com` other)
against a project created through the platform:

| Request | Result |
|---|---|
| owner `POST …/save` | `200` |
| other `GET …/sessions/{id}` | `403 FORBIDDEN` |
| other `POST …/save` (hijack) | `403 FORBIDDEN` |
| other `GET …/versions/{id}` | `403 FORBIDDEN` |

`python -m py_compile` passes.

## Still open

- Admins are treated as ordinary users here; if support access is wanted it needs
  an explicit, audited bypass.
- Ownership is not checked inside musicapi's `/internal/*` routes; they rely on the
  internal token and are not exposed publicly.
