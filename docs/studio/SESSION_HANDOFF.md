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
| **Build** (close gaps against that spec) | W1 ✅, W2 ✅ (all four), W3 ✅ (9 done, G12 partial), W4 ✅ 1/3/4 — only the stems-dependent items remain. |

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

## Tests and CI (added 2026-11-04)

| Layer | Command | Count |
|---|---|---|
| unit (pure helpers) | `npm test` | snap, meter, draft, seed, WAV encode |
| component | `npm test` | header, footer, library, provenance strip, track panel |
| API contract | `npm test` | paging, version field, 409 mapping, 204 |
| e2e | `npm run test:e2e` | smoke (move/undo/export), persistence across reload, library tabs + filter + workspaces, project menu rename + persistence, metric parity, axe ×3 (home, editor, library drawer) |

CI job `camxora-web-checks` in `pr-checks.yml` runs typecheck + check:ui + `npm test` on
any PR touching `camxora.com`. The e2e specs are not in CI yet — they need the app plus
the platform API and a database, which the workflow does not provision. They build their
own fixtures through the API (`tests/e2e/studio-fixture.ts`) and leave those fixture
projects in the sandbox database, so the sandbox accumulates test projects by design;
they never touch a non-sandbox account.

**Backend suite:** `python -m pytest platform_api/tests -q` → 3159 passed, 2 failed at
`dbe0245d`. Both failures pre-date D-009 and are unrelated (they assert on retired plan
machinery): `test_user_spend_service.py::test_user_spend_flags_over_allowance_and_margin_risk`
(expects a `song` meter) and
`test_web_music_batch_access.py::test_legacy_ledger_unlocks_pack_balance` (expects the
legacy pack unlock to win with the v3 flag off). Fixing them is a separate billing
cleanup; do not read them as studio regressions.

`beforeunload` note: when a save is pending the editor blocks navigation, so a
Playwright `page.goto` can hang on the confirmation dialog. Close the save first, or open
a fresh page.

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
cd camxora.com && npm run typecheck && npm run check:ui && npm test
```

Add `npm run test:e2e` when the change touches the editor's interaction model, the
metric surface, or accessibility.

`check:ui` rejects raw hex outside the palette (use `hsl(var(--token))`) and font sizes
outside the `.s-*` scale.

## What we deliberately did NOT copy from the reference

Written into the code where it matters: the reference has **no** save-status, conflict
UI, offline state or draft recovery (spec §93, §96). We built all four on purpose. Any
future "parity" work should not delete them.

## Next moves, in order

Everything that does **not** depend on a missing backend endpoint or a real generated
clip is done. What is left:

1. **W4.2 stems** and the stems half of **W4.3** — the charge path is fixed and verified
   (D-009); what remains is one genuinely generated clip so musicapi can resolve the
   owning Suno account (blocker B-005).
2. **G12 remainder** — a stems tab (needs a finished stems job first, B-005). Workspaces,
   Songs, Projects and Uploads are wired; workspace rows carry the server's song count
   and selecting one filters the Songs tab (`?workspace_id=`).
3. **G21 remainder** — per-track Arm (needs recording, which does not exist).
4. **W6 verification** — the inventory re-walk against a signed-in reference session
   (B-001); that is also where the five capture gaps get filled.
5. **e2e in CI** — the specs exist and pass locally; CI has no app/API/DB to run them.
   Adding a service-backed job is an infrastructure decision, not a code gap.

## Modules added this session (each with a dev handle for measurement)

| Module | Purpose | Handle (dev only) |
|---|---|---|
| `lib/studio-snap.ts` | snap-to-grid, drag threshold, pure | — |
| `lib/studio-draft.ts` | offline draft storage, storage-injected | — |
| `lib/studio-seed.ts` | build a project from a song | — |
| `lib/studio-master-bus.ts` | real EQ/comp/limiter/drive node graph | `window.__buildMasterBus` |
| `lib/studio-export.ts` | 16-bit WAV encoder + offline mixdown | `window.__studioExport` |
| `lib/studio-meter.ts` | peak / RMS / 4x inter-sample estimate | `window.__studioMeter` |
| `lib/studio-normalise.ts` | sample-peak gain matching for exports | `window.__studioNormalise` |

The handles exist so audio behaviour can be measured with an `OfflineAudioContext`
instead of by ear — that is how W4.1, W4.3 and W4.4 were verified.

## Capture position

65 screens: **60 DONE / 3 PART / 2 OPEN**, 78 images, spec §1–§96. The five remaining
are in `reference/CAPTURE_GAPS.md`; three need a Studio-native clip in a specific
state, two need a forced account state. None block the build.
