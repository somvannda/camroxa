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
- We do **not** keep Camxora-only document fields. Parity is strict (D-034): a
  field with no Suno representation is removed from the editor, never preserved
  as "local-only".
- Syncing does not make our DOM identical to Suno's DOM. Pixels are §8.

## 4. Data model (musicapi migration `0044_studio_suno_sync.sql`) — implemented

The link lives in the **musicapi** database, because musicapi owns the Suno
accounts and is the only service that can call them. The platform database keeps
the project document and passes a snapshot with every sync request, so the two
services share no tables.

```sql
CREATE TABLE studio_suno_accounts (
  user_id UUID PRIMARY KEY,           -- pinned once, immutable
  account_label TEXT NOT NULL,        -- suno_accounts.label in the same DB
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE studio_suno_projects (
  local_project_id UUID PRIMARY KEY,  -- platform studio_projects.id, no cross-DB FK
  user_id UUID NOT NULL,
  account_label TEXT NOT NULL,
  suno_project_id TEXT NOT NULL,
  suno_version_id TEXT,               -- version we last wrote
  suno_remote_version_id TEXT,        -- version Suno reported on the last check
  suno_title TEXT,
  suno_state JSONB,                   -- last Suno document: the merge baseline
  state_hash TEXT,                    -- sha256 of the local document last pushed
  skipped_clip_ids JSONB,             -- local clips with no Suno asset yet
  local_clip_ids JSONB,               -- Suno clip ids we wrote: a delete propagates
  archived BOOLEAN NOT NULL DEFAULT false,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','linked','synced','conflict','error')),
  last_error TEXT,
  synced_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (account_label, suno_project_id)
);

CREATE TABLE studio_suno_outbox (
  local_project_id UUID PRIMARY KEY,  -- one row per project: edits coalesce
  user_id UUID NOT NULL,
  document JSONB NOT NULL,            -- newest snapshot still to push
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Account pinning is mandatory. A Suno project belongs to one Suno account; moving
it to another account is not supported by Suno. `account_label` is therefore
immutable after create. Status meanings: `pending` never pushed, `linked` Suno
project exists but only metadata is mirrored, `synced` arrangement mirrored,
`conflict` Suno advanced first, `error` terminal until retried.

## 5. musicapi internal API — implemented

All routes require `x-internal-token`, resolve the pinned account, mint a JWT from
that account's durable cookie, and never return the JWT, cookie or document.

```
POST /internal/studio/projects/{local_id}/link
  { user_id, title, major_version, bpm, time_signature, data }
  -> { status, suno_project_id, suno_version_id }
  Idempotent: an advisory lock per project prevents a duplicate Suno project.

POST /internal/studio/projects/{local_id}/enqueue
  { user_id, title, major_version, bpm, time_signature, data }
  -> 202 { status: "queued" }        # coalesces onto one outbox row

POST /internal/studio/projects/{local_id}/sync
  { user_id, title, major_version, bpm, time_signature, data }
  -> { status, suno_project_id, suno_version_id, last_error, synced_at, state_sync }

GET  /internal/studio/projects/{local_id}/status?user_id=
  -> the same status view, or `pending` before the first link

POST /internal/studio/projects/{local_id}/refresh   { user_id }
  -> the status view after asking Suno whether it moved ahead
     (throttled per project; never touches the local document)

POST /internal/studio/projects/{local_id}/archive   { user_id, archived }
GET  /internal/studio/sync/health                   # counts, due outbox, pins, coverage
```

Error mapping: 401/403 from Suno means the account session died → link becomes
`error` and no other account is tried; 409 from `save-project` means
`base_version_id` is stale → the remote version is stored and status is
`conflict`; 429 backs off with the same account.

## 6. Sync flow

### 6.1 Create

```
editor POST /studio/projects
  -> platform inserts studio_projects
  -> platform queues one mirror push (the response does not wait for Suno)
  -> musicapi pins an account, POST /api/studio/create-project, stores the link
  -> later pushes read project/{id}, merge, save
```

If Suno is unavailable, the local project still exists and opens; the chip shows
`pending` and musicapi's outbox retries with backoff. Project creation never
blocks on Suno.

### 6.2 Save

- The editor's existing `PATCH` remains the local save. On success the platform
  queues the newest snapshot (the task is fire-and-forget).
- The outbox coalesces: a burst of debounced saves leaves exactly one row.
- Deletes propagate: the link stores the Suno ids it last wrote
  (`local_clip_ids`), so a clip removed locally is dropped from Suno on the next
  push, while clips we never mirrored (or that Suno added) are preserved.
- The worker converts the local document to Suno `state` (§7), calls
  `save-project` with `base_version_id = link.suno_version_id`, and adopts the
  returned version.
- If `409`, do **not** overwrite. The remote state is stored and the link becomes
  `conflict`. The editor offers:
  - **Load Suno version** (replace local `data` after confirmation)
  - **Keep mine** (rebase `base_version_id` and push again)
  - **Duplicate locally** (new local project; leave Suno unchanged)

### 6.3 Pull

- While a project is open the editor asks `refresh` every 15 s. The server
  throttles provider reads per project (30 s, `SUNO_SYNC_CHECK_MS`), so several
  editors on one pinned account share one check.
- `refresh` compares `latest_version_id` with the version we last wrote. A newer
  remote version marks the link `conflict` and stores the remote document as the
  next merge baseline. The local document is never overwritten by a poll.
- A full pull (apply the Suno document to local `data`) needs the reverse field
  mapping and lands with the same schema capture that enables pushes.
- The existing presence poll is a separate channel and is not conflated with this.

### 6.4 Archive / delete

- Archive mirrors `archive`; unarchive mirrors `unarchive`.
- Local hard-delete should not silently delete the Suno project. Preferred:
  archive on Suno and keep the link tombstone. A separate explicit "Delete on
  Suno" action can be added later with confirmation.

## 7. Document translation

The local document (`studio_projects.data`) is ours; the Suno document is
authoritative. The verified field map, the exact schema and the live probe
results live in `SUNO_STUDIO_STATE_SCHEMA.md`; `musicapi/src/studioStateCodec.ts`
is the implementation.

Mapping summary:

| Camxora | Suno `state` | Direction | Notes |
|---|---|---|---|
| `title`, `majorVersion` | `title`, `majorVersion` | both | metadata route also carries the title |
| `bpm` | `timing.bps` | both | `bps = bpm/60` (verified) |
| `time_signature` | `timeSignatureChanges` | both | verified |
| `masterVolume`, loop | `amplitude`, `loop` | both | verified |
| `tracks[]` | `tracks[]` | both | name, colour, hidden, mute/solo, volume→amplitude, pan→balance |
| MIDI clips + notes | `tracks[].clips[].midi` | both | seconds→beats, numeric note ids (verified live) |
| MIDI bend / mod | `midi.pitchBend`, `midi.controlChanges` (CC1) | both | point lists in beats (verified live) |
| clip offset / fades | `readStartBeats` / `fadeInBeats` / `fadeOutBeats` | both | seconds→beats |
| `volumeAutomation` | `tracks[].faderAutomation` | both | written; read-back pending |
| `markers` | `sections` | both | registry keyed by id, beats (verified live) |
| audio clips with a Suno asset | `clips[].asset` | both | asset id comes from the local Suno clip id |
| audio clips without an asset | — | — | not mirrored; reported in `skipped_clip_ids` |
| `lanes[].instrument` | synth `waveform1` | both | sine/triangle/saw (verified live) |
| `lanes[].takes` | `tracks[].takeLanes[].clips` | both | alternates need a Suno asset |
| local upload audio | `clips[].asset` | both | imported once into the pinned account, clip id cached |
| `chains` (all built-ins) | `tracks[].signalChain` | both | compressor, convolution, delay, distortion, chorus, gate, limiter, reverb, EQ; custom plugins stay local |
| `masterChain` | `masterSignalChain` | both | limiter, EQ and compressor (verified live) |
| `markers` | `sections` | both | registry keyed by id, beats (verified live) |
| `groups` | routing / group tracks | both | pending |
| custom wavetable ids | `wavetables` asset | removed | Suno has wavetables as assets, not an editor |

Rules (strict, D-034):

1. Every local key must map to a Suno key or be deleted from the document and
   its editor control. Nothing is "kept locally" as an exception.
2. Unknown **Suno** keys are preserved from the baseline document, so a Suno edit
   never erases fields we do not model yet.
3. A round-trip test must prove `local -> Suno -> local` is stable (semantic hash
   equality, ignoring ids/order where Suno normalizes). The codec tests do this
   offline, and the live probe proved the API side.
4. The coverage matrix doubles as a removal list: an unmapped feature is either
   wired to a Suno field or removed before the mirror is called complete.

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

**Implemented default (2026-11-13): option 1, one pool account pinned per user.**
On the first mirrored project a user is assigned a Studio-capable paid account
(preferring one whose plan advertises `studio`), stored in
`studio_suno_accounts` and never changed afterwards. That keeps every project a
user owns on one Suno account — the privacy property Suno actually enforces — and
makes the mapping predictable. If the pool is empty or has no paid account, the
mirror falls back to the normal picker so a sandbox still exercises the path.

**Still open:** whether provisioned users should each get a *dedicated* Suno
account (option 2) rather than sharing pool accounts (users on the same pool
account can see each other's projects in Suno's own UI). That is a procurement
and disclosure decision, not a code path: the link table already stores the pin,
so re-provisioning is a data migration, not a redesign.

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

**Phase 0 — schema capture. DONE (2026-11-13).**
Full schema, provenance and the live verification table are in
`SUNO_STUDIO_STATE_SCHEMA.md`. In short: 11 real projects were read, the nested
track/clip/MIDI shapes are known, and the contract was verified by creating,
saving twice, reading back and provoking a stale-version 409 on a throwaway
project (archived afterwards).

The client bundle facts that still anchor the contract:

| Fact | Evidence |
|---|---|
| `POST /api/studio/create-project?title=&major_version=` → `{id,title}` | chunk `3btgzx8fdnxv8.js` |
| `POST /api/studio/save-project` body `{project_id,state,title,base_version_id}` → `{version_id}` | same chunk |
| `409` carries `{latest_version_id}`; `429` is a rate limit | same chunk |
| `GET /api/studio/project/{id}` → `{state, latest_version_id, title, ...}`; `state` may be a JSON string | chunk `2u-vnr3lk1phb.js` |
| A loaded state must contain `timing` and `tracks` | same chunk |

**Phase 1 — create/list/link. DONE.**
Migration `0044`, link table, account pinning, coalescing outbox, create route,
status route and the editor's sync dot. Creating a local project queues exactly
one Suno project; an advisory lock makes retries idempotent.

**Phase 2 — save translation. DONE (live-verified).**
`studioStateCodec.ts` converts bpm/meter, master level, loop, tracks, mixer
values, MIDI clips and notes into Suno's document and back. It merges into the
last Suno document, so keys we do not model survive. Writes are on by default;
`STUDIO_SUNO_STATE_SYNC=0` is the kill switch.

Clips whose audio has no Suno asset are **not** represented; they are counted in
the link's `skipped_clip_ids` and surfaced in the sync chip, and existing Suno
audio clips are preserved untouched rather than dropped.

**Phase 3 — pull/reconcile. DONE.**
- `refresh` detects a newer Suno version (throttled) and marks the link `conflict`.
- The editor shows a conflict dialog with three honest choices:
  - **Load Suno version** — `POST /studio/projects/{id}/load-suno`. The server
    re-reads Suno, projects it with `sunoStateToProjectData`, and merges it into
    the local document (`mergeSunoProjectIntoLocal`): matched tracks/clips update,
    Suno-only ones are added, and local-only clips are **kept** and reported.
    The applied version is recorded so the next autosave is a no-op.
  - **Keep mine** — `POST /studio/projects/{id}/keep-mine` rebases onto Suno's
    observed version and pushes the local document.
  - **Duplicate locally** — forks the project; the copy mirrors as its own Suno
    project.
- `/internal/studio/sync/health` still reports the per-field coverage registry.

**Phase 4 — coverage matrix = removal list (D-034).**
Per-feature tests: tracks, clips, MIDI, effects, automation, markers, metadata,
archive. An unmapped local field is removed from the editor, not kept local-only.

**Phase 5 — operations.**
Sync status chip (done), admin diagnostics (`/internal/studio/sync/health`),
re-auth flow for dead Suno sessions, metrics and alerts.

## 12. Acceptance tests

| Case | Expected |
|---|---|
| Create local project | exactly one Suno project; link row `synced`; retry does not create a second |
| Edit local track/MIDI clip | Suno `project/{id}` state matches after the debounce; version advances (**verified on a live probe**) |
| Audio clip without a Suno asset | not silently dropped: counted in `skipped_clips`, Suno-side audio preserved |
| Edit in Suno | reopening the local project detects the newer version (`refresh` → `conflict`); applying it is Phase 3 |
| Both sides changed | `409`; no silent overwrite (**409 contract verified live**) |
| Suno offline | local edit saves; status `pending`; outbox retries; no data loss |
| Expired account | status `error`; no other account is tried |
| Other Camxora user | 404/403; no cross-account read or write |
| Unsupported local field | removed from the editor and the document (D-034), never carried local-only |

## 13. Open decisions before implementation

1. **Account policy:** one Suno account per Camxora user, a dedicated mirror
   account per user, or one shared demo account? (§9)
2. **Source of truth:** local-first with Suno mirror (recommended) or Suno-first
   with local cache?
3. **Pixel goal:** semantic/geometry parity (current D-025) or literal Suno
   palette/UI?
4. ~~**Unsupported fields:** keep local-only, or drop them when syncing?~~
   **Decided (D-034): drop them.** The Suno document is the truth; a feature with
   no Suno representation is removed from the editor.
5. **Suno ToS/private API approval:** do we have permission to write projects to
   the reference Studio for users?
6. **Sync cadence:** debounce interval and pull interval (suggested 1.5 s save /
   30 s pull while open).

Until §13 is decided, the safe implementation is Phase 0 only: capture the state
schema without writing user data.
