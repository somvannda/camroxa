# YouTube Upload: Network/DNS Retry (Technical)

## Existing Behavior (Verified)
- Retry decision is made in `MainWindow._run_one_youtube_upload_job` exception handler:
  - `transient=True` for HTTP 5xx and some timeout strings.
  - Otherwise, the job is marked `FAILED`.

## Root Cause
- DNS/name resolution failures (e.g. `NameResolutionError`, `Failed to resolve`, `Errno 1100`) were not classified as transient.

## Change
- Extend transient detection to include common DNS resolution failure signatures:
  - `failed to resolve`
  - `name resolution` / `nameresolutionerror`
  - `getaddrinfo failed`
  - `temporary failure in name resolution`
  - `errno 1100`

## File(s)
- `python_app/app/main_window.py`

## Verification Strategy
- Force a DNS failure (disconnect network or block DNS briefly) during upload.
- Confirm job transitions:
  - `RUNNING` → `PENDING` (retry) until retry limit
  - eventually `READY` after network recovers, or `FAILED` after retries are exhausted.

