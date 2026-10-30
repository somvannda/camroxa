# PROJECT BLOCKERS

Open items that stop work. Each names the unblocking action and the owner.

## B-001 — No live reference session

**Blocks:** M1 completeness, and every `VERIFIED` transition that depends on
comparing behaviour with the real Studio (mostly VISUAL/flow questions, not API).

**State:** the pool's `__client` value in `musicapi/accounts.json` is a Clerk
**refresh** token whose client has **no active sessions**
(`GET https://auth.suno.com/v1/client` → `sessions: []`). It cannot mint a session
JWT, so a browser cannot be signed in with it. Cookie injection was attempted and
correctly did not authenticate.

**Unblock (any one):**

1. A human signs in to the reference in the connected browser once; the session
   cookie persists for later inspection.
2. A fresh `__client` **session** cookie (with at least one active session) is added
   to the pool.
3. Accept bundle/help-centre evidence as sufficient for the remaining questions and
   mark those rows `DOCUMENTED`, not `VERIFIED`.

**Impact if unresolved:** we can still build and verify our own product end to end;
we cannot claim reference parity for ambiguous interactions. No code is blocked.

## B-002 — No Studio test harness

**Blocks:** M11 and the `VERIFIED` roll-up for most features.

**State:** `camxora.com` has no test runner configured. Adding one is a dependency
decision (vitest vs. node:test vs. Playwright only).

**Unblock:** approve vitest + Playwright as dev dependencies, then W5.1.

**Interim:** manual journeys W-A…W-H recorded in `PROJECT_PROGRESS.md`.

## B-003 — Local services not running

**Blocks:** end-to-end manual verification right now.

**State:** at session start only the web dev server was up (3103); `musicapi` (4003)
and `platform_api` (8100) were stopped. PostgreSQL (5432) is up.

**Unblock:** start the two services (see `README.md` / `musicapi/README.md`), ensure
`camxora.com/.env.local` points at `PLATFORM_API_URL=http://localhost:8100`.

## B-004 — Uploads/stems tabs need a listing API

**Blocks:** PRJ-022/023 completion.

**State:** uploads and stems exist as objects but there is no "list my stems" /
"list my uploads" endpoint surfaced to the web client.

**Unblock:** add `GET /api/v3/web-music/studio/uploads` and a stems projection, or
derive from generations. Needs a small backend task; not on the critical path.

## Closed

| ID | Was | Closed by |
|---|---|---|
| — | — | — |
