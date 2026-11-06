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

## B-004 — Stems tab needs a listing API

**Blocks:** G12's stems tab, and PRJ-023.

**State:** uploads and workspaces now list (`GET /studio/uploads`, `GET /workspaces`
with `song_count`), and workspace selection filters the song list. Stems do not: a stem
set exists only as a `studio_operations` row with a provider-shaped `result_json`, and
no stems job has ever completed in this environment (B-005), so the projection cannot be
written against real data.

**Unblock:** finish B-005, capture one successful stems result, then project it as a
typed list endpoint. Not on the critical path.

## B-005 — Studio ops need one genuinely generated clip

**Blocks:** the last step of W4.2 (receiving an actual stem set) and the stems half of
W4.3.

**State:** the credit path is fixed and verified (D-009). The forward now reaches
musicapi, which answers `409 "The source clip's Suno account is not recorded."` because
`findAssetAccountAny` finds nothing for the seeded `sandbox-clip-ok`: it reads
`asset_owners` / `jobs.result_json` in the `sunoapi` database, and the seeded clip never
came from a Suno account.

**Unblock:** generate one real clip in the sandbox (needs a public
`PLATFORM_SUNO_CALLBACK_BASE_URL` — Suno refuses to call back to localhost, which the
readiness endpoint reports as `suno_callback_base_url: false`), then request stems on it.

**Do not** point a seeded task at another user's real asset id: it would run a paid
Studio operation against someone else's Suno asset.

## Closed

| ID | Was | Closed by |
|---|---|---|
| — | Studio charge died on `relation "plans" does not exist` | D-009 — studio ops price from `credit_pricing` |


## B-006 � Library upload needs streaming storage

**Blocks:** the level-2 toolbar upload (�19.2) and the Uploads tile's first-use path.

**State:** `POST /api/v3/web-music/studio/uploads` answers `503 "Studio uploads are not
configured."` because `resolve_streaming_storage_config` has no configured bucket
(`storage_not_configured`). The control exists, posts the file, and the panel shows the
backend's message in an alert; no row is invented.

**Unblock:** point `camxora_pfm_sandbox` at a configured streaming bucket (local MinIO is
enough) and re-run `studio-library.spec.ts` � its upload test accepts either the row or
the configured-error path.

**Do not** stub the endpoint to return a fake upload: the Add button would then place a
clip whose URL 404s.
