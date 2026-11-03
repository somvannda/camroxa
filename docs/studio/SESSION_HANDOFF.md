# SESSION HANDOFF — read this first, nothing else

State as of 2026-11-03. A new session should need only this file plus
`reference/SCREEN_MANIFEST.md` and `IMPLEMENTATION_ROADMAP.md`.

## Where things are

| | |
|---|---|
| Worktree | `C:\Users\Kong Somvannda\.local\share\opencode\worktree\d16337\studio-rebuild` |
| Branch | `feat/studio-rebuild` — clean, pushed |
| Web | `localhost:3103` (`npm run dev` in `camxora.com`) |
| Platform API | `localhost:8100` — **now runs from this worktree** |
| MusicAPI | `localhost:4003` |
| Capture archive | `docs/studio/reference/screens/` — 78 images |

## Two halves of the work

| Half | State |
|---|---|
| **Capture** (65 screens → screenshot + spec) | **60 DONE / 3 PART / 2 OPEN**, spec §1–§96. Remaining five are documented in `reference/CAPTURE_GAPS.md` and are not blocking. |
| **Build** (close gaps against that spec) | W1 ✅, W2 ✅ (all four), W3 mostly ✅ — see the roadmap for the live list. |

## Running the app (the part that costs time)

The API **must** run from this worktree or backend edits do not apply:

```
cd <repo root>
set "PYTHONIOENCODING=utf-8"
set "PLATFORM_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/camxora_pfm_sandbox"
python -m uvicorn platform_api.main:app --host 127.0.0.1 --port 8100 --log-level info
```

- `PYTHONIOENCODING=utf-8` matters: the access log contains `→` and crashes on cp1252.
- `set "VAR=value" && …` must be quoted; `set VAR=value &&` puts a trailing space in
  the DB name and the pool fails with `database "… " does not exist`.
- Don't `cd platform_api` — `platform_api` must be importable from the repo root.

**Local account** (sandbox DB, disposable):
`somvannda@gmail.com` / `StudioLocal!2026`

Helpers in `scripts/`:
- `inspect_api_env.py <pid>` — find which DB a running API actually uses.
- `seed_sandbox_user.py [email] [pw]` — create/reset a user in that DB.
- `seed_sandbox_song.py` — writes `public/seed/demo-loop.wav` and inserts a completed
  `suno_task`, so the library/provenance paths have real data. Note the three things
  the list endpoint filters on (`source='web_music'`, a `workspace_id`) and the two
  that make a clip playable (`stream_ready_*`, `package_status_*`).
- `verify_studio_conflict.py` — proves the 409 path against the live API.

## Traps that cost time

| Trap | Avoid |
|---|---|
| Access tokens live **30 minutes** | expect `401` mid-session; re-login with `POST /api/v3/auth/login` from the page |
| Background tab throttles `requestAnimationFrame` | the playhead will not advance; don't read that as a playback bug |
| `beforeunload` guard blocks navigation while a save is pending | accept the dialog via the browser tool, or open a new tab |
| Synthetic pointer events need `pointerdown` **on the element** | a press with no movement is a click; a move past 3 px is a drag |
| Stale closures in pointer handlers | read live data through refs (`tracksRef`, `clipsRef`) |
| PowerShell mangles `—`/`§` and nested quotes | write docs with the write/edit tools; put JS in a file |
| `next dev` re-adds `camxora.com/AGENTS.md` | commit it, or it stays dirty |

## Gates before every commit

```
cd camxora.com && npm run typecheck && npm run check:ui
```

`check:ui` rejects raw hex outside the palette (use `hsl(var(--token))`) and font sizes
outside the `.s-*` scale.

## What we deliberately did NOT copy from the reference

Written into the code where it matters: the reference has **no** save-status, conflict
UI, offline state or draft recovery (spec §93, §96). We built all four on purpose. Any
future "parity" work should not delete them.

## Next moves, in order

1. **W4.1** mastering chain audible (EQ/comp/drive on master + per track).
2. **W4.3** export matrix (mix, range, stems, per-track WAV, project JSON).
3. **G12 remainder** — workspaces/stems/uploads tabs need a stems-listing API first.
4. **G13/G14** — test runner (none installed) and an axe pass on the Studio routes.
5. Capture the five gaps opportunistically; do not spend a session on them.
