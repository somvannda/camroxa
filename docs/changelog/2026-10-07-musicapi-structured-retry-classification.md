# musicapi: classify Suno retryable failures structurally (not by message regex)

## Summary

The cross-account retry loop decided whether to retry a failed submit by
regex-matching the **error message** (`RETRYABLE_ERROR`). That is brittle: a
wording change in Suno's response body can silently turn a retryable failure
(402 "not enough credits", 429 "too many requests") back into a terminal one —
the exact class of bug that had to be patched in #367. This carries the HTTP
status and Suno's `error_type` on a typed error and classifies on those, keeping
the message regex only as a fallback. (Issue #369.)

## Product impact

- No behaviour change on the happy path. Retryable failures (402/429/5xx) still
  switch to another pooled account; terminal ones (400/422) still fail fast.
- More robust to upstream message changes — a retryable failure can no longer be
  misclassified as terminal by a body reword.

## Technical impact

- `src/sunoError.ts` (new): `SunoHttpError` (carries `status`, `errorType`) +
  `sunoHttpError(label, res)` builder + `isRetryableSunoError(err)` (structured
  first, message regex fallback).
- `src/client.ts`, `src/suno.ts`: the submit-path HTTP errors now throw
  `SunoHttpError` (message shape unchanged, so `jobs.error` / logs / admin
  "top causes" are identical).
- `src/server.ts`: retry loops use `isRetryableSunoError(e)` instead of
  `RETRYABLE_ERROR.test(msg)`; the local regex constant is removed.
- `test/suno-error.test.ts` (new): structured + fallback classification cases.

No schema change.

## Files touched

- `musicapi/src/sunoError.ts` (new)
- `musicapi/src/client.ts`
- `musicapi/src/suno.ts`
- `musicapi/src/server.ts`
- `musicapi/test/suno-error.test.ts` (new)
- `musicapi/test/run.ts`
- `docs/changelog/2026-10-07-musicapi-structured-retry-classification.md` (this file)

## Migration / deploy

- No migration. Normal sandbox-first deploy.

## Tests

- `npm run typecheck` (musicapi) → clean.
- `npm run test:unit` (musicapi) → all pass (5 new `isRetryableSunoError` cases:
  402/429/5xx retryable, `rate_limited` retryable, 400/422 terminal, regex
  fallback, non-Error handling).

## Follow-ups

- `sunoHttpError(...)` is now used at the Suno-API HTTP-error sites in
  `client.ts` (19 sites); a handful that use a different condition/status
  variable are left to the message fallback.
- #368: idempotency key for ambiguous timeout/5xx submits.
