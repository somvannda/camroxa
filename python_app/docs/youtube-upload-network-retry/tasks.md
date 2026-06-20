# YouTube Upload: Network/DNS Retry

## Goals
- Treat transient network failures (especially DNS resolution failures) as retryable.
- Avoid marking jobs permanently `FAILED` when the machine temporarily cannot resolve `oauth2.googleapis.com`.

## Tasks
- [completed] Inspect current retry logic and error classification in the YouTube upload worker.
- [completed] Expand transient detection to include DNS/name-resolution failures.
- [pending] Verify on a real failure:
  - Job flips to `PENDING` (retry) up to the retry limit.
  - UI shows retry state correctly (Progress/Workflow).
- [pending] Document change in `DEVELOPMENT_LOG.md`.

