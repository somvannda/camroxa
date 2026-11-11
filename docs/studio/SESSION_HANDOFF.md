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
| `npm test` (vitest) | **274 / 274**, 30 files |
| `npx playwright test` | **130 passed / 2 skipped** |
| python -m pytest platform_api/tests -q (merged main) | **3354 passed**, 2 known warnings |

The single skip is the uploads spec's optional branch (`STUDIO_EXPECT_UPLOADS=1` when a
bucket is configured).

## Recently shipped (all on this branch)

| Area | Evidence |
|---|---|
| Time selection (N-01) | ruler drag/Shift-click, edge grips, range menu, delete/duplicate time with ripple, scoped delete, loop selection, range export unlock — `lib/studio-time.ts`, `tests/e2e/studio-time-selection.spec.ts` |
| Warp markers (S30) | audio clip editor on double-click, Stretch switch + 3 captured modes + Formant, pennant markers over the waveform, drag/select/quantize — `lib/studio-warp.ts`, `components/studio/StudioAudioEditor.tsx` |
| Clip settings (§81) | the whole captured column is live: Volume dB, Loop/Reverse, Pitch, Speed, Quantize; one planner drives playback and export — `lib/studio-clip-audio.ts` (D-032) |
| Track bounce (N-06) | track menu renders that track through its chain and places a `(bounced)` track with the source muted; when uploads are unavailable it downloads the WAV and the toast says why — `tests/e2e/studio-bounce.spec.ts` |
| MIDI download (N-05) | selected MIDI clips become one `.mid` (format 0, 480 PPQ) — `lib/studio-midi-file.ts` |
| Clip transforms | Extend / Cover… / Remaster run the Studio operation API and land as a lane after the clip or as a new take — `lib/studio-transforms.ts` (D-033) |
| Library filters + uploads | honest filter menu (`lib/library-filters.ts`), Uploads tab listing Studio imports, and add-to-project placement (`lib/studio-upload-place.ts`) |
| Site accessibility | `<main>` landmark on every `(site)` page, named player region, decorative images, `h2` ordering, readable disabled menu items; axe gates now cover Studio, Library, Create, `/`, `/pricing` and `/discover` |

Decisions recorded: **D-029** (two selection types), **D-030** (warp marker pairs),
**D-031** (bounce renders the track; in-place placement with a download fallback),
**D-032** (clip settings run through one planner; pitch and speed share the rate).

## Still blocked or deferred

| Item | Why | Where |
|---|---|---|
| Real-bucket verification of in-place bounce | **verified 2026-11-11** against moto with a disposable database (recipe in B-007); the running sandbox API still has no storage, so the fallback is what executes locally | D-031, B-007 |
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
| e2e | `npm run test:e2e` | 49 specs, 130 passing |

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
   `gh auth login -h github.com` is required first (the local token is invalid).
2. **Give the running sandbox API storage**: configure a bucket (or re-save the streaming
   settings in admin, B-006/B-007). The upload + in-place bounce path is already verified
   against moto with a disposable DB; this step makes the *local* dev stack match.
3. **Optional library follow-ups**: uploads rename/delete (needs a mutation endpoint);
   covers/remasters filters (need generation↔`studio_operations` attribution).
4. **S60/S61** and the §100 detail-rail image when a reference session is available.

Everything else in the documented gap list is built: the §81 column shipped as D-032, the
selection model as D-029, warp markers as D-030, bounce as D-031 and MIDI export as N-05.
The merged task branches were deleted from `origin` on 2026-11-11; only
`feat/studio-rebuild` carries this work.
