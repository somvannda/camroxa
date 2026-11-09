# musicapi: tag credit exhaustion, alert before the pool hits zero

**Date:** 2026-11-01
**Branch:** `fix/musicapi-credit-signal`
**Surfaces:** musicapi

## Summary

Follow-up to `docs/changelog/2026-11-01-music-credit-exhaustion-not-a-rate-limit.md`.

`musicapi` answers `402 Insufficient credits.` and remaps it to `429` on the
public `/api/v1/*` surface for sunoapi.org compatibility. Callers could only
tell a billing stop from throttling by reading the message text, so platform_api
parked its whole key pool when the reseller account ran dry.

## Changes

- The `402 -> 429` remap now also sets `x-credit-exhausted: 1`, so clients get a
  machine-readable signal without changing the status code sunoapi.org expects.
- The alert evaluator now also watches **admin-owned API-key pools**: when an
  admin account's summed key credits fall to or below
  `low_credits_threshold`, the existing `low_credits` alert fires with the
  account email and balance. Previously only upstream Suno account balances were
  watched, so the reseller pool reaching 0 was silent until generation stopped.

## Product impact

- A drained reseller pool pages ops while there is still headroom to top up.
- No change to pricing, charging, or the 429 status code itself.

## Files touched

- `musicapi/src/server.ts`

## Verification

```
npx tsc --noEmit -p musicapi/tsconfig.json   # clean
npx tsx musicapi/test/run.ts                 # 132 passed
```
