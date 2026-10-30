# Studio must be a genuine 1:1 clone

**Rule:** every Studio feature ships only when it matches Suno Studio's real
behaviour, flow and UX. Camxora's colours/components are the only deliberate
difference.

## Evidence first

No Studio behaviour is invented. In order of preference:

1. **Suno's shipped bundle** — every `/api/...` call, request body and error code.
   Inventory: `docs/suno-studio-api-surface.md` (PR #470 branch).
2. **Suno help centre / release notes** — user-facing flow and wording.
3. **A live Studio session** — the final check before merging.

If none of the three exists, the feature is **not built**; it stays out of the UI
rather than shipping a guess.

## Verified contracts

| Call | Body / result |
|---|---|
| `POST /api/studio/create-project` | query `title`, `major_version`, `trigger`, `entry_source` → `{id,title}` |
| `POST /api/studio/create-or-load-project-for-clip/{clip_id}` | → `{id,…}` |
| `POST /api/studio/save-project` | `{project_id, state, title, base_version_id}` → `{version_id}`; `409` + `latest_version_id`, `429` too many saves |
| `GET /api/studio/project/{project_id}` | project metadata (no arrangement) |
| `GET /api/studio/{project_id}/version/{version_id}` | arrangement |
| `GET /api/studio/project_revision/{revision_id}` | revision |
| `POST /api/studio/project_revision/{revision_id}/clone` | `{title, major_version}` |
| `POST /api/project/{project_id}/clips` | `{update_type:"add"\|"remove", metadata:{clip_ids}}` |
| `POST /api/project/{project_id}/metadata` | `{name, description}` |
| `POST /api/studio/render-state` | `{title, lyrics, state, project_id, export_mode, start_beats, end_beats, downbeats, render_engine, encode_latents}` |
| `POST /api/edit/crop/{clip_id}/` | `{crop_start_s, crop_end_s, is_crop_remove, title}` |
| `POST /api/edit/fade/{clip_id}/` | `{fade_in_time, fade_out_time, title}` |
| `POST /api/clips/adjust-speed/` | `{clip_id, speed_multiplier, keep_pitch, title}` |
| `POST /api/clips/reverse-clip/` | `{clip_id, title}` |

## Behaviour rules

- **Autosave, no Save button.** Versioned writes debounced 3–5 s after the last
  edit; nothing is written while idle.
- **One version per edit burst**, with `base_version_id`; on `409` reload
  `latest_version_id` and replay.
- **No invented controls.** A control that has no matching Suno behaviour is
  either removed or disabled with a reason.
- **No local-only state pretending to be saved.** If it isn't persisted through
  `save-project`, the UI must not imply it is.

## Current gaps (must not be faked)

- `state` is captured — see [studio-state-schema.md](studio-state-schema.md).
  Hydration and autosave are implemented; the live round trip against a real
  Suno project is still a merge gate.
- Clips whose provider id cannot be mapped back to one of our songs are left
  untouched on Suno: they are neither played nor rewritten.
- Export still needs `render-state` wired in the UI (payload is captured).
- Version restore (`project_revision/{id}/clone`) is not surfaced.
