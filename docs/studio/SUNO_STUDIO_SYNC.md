# Suno Studio project sync — requirement and design

**Status:** proposed, not implemented
**Date:** 2026-11-13
**Scope:** `musicapi` ↔ Suno Studio project APIs, `platform_api` ownership,
`camxora.com` editor

## 1. The requirement, stated precisely

A Camxora Studio project must have a **1:1 semantic mirror** in Suno Studio:

1. Creating a project in Camxora creates exactly one Suno Studio project under a
   pinned Suno account, and stores the mapping
   `camxora_project_id ↔ suno_project_id ↔ camxora_user_id ↔ suno_account`.
2. Every Camxora change (tracks, clips, MIDI, audio settings, effects, markers,
   automation, title, tempo, meter, archive state) is pushed to the same Suno
   project, so opening it in Suno Studio shows the same arrangement.
3. Changes made directly in Suno Studio are pulled back into Camxora when the
   project is opened or refreshed.
4. The mapping is stable and private: a project is always read/written through the
   Suno account that created it; no other account or user can see or mutate it.
5. Failures are visible and recoverable: a local edit never depends on Suno being
   online, but the UI shows `Synced` / `Pending` / `Sync failed`, and a durable
   outbox retries.

"Everything" here means **document state**, not screenshot pixels. Section 8
explains the pixel question and why it is a separate decision.

## 2. What the existing code already provides

| Layer | Existing piece | Reuse |
|---|---|---|
| Suno auth | `musicapi` holds durable `__client` cookies, mints Clerk JWTs, rotates cookies | unchanged |
| Suno web APIs | `/api/studio/create-project`, `/api/studio/save-project`, `/api/studio/project/{id}`, `/api/studio/list-projects`, revisions, metadata, archive | new internal client |
| Account pool | per-account health, credits, rate limits, pinned task keys (`suno_tasks.suno_key_id`) | same pattern for projects |
| Local document | `platform_api` `studio_projects` (`id, user_id, title, bpm, time_signature, data jsonb`) + versions/shares/comments | keep as local source |
| Editor save | debounced `PATCH /studio/projects/{id}` with `expected_updated_at` | add sync hook |
| Worker | `platform_api.worker` + `job_queue` | new `suno_project_sync` job type |

Suno endpoints confirmed in `docs/studio/reference/endpoint-inventory.md`:

```
POST /api/studio/create-project
POST /api/studio/save-project          { project_id, state, title, base_version_id }
GET  /api/studio/project/{project_id}
GET  /api/studio/list-projects
GET  /api/studio/{project}/versions
GET  /api/studio/{project}/version/{version_id}
POST /api/studio/project/{project_id}/metadata
POST /api/studio/project/{project_id}/archive
POST /api/studio/project/{project_id}/unarchive
```

`save-project` carries a `base_version_id`, which is Suno's optimistic
concurrency token and the basis for conflict handling.

## 3. Non-goals / limits

- A local project is **not** a live co-editing session of the same Suno page.
  Suno's own live collaboration remains Suno-side; we mirror saved state.
- We do not store Suno cookies or JWTs in the platform database; only the account
  mapping and project ids.
- We do not mirror our own **extra** features that have no Suno field (see §7).
- Syncing does not make our DOM identical to Suno's DOM. Pixels are §8.

## 4. Data model (platform DB, new migration)

```sql
CREATE TABLE studio_suno_projects (
  local_project_id UUID PRIMARY KEY
    REFERENCES studio_projects(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  -- Suno accounts live in the `sunoapi` database, so this is an identity string,
  -- not a cross-database FK. It is the same value as `suno_accounts.label`.
  suno_account_label TEXT NOT NULL,
  suno_project_id UUID NOT NULL,
  suno_version_id UUID,
  status TEXT NOT NULL DEFAULT 'pending', -- pending | synced | error | local-only
  last_synced_at TIMESTAMPTZ,
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (suno_account_label, suno_project_id)
);

CREATE TABLE studio_suno_outbox (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  local_project_id UUID NOT NULL
    REFERENCES studio_suno_projects(local_project_id) ON DELETE CASCADE,
  kind TEXT NOT NULL,                    -- create | save | metadata | archive | delete
  payload JSONB NOT NULL,
  attempts INT NOT NULL DEFAULT 0,
  next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status TEXT NOT NULL DEFAULT 'queued', -- queued | running | done | dead
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Account pinning is mandatory. A Suno project belongs to one Suno account; moving
it to another account is not supported by Suno. `suno_account_label` is therefore
immutable after create. This is the same rule already used by
`platform_api.migrations` for `suno_tasks.suno_key_id`.

## 5. musicapi internal API

All routes require `x-internal-token`, resolve a pinned account, mint a JWT from
that account's durable cookie, and never return the JWT/cookie.

```
POST /internal/studio/projects
  { local_project_id, user_id, title, state, account_label? }
  -> { suno_project_id, suno_version_id, account_label }
  Idempotent on local_project_id: an existing link returns the same ids.

POST /internal/studio/projects/{suno_project_id}/save
  { state, title, base_version_id }
  -> { suno_version_id }

GET  /internal/studio/projects/{suno_project_id}
  -> { state, title, suno_version_id, updated_at }

GET  /internal/studio/projects?account_label=&cursor=&limit=

POST /internal/studio/projects/{id}/metadata
POST /internal/studio/projects/{id}/archive
POST /internal/studio/projects/{id}/unarchive
```

Error mapping: 401/403 means the account session died → mark link `error` with
`reauth_required` and do not try another account; 409 means `base_version_id` is
stale → return the remote version for conflict resolution; 429 means back off with
the same account.

## 6. Sync flow

### 6.1 Create

```
editor POST /studio/projects
  -> platform inserts studio_projects + studio_suno_projects(status=pending)
  -> job_queue(suno_project_sync, kind=create)
  -> worker calls musicapi /internal/studio/projects
  -> link updated: suno_project_id/version, status=synced
```

If Suno is unavailable, the local project still exists and opens; the editor shows
`Sync pending` and the worker retries. Never block project creation on Suno.

### 6.2 Save

- The editor's existing debounced `PATCH` remains the local save. On success it
  enqueues `suno_project_sync(kind=save)` with the project version it just wrote.
- The outbox coalesces: only the newest pending state per project is retained.
- The worker converts the local document to Suno `state` (§7), calls `save-project`
  with `base_version_id = link.suno_version_id`, stores the returned version.
- If `409`, do **not** overwrite. Fetch `GET project/{id}`, store the remote state
  and mark `conflict`. The editor offers:
  - **Load Suno version** (replace local `data` after confirmation)
  - **Keep mine** (rebase `base_version_id` and push again)
  - **Duplicate locally** (new local project; leave Suno unchanged)

### 6.3 Pull

- On project open, if `link.status != synced` or `suno_version_id` differs from
  the last read, fetch the Suno project and compare a semantic hash.
- If only Suno changed, apply its state to local `data` (same transaction as a
  version snapshot).
- If both changed, use the conflict path above.
- A low-frequency poll (e.g. every 30 s while the editor is open) can refresh; the
  existing presence poll is a separate channel and must not be conflated.

### 6.4 Archive / delete

- Archive mirrors `archive`; unarchive mirrors `unarchive`.
- Local hard-delete should not silently delete the Suno project. Preferred:
  archive on Suno and keep the link tombstone. A separate explicit "Delete on
  Suno" action can be added later with confirmation.

## 7. Document translation

The local document (`studio_projects.data`) is ours. Suno's `state` schema must be
captured from a real project before this mapping can be finalized. Phase 0 below
captures `GET /api/studio/project/{id}` for a generated project and stores a
sanitized sample under `docs/studio/reference/suno-project-state.sample.json`.

Mapping table (to be completed after Phase 0):

| Camxora | Suno `state` | Direction | Notes |
|---|---|---|---|
| `title` | project `title` | both | metadata route may also carry it |
| `bpm`, `time_signature` | tempo/meter fields | both | exact field names TBD |
| `tracks[]` | track list | both | id, name, colour, index, mute/solo/volume/pan |
| `lanes[]` (clips) | clip list | both | start/duration/offset/fade, audio/song id, type |
| `midi.notes`, bend, mod | MIDI clip fields | both | pitch/start/length/velocity |
| `chains` (effects) | effect chain | both | plugin ids/params must map to Suno device ids |
| `masterChain` | master chain | both | limiter/EQ/compressor amounts |
| `markers` | section markers | both if present | exact field TBD |
| `groups` | — | local-only? | no captured Suno group record |
| `volumeAutomation`/`panAutomation` | automation lanes | both if present | point schema TBD |
| custom wavetable/IR ids | — | local-only | Suno has no custom table asset in the state |
| `pluginPresets`, `librarySongs` | — | local-only | our UI metadata |

Rules:

1. Unknown local keys are **preserved locally** and omitted from Suno; they never
   block a save.
2. Unknown Suno keys are preserved in a `sunoExtras` bag so a Suno edit does not
   erase fields we do not model.
3. A round-trip test must prove `local -> Suno -> local` is stable for supported
   fields (semantic hash equality, ignoring ids/order where Suno normalizes).
4. Unsupported fields are listed in the sync status tooltip, so "1:1" is never
   claimed for data Suno does not have.

## 8. Pixel parity vs state parity

They are different requirements:

- **State parity** is this document: the arrangement is the same when opened on
  either side.
- **Pixel parity** is a rendering property. Our editor is a CAMXORA-branded
  implementation (D-025): navy surfaces, product purple, our wordmark and copy.
  The captured geometry, spacing, type scale and control sizes are asserted by
  `studio-pixel.spec.ts`; the palette is intentionally different.

A literal screenshot diff against Suno is therefore expected to fail on colour,
logo, copy and project content. If "pixel by pixel" means **literal Suno pixels**,
that is a separate product decision: adopt Suno's palette/typography/assets, which
reverses D-025. It does not follow from state sync.

## 9. Account and privacy model (critical decision)

Suno projects are account-scoped. Two local users cannot share one Suno account
without seeing each other's projects in Suno Studio. Options:

1. **One Suno account per Camxora user** (recommended for privacy): a user without
   a linked Suno account gets `local-only` projects.
2. **A dedicated mirror account per local user** on the Suno side.
3. **A single shared mirror account** (only acceptable if the product is a demo and
   users are told their projects share that Suno account).

The current pool has a small number of accounts. The requirement must name the
policy before implementation; this is the main blocker.

## 10. Security / compliance

- Never expose `__client`, JWT, or account labels to the browser.
- Enforce local ownership in `platform_api` before any internal call.
- Pin the account and verify the Suno project belongs to it; never "try another
  account" on 401/403.
- Suno Studio's project endpoints are private web APIs, not a documented public
  API. Confirm the account/ToS position before shipping a mirror that writes to
  them.
- Rate limits: debounce saves (the editor already debounces locally), coalesce the
  outbox, and cap retries with exponential backoff.
- Audit every sync attempt: local project, account label, Suno project/version,
  result, error.

## 11. Phased implementation

**Phase 0 — schema capture (must be first).**
Create one throwaway project on the reference account, then capture
`create-project`, `save-project`, `project/{id}`, `list-projects` request/response
pairs. Store a sanitized `state` sample and the exact version fields. Without this,
the translation layer is guesswork.

**Phase 1 — create/list/link.**
Migration, link table, create route, worker job, mapping row. Creating a local
project creates exactly one Suno project; retries are idempotent. No document
translation yet; push a minimal valid `state`.

**Phase 2 — save translation.**
Read-only round-trip: local project -> Suno state -> local. Compare semantic hash.
Then enable saves, with `base_version_id` and conflict storage.

**Phase 3 — pull/reconcile.**
Open/refresh pull, semantic hash comparison, conflict UI (`Load Suno`, `Keep mine`,
`Duplicate`).

**Phase 4 — coverage matrix.**
Per-feature tests: tracks, clips, MIDI, effects, automation, markers, metadata,
archive. Mark unsupported fields as local-only in the UI.

**Phase 5 — operations.**
Sync status chip, admin diagnostics, re-auth flow for dead Suno sessions, metrics
and alerts.

## 12. Acceptance tests

| Case | Expected |
|---|---|
| Create local project | exactly one Suno project; link row `synced`; retry does not create a second |
| Edit local track/clip | Suno `project/{id}` state matches after the debounce; version advances |
| Edit in Suno | reopening the local project detects the newer version and applies it |
| Both sides changed | `409`; conflict UI appears; no silent overwrite |
| Suno offline | local edit saves; status `pending`; outbox retries; no data loss |
| Expired account | status `error/reauth_required`; no other account is tried |
| Other Camxora user | 404/403; no cross-account read or write |
| Unsupported local field | preserved locally, omitted from Suno, documented in the status |

## 13. Open decisions before implementation

1. **Account policy:** one Suno account per Camxora user, a dedicated mirror
   account per user, or one shared demo account? (§9)
2. **Source of truth:** local-first with Suno mirror (recommended) or Suno-first
   with local cache?
3. **Pixel goal:** semantic/geometry parity (current D-025) or literal Suno
   palette/UI?
4. **Unsupported fields:** keep local-only, or drop them when syncing?
5. **Suno ToS/private API approval:** do we have permission to write projects to
   the reference Studio for users?
6. **Sync cadence:** debounce interval and pull interval (suggested 1.5 s save /
   30 s pull while open).

Until §13 is decided, the safe implementation is Phase 0 only: capture the state
schema without writing user data.
