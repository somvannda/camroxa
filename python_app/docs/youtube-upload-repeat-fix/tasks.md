# YouTube Upload: Prevent Repeat Upload Loop

## Goals
- Prevent jobs from cycling `RUNNING → PENDING → RUNNING` forever.
- Ensure “MP4 not ready yet” validation does not cause infinite retries.
- Preserve normal retry behavior for transient network/API errors.

## Tasks
- [completed] Inspect auto-scan enqueue + worker retry paths and identify why uploads repeat.
- [pending] Implement bounded MP4-readiness retries:
  - Store the real readiness reason in `error`.
  - Increment `attempt_count` and cap retries.
  - Mark job `FAILED` with a clear message when the output is invalid/unrecoverable.
- [pending] Verify:
  - When merged MP4 is still being written, job retries a limited number of times.
  - When merged MP4 is corrupt/invalid, job fails and stops re-uploading.
  - When network is transient, existing transient retry still works (bounded).
- [pending] Update `DEVELOPMENT_LOG.md`.

