# SESSION HANDOFF — read this first

State as of **2026-11-11**. Start here; the long plans live beside this file.

## Where things are

| | |
|---|---|
| Worktree | `C:\Users\Kong Somvannda\.local\share\opencode\worktree\d16337\studio-rebuild` |
| Branch | `feat/studio-rebuild` — clean, pushed, **reconciled with `origin/main`** (`0` behind, `437` ahead) |
| Web | `localhost:3103` (`npm run dev` in `camxora.com`) |
| Platform API | `localhost:8100` — **must run from this worktree** |
| MusicAPI | `localhost:4003` |
| Local account | `somvannda@gmail.com` / `StudioLocal!2026` |
| UI login | needs `NEXT_PUBLIC_TURNSTILE_DISABLED=1` in `camxora.com/.env.local` |
| Capture archive | `docs/studio/reference/screens/` — 83 images |

## State in one paragraph

Capture is **63/65 DONE / 2 OPEN** (S60 moderation, S61 credits — both need forced
account states). The gap analysis `G1`–`G49` is **done** except `G12`'s remaining
blocked halves, and the build has now shipped the last unblocked feature areas:
time-selection editing (N-01), warp markers + the audio clip editor (S30), track
bounce (N-06) and MIDI download (N-05). Every one of them is covered by unit tests and
browser tests, and the branch is main-synced.

## Verified on `7a51da8b` (post-merge)

| Gate | Result |
|---|---|
| `npm run typecheck` | clean |
| `npm run check:ui` | compliant |
| `npm test` (vitest) | **255 / 255**, 27 files |
| `npx playwright test` | **116 passed / 1 skipped** |

The single skip is the uploads spec's optional branch (`STUDIO_EXPECT_UPLOADS=1` when a
bucket is configured).

## Recently shipped (all on this branch)

| Area | Evidence |
|---|---|
| Time selection (N-01) | ruler drag/Shift-click, edge grips, range menu, delete/duplicate time with ripple, scoped delete, loop selection, range export unlock — `lib/studio-time.ts`, `tests/e2e/studio-time-selection.spec.ts` |
| Warp markers (S30) | audio clip editor on double-click, Stretch switch + 3 captured modes + Formant, pennant markers over the waveform, drag/select/quantize — `lib/studio-warp.ts`, `components/studio/StudioAudioEditor.tsx` |
| Clip settings (§81) | the whole captured column is live: Volume dB, Loop/Reverse, Pitch, Speed, Quantize; one planner drives playback and export — `lib/studio-clip-audio.ts` (D-032) |
| Track bounce (N-06) | track menu renders that track through its chain and downloads a WAV, solo-aware — `tests/e2e/studio-bounce.spec.ts` |
| MIDI download (N-05) | selected MIDI clips become one `.mid` (format 0, 480 PPQ) — `lib/studio-midi-file.ts` |

Decisions recorded: **D-029** (two selection types), **D-030** (warp marker pairs; the
rest of the captured §81 settings column is deferred), **D-031** (bounce renders the
track; in-place waits for storage).

## Still blocked or deferred

| Item | Why | Where |
|---|---|---|
| Render-in-place bounce | `POST /studio/uploads` answers `storage_not_configured` on the running API; data-URL clips were rejected as document bloat | D-031, B-007 |
| Key/BPM rows in the library rail | the corpus carries neither (`suno_tasks` has no fields, provider metadata had none) | G12, D-016 |
| Stems tile/upload halves of G12 | stems needs a genuinely generated clip (B-005); uploads need a bucket (B-006, moto env works locally) | B-005, B-006 |
| S60 / S61 captures | need a signed-in Suno reference session with a real moderation/no-credit trigger | `reference/CAPTURE_GAPS.md` |
| Song Radio + playlists UI | **already shipped in `origin/main`** — Song Radio is in `SongRowMenu` on Create and Library with a working radio endpoint, and Library has a full Playlists tab, detail view and composer. The old handoff list was stale on this point | `components/SongRowMenu.tsx`, `components/LibraryView.tsx` |

## Running the app (the part that costs time)

The API **must** run from this worktree or backend edits do not apply:

```
cd <repo root>
set "PYTHONIOENCODING=utf-8"
set "PLATFORM_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/camxora_pfm_sandbox"
python -m uvicorn platform_api.main:app --host 127.0.0.1 --port 8100 --log-level info
```

- `PYTHONIOENCODING=utf-8` matters: the access log contains `→` and crashes on cp1252.
- Don't `cd platform_api` — the package must be importable from the repo root.
- Uploads (recorded takes, bounce-in-place) need the moto S3 env in `B-006`; without it
  the endpoint answers `storage_not_configured` by design.

Helpers in `scripts/`:

- `inspect_api_env.py <pid>` — which DB a running API actually uses.
- `seed_sandbox_user.py [email] [pw]` — create/reset the user **and its workspace**.
- `seed_sandbox_song.py` — writes `public/seed/demo-loop.wav` + a completed `suno_task`.
- `verify_studio_conflict.py` — proves the 409 path against the live API.

## Tests and CI

| Layer | Command | Count |
|---|---|---|
| production build | `npm run build` | passes (classic editor page is wrapped in Suspense) |
| unit | `npm test` | snap, time edits, warp markers/onsets, MIDI file, meter, export, plugins, … |
| component | `npm test` | header, footer, library, timeline, track panel, audio editor, MIDI editor |
| API contract | `npm test` | paging, version field, 409 mapping, 204 |
| e2e | `npm run test:e2e` | 43 specs, 116 passing |

CI jobs on any PR touching `camxora.com`: `camxora-web-checks` (typecheck, `check:ui`,
`npm test`, `npm run build`) and `camxora-e2e` (Postgres, Redis, musicapi,
platform_api, web, seeded user + song). Both block.

Specs build their own fixtures through the API (`tests/e2e/studio-fixture.ts`) and leave
them in the sandbox database by design; they never touch a non-sandbox account.

**Backend suite:** `python -m pytest platform_api/tests -q` → green after the
`origin/main` reconciliation; plan-era tests were rewritten to the credits-only
contract, so a new failure is a real one.

`beforeunload` note: while a save is pending the editor blocks navigation, so a
Playwright `page.goto` can hang on the confirmation dialog. Close the save first, or open
a fresh page.

## Traps that cost time

| Trap | Avoid |
|---|---|
| Access tokens live **30 minutes** | expect `401` mid-session; re-login via `POST /api/v3/auth/login` from the page |
| Background tab throttles `requestAnimationFrame` | the playhead will not advance; not a playback bug |
| `beforeunload` guard blocks navigation while a save is pending | accept the dialog, or open a new tab |
| Synthetic pointer events need `pointerdown` **on the element** | a press with no movement is a click; >3 px is a drag |
| Stale closures in pointer handlers | read live data through refs (`tracksRef`, `clipsRef`) |
| Two edits in quick succession | writes are serialized; do not loosen the version check (G29) |
| API reads race the async save | poll the project document in e2e instead of reading once |
| PowerShell mangles dashes and nested quotes | write docs with the tools; put JS in a file |
| `next dev` re-adds `camxora.com/AGENTS.md` | commit it, or it stays dirty |

## Gates before every commit

```
cd camxora.com && npm run typecheck && npm run check:ui && npm test
```

Add `npx playwright test` when the change touches the editor's interaction model,
export bytes, the menu surfaces or accessibility.

`check:ui` rejects raw hex outside the palette (use `hsl(var(--token))`) and font sizes
outside the `.s-*` scale — and the `.se-*` block is scanned for stray hexes too.

## What we deliberately did NOT copy

The reference has **no** save-status, conflict UI, offline state or draft recovery
(spec §93, §96). All four are deliberate (W2). Any future "parity" work must not delete
them. Same for the selection model: the reference's time range is transient, so ours is
not persisted (D-029).

## Next moves, in order

1. **Ship the branch**: open a PR from `feat/studio-rebuild` to `main`. The branch is
   main-synced and green, so this is a review step rather than a reconciliation step.
2. **Delete the four merged remote branches** after review
   (`feat/studio-time-selection`, `-warp-markers`, `-bounce`, `-midi-export`); their
   commits are all contained in `feat/studio-rebuild`.
3. **Unblock render-in-place** by starting the API with the moto env (B-006/B-007), then
   upload the bounce and add the `(bounced)` track.
4. **Audio settings pass** — the captured §81 column (Volume, Loop/Reverse, Pitch,
   Speed, Quantize) on top of the clip editor built for S30 (D-030).
5. **S60/S61** and the §100 detail-rail image when a reference session is available.
