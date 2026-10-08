# musicapi: generation-flow guard (require a prior owned generation)

## Summary

Derivative endpoints (`extend`, `cover`, `remaster`, `add_vocals`,
`add_instrumental`, `mashup`, `replace_section`, `stems`, `cover_image`, `wav`,
`midi`, `mp4`, `recovery`, `persona`, `voice_*`, `timestamped_lyrics_detail`,
and the `*_detail` reads) previously either performed **no ownership check at
all** (`meClipRoute`, `meResultRoute`, `/v1` `clipRoute`, `/me/stems`,
`/me/music/midi`, …) or only denied **foreign** assets while letting an
**unowned/unknown** id through (`assetOwnedByOtherUser`). So a caller could
request a derivative — e.g. timestamped lyrics, stems, a cover — for a clip they
never generated.

This adds a **positive prerequisite guard**: a derivative endpoint requires the
caller to own the referenced asset AND (when known) the job that produced it to
have **completed**. It ships **off by default**; enabling is a deliberate
operator action.

## Product impact

- When enabled, a clip can no longer be consumed without a prior owned,
  completed generation:
  - unknown/unowned clip id → `403 "No completed generation found for this asset."`
  - another user's clip id → `403 "This asset does not belong to your account."`
- Off by default, so behavior is unchanged until an operator turns it on
  (admin → Settings → Integrations → **Generation flow guard**).
- Root producers (`music`, `sounds`, `lyrics`, uploads) are unaffected; paid and
  read behavior otherwise unchanged.

## Technical impact

- `src/config.ts` — new `flowGuard.enforced` (`FLOW_GUARD_ENFORCED`, default
  false).
- `src/runtimeSettings.ts` — boot-time `FLOW_GUARD_DEFAULTS`; new
  `"Generation flow guard"` group in `INTEGRATION_GROUPS`; applied live in
  `applyToConfig()`.
- `src/server.ts`
  - `findAssetOwner(userId, assetId)` → `"caller" | "other" | "none"` (indexed
    `asset_owners` lookup, with the legacy result-JSON scan fallback).
  - `assetProducedByCompletedJob(assetId)` — joins `asset_owners.job_id → jobs.status`;
    legacy/unmapped rows are grandfathered.
  - `requireOwnedAsset(userId, assetId, { mustBeComplete })` → `"ok" | "foreign" |
    "unowned" | "incomplete"`; returns `"ok"` when the guard is disabled.
  - `enforceFlow(reply, userId, assetId)` — sends the 403 and returns false.
  - `assetIdsInBody(body)` — reads `clip_id`, `clip_ids`, `uploaded_clip_id(s)`,
    `audioId`/`audio_id` (excludes `taskId`, which may be a job id).
  - Wired into `meClipRoute`, `meResultRoute`, `/v1` `clipRoute`, `/v1/music/mashup`,
    `/me/stems`, `/me/{,music/}replace-section`, `/me/persona-create`,
    `/me/voice-generate`, `/me/{,music/}recovery`, `/v1/music/recovery`,
    `/me/music/wav`, `/v1/music/wav`, `/me/music/midi`, `/v1/music/midi`,
    `/me/mp4/generate`, `/v1/mp4/generate`.
  - All previous `assetOwnedByOtherUser` call sites upgraded to `enforceFlow`
    (deny-foreign-only → positive ownership + completion); the old helper is
    removed.

## Files touched

- `musicapi/src/config.ts`
- `musicapi/src/runtimeSettings.ts`
- `musicapi/src/server.ts`
- `musicapi/test/flow-guard.test.ts` (new)
- `musicapi/test/auth-guards.test.ts`
- `musicapi/test/run.ts`

## Migration / deploy

- No DB migration. Uses the existing `asset_owners` table and `jobs.status`.
- Deploy the API with the guard **off** (default). Enable afterwards via the
  admin Integrations toggle or `FLOW_GUARD_ENFORCED=true`.

## Tests

- `npm run typecheck` (musicapi) → clean.
- `npm run test:unit` → 69/69 pass (adds `flow-guard.test.ts`; updates
  `auth-guards.test.ts` to accept the new guard name).

## Follow-ups

- **Alias routes not yet guarded:** the `/api/v1/generate/*` and
  `/api/v1/convert-to-wav/*` compatibility handlers take a `clip_id` and call
  Suno directly; they still need the `enforceFlow` guard so the feature cannot
  be bypassed through the alias surface.
- Upload-session (`upload_extend`/`upload_cover`) and persona+clip
  (`voice_apply`/`voice_extend`) prerequisites are not yet modelled explicitly.
- A classification table (endpoint → required parent kind) plus a full coverage
  test that enumerates every clip-consuming route.
- Enable `FLOW_GUARD_ENFORCED` in production only after a smoke test.
