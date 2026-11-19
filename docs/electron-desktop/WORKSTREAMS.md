# Workstreams and Merge Protocol

> **Integrator worktree:** `G:\Developments\Projects\Camxora Desktop`
> **Integrator branch:** `desktop/electron-v1`
> **Base commit:** `1bfcaae`
> **Updated:** 2026-11-19 (wave 10)

The project follows the repo rule: **one agent per worktree**. Agents do not share a
directory and do not push. The integrator reviews and merges each branch in order.

---

## Active workstreams

| Worktree | Branch | Agent scope | Status |
|---|---|---|---|
| `Camxora Desktop` | `desktop/electron-v1` | Integrator: shared files, reviews, merges | Active |
| ~~`Camxora Desktop Upload`~~ | ~~`desktop/youtube-upload`~~ | Manual YouTube upload from Progress | **Merged** |
| ~~`Camxora Desktop Downloads`~~ | ~~`desktop/downloads`~~ | Music download coordinator + Progress live queue | **Merged** |
| ~~`Camxora Desktop P8`~~ | ~~`desktop/settings-p8`~~ | Descriptions, Structures, Moods, Pools, Suno tabs | **Merged** |
| ~~`Camxora Desktop Batch`~~ | ~~`desktop/batch`~~ | Offscreen render host, queue wiring, Progress/Music triggers, merge | **Merged** |
| ~~`Camxora Desktop Templates`~~ | ~~`desktop/templates`~~ | Save-as-template, template rail, single-template render | **Merged** |
| ~~`Camxora Desktop Pipeline`~~ | ~~`desktop/pipeline`~~ | Native export + Renders | **Merged** |
| ~~`Camxora Desktop Vizzy`~~ | ~~`desktop/vizzy`~~ | P7 real editor host, native project I/O, save/open bridge | **Merged** |
| ~~`Camxora Desktop Settings`~~ | ~~`desktop/settings`~~ | P2 Settings core: Profiles, Publication, Preferences | **Merged** |
| ~~`Camxora Desktop Progress`~~ | ~~`desktop/progress`~~ | P3 Progress page | **Merged** |
| ~~`Camxora Desktop Music`~~ | ~~`desktop/music`~~ | P4 Music page | **Merged** |
| ~~`Camxora Desktop Image Marketplace`~~ | ~~`desktop/image-marketplace`~~ | P5 Image + P6 Marketplace | **Merged** |

Wave 1 (Auth, Account, Vizzy Host), wave 2 (Progress, Music, Image/Marketplace), Settings,
the Vizzy editor host, export/Renders, save-as-template, batch orchestration, P8 settings,
downloads and manual upload are merged and removed. There is no active page worktree; new work
starts from `1bfcaae`.

Create future worktrees from the latest integrator commit, not from an older page branch.

---

## File ownership

| Owner | Files |
|---|---|
| **Integrator** | `package.json`, `package-lock.json`, `vite.config.ts`, `tsconfig.json`, `src/app.tsx`, `src/shell/**`, `src/styles/**`, `electron/ipc/index.ts`, `electron/preload.ts`, `electron/shared/types.ts`, `docs/electron-desktop/**` (except the Vizzy host spike report) |
| **Auth agent** | `electron/services/api-client.ts` (auth/bootstrap), `electron/services/session.ts`, new `electron/services/google-oauth.ts`, `electron/ipc/auth.ts`, `src/features/auth/**`, `src/store/session.ts`, auth tests |
| **Account agent** | `src/features/dashboard/**`, `src/features/profile/**`, dashboard/profile tests; `src/app.tsx` route mapping for those two pages only |
| **Vizzy host agent** | `electron/vizzy-host/**`, `vizzy/**`, `scripts/vizzy-host-spike.mjs`, `docs/electron-desktop/vizzy/HOST-SPIKE.md` |
| **Settings agent** | `src/features/settings/**`, settings tests |
| **Progress agent** | `src/features/progress/**`, progress tests |
| **Music agent** | `src/features/music/**`, music tests |
| **Image/Marketplace agent** | `src/features/image/**`, `src/features/marketplace/**`, `electron/services/templates.ts`, `electron/ipc/templates.ts`, template-only `ipc/index.ts`/`preload.ts`/`shared/types.ts`/`package.json` additions |

If an agent needs a shared-file change, it reports the request instead of editing the file.
The integrator makes the change on `desktop/electron-v1` and agents rebase/merge it.

---

## Merge order

1. **Auth** — unblocks real sessions and gates; merge first.
2. **Account** — Dashboard/Profile assume the shared API client; rebase on Auth if needed.
3. **Vizzy Host** — independent spike; merge last; no page wiring yet.

After each merge:

```powershell
cd "G:\Developments\Projects\Camxora Desktop\desktop-electron"
npm ci                 # only if the lockfile changed
npm run typecheck
npm run lint
npm test
npm run build
npm run test:e2e
```

Only then merge the next branch. If a page agent and Auth both changed a shared file, the
integrator resolves it; agents must not resolve cross-worktree conflicts themselves.

---

## Review checklist per branch

- [ ] Branch is based on the current `desktop/electron-v1` (or rebased cleanly).
- [ ] No files outside the agent's ownership.
- [ ] No token, password, email or absolute user path in logs/fixtures.
- [ ] `typecheck`, `lint`, `test`, `build` pass.
- [ ] Relevant E2E passes (auth/account).
- [ ] Loading/error/empty states exist.
- [ ] No dead controls or placeholder copy in shipped surfaces.
- [ ] Design tokens/components used; no new visual language.
- [ ] Commits are logical and local (no push).
- [ ] Worktree is clean after merge; remove it with `git worktree remove`.

---

## Conflict rules

1. Shared file changed by an agent → integrator owns the resolution.
2. Two agents need the same shared file → integrator lands the shared change first, then both
   agents rebase.
3. A page needs a new IPC channel → add a domain IPC module under `electron/ipc/` and register
   it in `electron/ipc/index.ts`; do not add handlers to another domain's module.
4. A page needs a new API type → use the generated `src/lib/api-schema.d.ts`; do not hand-edit
   the schema.
5. A new dependency → integrator adds it on `desktop/electron-v1`; agents do not edit
   `package.json`.

---

## Current phase mapping

| Workstream | Phase | Primary docs |
|---|---|---|
| Auth | P1 | `pages/01-LOGIN.md`, `02-TECHNICAL-ARCHITECTURE.md` §4 |
| Account | P2 | `pages/02-DASHBOARD.md`, `pages/03-PROFILE.md` |
| Vizzy host | P7 spike | `vizzy/02-MODULE-MAP.md`, `vizzy/03-PARITY-HARNESS.md` |
| Integrator | All | `03-IMPLEMENTATION-PLAN.md`, `STATUS.md` |
