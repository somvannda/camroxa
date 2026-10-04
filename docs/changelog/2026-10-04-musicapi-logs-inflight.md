# musicapi: show in-flight jobs in the dashboard usage logs

## Summary

The dashboard logs (`/dashboard/logs`) read only `usage_logs`, which is written at
**finalize** — after Suno finishes generating and after the completed media is
copied to B2. A request therefore stayed invisible until the whole job settled,
which read as "the log is very slow". The page now merges the settled ledger with
the in-flight rows still in `jobs`, so a task shows `RUNNING`/`PENDING` from submit
and flips to `SUCCESS`/`FAILED` in place — matching how sunoapi.org's
`GET /api/v1/generate/record-info` exposes a task as `PENDING → TEXT_SUCCESS →
FIRST_SUCCESS → SUCCESS` while it runs.

## Product impact

- New requests appear on `/dashboard/logs` immediately as `RUNNING` (or `PENDING`),
  with the model, prompt and credit cost already shown, instead of only appearing
  once the audio is generated and mirrored to storage.
- When the job settles, the same row (same `taskId`) becomes `SUCCESS`/`FAILED`
  with its result and download actions — no duplicate row.
- Existing tabs (audio, recovery, lyrics, wav, …) filter both in-flight and settled
  rows the same way.
- The usage CSV export (`GET /me/logs`) is unchanged: it stays a settled-only,
  append-only record.

## Technical impact

- `musicapi/src/server.ts` — `GET /me/logs/page`
  - Replaced the single `usage_logs` query with a `UNION ALL` of
    `usage_logs` (settled) and `jobs` where
    `status IN ('pending','running','streaming')` (in-flight), projected to the
    same row shape (`id`, `endpoint`, `model`, `prompt`, `status`,
    `credits_consumed`, `task_id`, `result_json`, `created_at`).
  - Filter clauses (taskId, endpoint-tab patterns, date window) are built once per
    side of the union and share the same positional params; a running job that has
    not stamped `endpoint` yet falls back to its `type`.
  - A job leaves the `jobs` half the moment it finalizes into `usage_logs`, so
    there is exactly one row per task at any time (no de-dupe needed).
- `musicapi/web-user/app/dashboard/logs/page.tsx`
  - Row React key is now `task_id || id` so a row keeps its identity across the
    in-flight → settled transition.

No schema change. `usage_logs` remains append-only; billing queries are untouched.

## Files touched

- `musicapi/src/server.ts`
- `musicapi/web-user/app/dashboard/logs/page.tsx`
- `docs/changelog/2026-10-04-musicapi-logs-inflight.md` (this file)

## Migration / deploy

- No migration. Deploy via the normal sandbox-first chain
  (`scripts/deploy/sync_musicapi_sandbox.py`, then the production twin) — the core
  API and web-user both change.

## Tests

- `npm run typecheck` (musicapi) → clean.
- `npm run typecheck` (web-user) → clean.
- The generated union SQL was `EXPLAIN`'d against the production `sunoapi`
  database (read-only): valid plan, no errors; the count query returned correctly.

## Follow-ups

- The handoff point is when the job lands in `jobs`, which currently happens
  inside the runner after it acquires a Suno slot. Persisting the job at request
  time (before slot acquisition) would make rows appear even for capacity-queued
  jobs; today a saturated pool can still delay the first appearance.
