# Debug Session: youtube-upload-issues

Status: [OPEN]

## Summary
YouTube uploading is unreliable/challenging. We need runtime evidence to pinpoint which stage fails (MP4 readiness, OAuth refresh, upload chunks, thumbnail/playlist, or job-looping).

## Hypotheses (Falsifiable)
- **A — OAuth refresh instability**: `creds.refresh(Request())` fails intermittently (DNS/proxy/firewall/expired refresh token), causing repeated failures.
- **B — MP4 readiness loop**: merged MP4 is still changing/locked/invalid, causing the job to bounce back to `PENDING` and appear like repeated uploads.
- **C — Upload chunk failures**: `req.next_chunk()` throws (429 quota, 403 permission, 5xx, network resets) leading to retries and restart behavior.
- **D — Post-actions fail**: thumbnail/playlist calls fail in a way that marks jobs failed or causes repeated retries.
- **E — Job claim/re-enqueue duplication**: auto-scan and job claiming logic causes the same job to be re-opened unexpectedly.

## Instrumentation Plan (First)
Add debug events (to Debug Server) at:
1) Worker pick + job meta (jobUid, attemptCount, batch/profile/role)
2) MP4 readiness decision + reason
3) OAuth refresh start/success/failure
4) Upload start/success/failure (exception type + HTTP status if present)
5) Post-actions result (thumbnail/playlist warnings)

## Repro Checklist (Boss)
1) Keep Debug Server running.
2) Start a YouTube upload (auto or manual retry).
3) Wait until it either succeeds or fails/retries.
4) Send me:
   - the visible UI error text
   - the approximate time window (HH:MM:SS)

## Notes
- Instrumentation must not log secrets (client secret / refresh token).

