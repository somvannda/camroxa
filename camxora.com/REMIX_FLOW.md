# Remix Flow Spec

Status: **Library + Staff Picks implemented; Staff Picks remix blocked by Premier credits**
Owner surface: `camxora.com/components/CreateStudio.tsx`
Backend path: **web → platform_api → musicapi → Suno**
Production deploy: **not approved** — sandbox only after the checklist passes.

## 1. Purpose

Match Suno’s Remix flow without calling Suno from the browser.

Entry points:

- Song row `⋯ → Remix`
- Track detail rail `Remix`
- Future: release/playlist cards

## 2. High-level flow

1. User clicks **Remix**.
2. `Choose a song to Remix` modal opens.
3. User selects a song and version.
4. Modal closes; the composer enters **Remix mode** with a source chip.
5. User edits prompt / style / lyrics / model.
6. **Create** submits the remix through `platform_api`.
7. `platform_api` validates ownership and calls `musicapi`.
8. `musicapi` calls Suno’s cover/remix path.
9. UI polls the operation/task and shows the result in the feed.
10. Removing the source chip exits Remix mode without submitting.

## 3. Remix picker modal

### Header

- Title: `Choose a song to Remix`
- Close button.

### Tabs

| Tab | Source | Status |
|---|---|---|
| **Library** | Current user’s generations | Ready — use existing generation list |
| **For You** | Curated/recommended public songs | **Blocked** — no catalog source yet |
| **Staff Picks** | Curated public songs | **Blocked** — no catalog source yet |

Only **Library** ships in the first implementation. The other tabs must not be
shown as functional until a real catalog endpoint exists.

### Library tab controls

- Search by title/style.
- Filters:
  - status (`Ready`)
  - model
  - instrumental / vocal
  - version availability
- Sort:
  - Newest
  - Oldest
  - Title A–Z
- Pagination or infinite list.
- 50 rows per page (match `/library`).

### Row content

- Cover image (with fallback).
- Title.
- Model badge (`V6`, `V6-MINI`, …).
- Style/tags (single-line truncation).
- Ready state.
- Version availability (`V1`, `V2`).
- `Remix` button.

### Row behavior

- Rows without a ready clip cannot be remixed.
- Rows without `audio_id_ok`/`audio_id_alt` cannot be remixed.
- Clicking `Remix` selects the preferred ready version (`ok` first, else `alt`) and closes the picker.

### States

- Loading skeleton.
- Empty: `No songs to remix yet. Create a song first.`
- Error: retry button.
- Filtered empty: `No songs match these filters.`

## 4. Composer in Remix mode

- Source chip inside the prompt area:
  - cover thumbnail
  - title
  - version label
  - remove `×`
- Chip removal exits Remix mode.
- Attach menu remains available (Image / Voice / Audio).
- Create button label can remain `Create`; the chip communicates remix.

### Submission contract

`platform_api` validates:

- task belongs to the authenticated user
- task source is `web_music`
- selected version has a provider clip id
- source task is not pending/failed

First implementation uses the existing cover operation:

```http
POST /api/v3/web-music/studio/generations/{task_id}/cover
{
  "variant": "ok",
  "prompt": "rework this as a house track",
  "project_id": null
}
```

Response is a Studio operation:

```json
{
  "id": "…",
  "status": "pending",
  "operation_type": "cover",
  "mode": "cover",
  "task_id": "…",
  "variant": "ok",
  "provider_clip_id": "…"
}
```

Poll:

```http
GET /api/v3/web-music/studio/operations/{operation_id}
```

Terminal states: `complete`, `error`, `failed`.

### Musicapi

Existing route:

```http
POST /internal/studio/cover
x-internal-token: …
{
  "clip_id": "…",
  "prompt": "rework this as a house track"
}
```

Maps to `SunoClient.coverMusic()` (`SIMPLE_REMIX`).

Do **not** add a second remix route until we verify Suno’s Remix differs from
Cover. If it differs, add one internal route and one platform proxy, not both.

## 5. Billing

- Charge through the existing Studio operation pricing path.
- No hardcoded price in the route or UI.
- Failed operations refund through the existing Studio refund path.

## 6. Data / storage

- No B2 upload required for a basic remix.
- Source task and provider clip id come from `suno_tasks`.
- No new table for the Library path.
- If “For You / Staff Picks” becomes real, add a catalog table or use a curated
  playlist source.

## 7. UI state machine

```
idle
  → picker_open
  → source_selected
  → remix_queued
  → remix_running
  → remix_complete
  → idle
```

Failure branches:

```
source_selected → error (invalid source)
remix_queued   → error (submit failed)
remix_running  → error (provider failed, refund)
```

Cancel branches:

- `picker_open → idle`
- `source_selected → idle` (remove chip / choose another)

## 8. Edge cases

- Source task deleted after selection → submit returns 404; show error and clear chip.
- Source has no provider clip id → disable Remix in picker.
- Source is pending → disable Remix.
- User has no ready songs → empty state.
- Operation succeeds but the result is not yet in the feed → refresh operations/generations.
- Duplicate submission → disable Create while an operation is pending.
- User switches workspace while picker is open → close picker.
- Model mismatch → do not silently change model; show an error if Suno rejects.
- Auth expired mid-flow → prompt sign-in and preserve source selection if safe.

## 9. Implementation checklist

### Web

- [x] `RemixPicker` modal component.
- [x] Library tab + search/sort + model/type filters.
- [x] Row selection uses the preferred ready version.
- [x] `remixSource` state in `CreateStudio`.
- [x] Source chip with remove.
- [x] Create submits cover/remix operation.
- [x] Poll operation and refresh Audio results.
- [x] Empty/error states.
- [x] Disable unsupported rows.
- [x] Row-menu entry point, detail-rail Remix button, and Library row/rail deep link.

### Platform API

- [x] Confirm `/studio/generations/{task_id}/cover` contract fits Remix.
- [ ] Optional alias `POST /web-music/remix` **only if** the UI contract needs it.
- [x] Ownership/readiness validation (existing path; ownership denial not exercised).
- [x] Pricing via Studio path (12-credit charge observed; failure refund not tested).

### Musicapi

- [x] Verify `/internal/studio/cover` payload matches Suno Remix.
- [x] No `/internal/studio/remix` needed — the cover route produced a completed remix.

### Tests

- [x] Library picker loads ready songs only.
- [x] Search and sort.
- [x] Remix uses preferred ready version.
- [x] Submit creates operation with correct `task_id` + `variant`.
- [x] Success shows the remix result in Audio results.
- [x] Failure shows refund/error — provider failure returned 502, operation marked `error`, 12 credits refunded.
- [x] Remove chip cancels mode.
- [x] Permissions: another user’s task returns 404 `Generation not found.`

## 10. Open questions / blockers

1. **For You data source** — no personalized catalog exists.
2. **Staff Picks remix success** — catalog and admin management are implemented,
   but remix requires a pool account with credits. The Premier catalog account
   currently has 0 credits, so the provider returned 402 and the operation refunded.
5. **Visibility** — remix result goes to the user’s library only, or can target a
   playlist/workspace?

Until 1–2 are confirmed, only the **Library → cover-based remix** path should
ship and be labeled as implemented. Do not show For You / Staff Picks as working.
