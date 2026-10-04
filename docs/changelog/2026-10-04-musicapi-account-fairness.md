# musicapi: spread jobs across Suno accounts (least-loaded + per-account cap)

## Summary

The concurrency gate (#237/#242) caps how many jobs run **in total**, but account
selection was first-fit: `pool.pickExcept` returned the first healthy account, so
a burst could land mostly on one account while the rest of a small pool sat idle.
With 2 Premier accounts that means avoidable 429s/captchas on the busy account and
under-used capacity on the other. This makes selection **least-loaded-first** and
adds a per-account in-flight cap.

## Product impact

- A burst now **spreads across the pool**: each new job goes to the account with
  the fewest in-flight jobs. With `N` accounts and a global ceiling of `G`, no
  account ends up with more than `ceil(G/N)` in flight.
- An account already at `SUNO_MAX_CONCURRENT_PER_ACCOUNT` (default 4) is used only
  when no under-cap account is available, so one account can't be hammered.
- Routing preference is preserved: `prefer_free` still prefers free accounts
  first, then balances load within that tier.

## Technical impact

- `src/pool.ts`
  - New pure, exported `orderByLoad(clients, load, {preferFree, maxPerAccount})`
    that ranks candidates by routing preference → under-cap → least in-flight.
  - `pick`, `pickExcept`, `pickFeature`, `pickFeatureExcept` accept an optional
    `{ load, maxPerAccount }` and order candidates through `orderByLoad`.
    Callers that don't pass it keep the previous order (all loads equal, stable
    sort), so non-job paths are unchanged.
- `src/server.ts`
  - In-process `accountInflight` map + `markAccountStart/End`, applied around each
    attempt in `runClipJobWithRetryImpl` / `runResultJobWithRetryImpl` (the two
    job execution paths). Counts release in a `finally`, so they can't leak.
  - The job paths pass `{ load: accountLoad, maxPerAccount }` to account selection.
  - `/metrics` `suno` block adds `maxConcurrentPerAccount` and `byAccount`
    (in-flight per account).
- `src/config.ts`: `suno.maxConcurrentPerAccount` (`SUNO_MAX_CONCURRENT_PER_ACCOUNT`,
  default 4).

No schema change.

## Files touched

- `musicapi/src/pool.ts`
- `musicapi/src/server.ts`
- `musicapi/src/config.ts`
- `musicapi/.env.example`
- `docs/changelog/2026-10-04-musicapi-account-fairness.md` (this file)

## Migration / deploy

- No migration. Deploy via the normal sandbox-first chain. New optional env:
  `SUNO_MAX_CONCURRENT_PER_ACCOUNT` (default 4).

## Tests

- `npm run typecheck` (musicapi) → clean.
- Unit probe of `orderByLoad`: stable order when no load; least-loaded ordering;
  `prefer_free` tier-before-load; over-cap accounts ordered last.
- Bounded property (simulated dispatch): with capacity `A × K` and cap `K`, the
  busiest account never exceeds `ceil(G/A)` — 2 accounts/8 → max 4; 3/7 → max 3;
  1/4 → max 4. Temp harness removed after.

## Follow-ups

- Rebalance on account health: a healthy account that just recovered re-enters
  rotation immediately (already true — it becomes least-loaded).
- Optional: expose per-account load in the admin console (today only in `/metrics`).
