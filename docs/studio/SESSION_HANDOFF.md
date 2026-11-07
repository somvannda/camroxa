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
| **Capture** (65 screens → screenshot + spec) | **63 DONE / 0 PART / 2 OPEN**, spec §1–§99, 80 images. The two remaining are S60/S61 and are documented in `reference/CAPTURE_GAPS.md`; neither blocks the build. |
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
| e2e | `npm run test:e2e` | smoke, persistence, home + search, library + date grouping, project menu, clip menu + split, clip info, conflicts, offline, share page, versions, transport, meter, shortcuts, trim, fade, snap guideline, track colour, loop/seek, export bytes, zoom, tracks, clipboard, marquee, plugins dry/wet + live, mute/solo, solo-aware bounce, master, help, keys, metronome, writes, metrics, axe ×3 |

CI job `camxora-web-checks` in `pr-checks.yml` runs typecheck + check:ui + `npm test` on
any PR touching `camxora.com`. The e2e specs are not in CI yet — they need the app plus
the platform API and a database, which the workflow does not provision. They build their
own fixtures through the API (`tests/e2e/studio-fixture.ts`) and leave those fixture
projects in the sandbox database, so the sandbox accumulates test projects by design;
they never touch a non-sandbox account.

**Backend suite:** `python -m pytest platform_api/tests -q` → **3163 passed, 0 failed**
at `3215e3d1`. Two tests that still asserted the retired plan machinery were rewritten to
the credits-only contract: `test_user_spend_service` now expects every spender to be
reported Free (no plan meters, over-allowance from soft overages), and
`test_web_music_batch_access` asserts `usage_today` never reads the legacy v2 ledger even
with the v3 flag off. The suite is green, so a new failure is a real one.

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
| Two edits in quick succession | writes are serialized; do not "fix" a 409 by loosening the version check — the queue already coalesces (G29) |
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

Capture is **63/65** (S60/S61 need forced states) and the signed-in reference session is
available; the one missing image is §100's song-detail rail, blocked only by the Review
pane not being visible when the screenshot runs. What is left:

1. **W4.2 stems** and the stems half of **W4.3** — the charge path is fixed and verified
   (D-009); what remains is one genuinely generated clip so musicapi can resolve the
   owning Suno account (blocker B-005).
2. **G12 remainder** — only the stems tile/list (B-005). The two-level library is fully
   wired: level 1 tile chooser + Workspaces (with `New workspace`) + Studio Projects;
   level 2 with collapsible date headings, Play/Like row actions, draggable rows,
   tag strips, the captured toolbar, and the §100 song-detail rail on double-click.
   Library upload is **verified locally** against a moto S3 stand-in (B-006); production
   still needs a real bucket.
3. **G21 remainder** — per-track Arm (needs recording, which does not exist).
4. **§100 image + S60/S61** — an image of the detail rail when the pane is visible, and
   the two forced states (moderation, no credits). Neither blocks the build.
5. **e2e in CI** — the specs exist and pass locally (57 tests); CI has no app/API/DB to
   run them. Adding a service-backed job is an infrastructure decision, not a code gap.

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
| `lib/studio-settings.ts` | editor preferences + the ghost-drag apply plan | — |
| `lib/studio-help.ts` | What's This? copy registry + our real shortcut list | — |
| `lib/studio-metronome.ts` | click timing (pure) + beat-in-bar | — |

The handles exist so audio behaviour can be measured with an `OfflineAudioContext`
instead of by ear — that is how W4.1, W4.3 and W4.4 were verified.

## Capture position

65 screens: **63 DONE / 0 PART / 2 OPEN**, 80 images, spec §1–§99. The two remaining
are the forced account states in `reference/CAPTURE_GAPS.md`. None block the build.
