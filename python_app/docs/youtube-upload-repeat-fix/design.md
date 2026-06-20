# YouTube Upload: Prevent Repeat Upload Loop (UX)

## Problem
- Boss sees the same YouTube upload start repeatedly (“again and again”).

## Expected UX
- While the merged MP4 is still being produced:
  - The job may wait/retry a few times, but it should not spam uploads forever.
- If the merged MP4 output is invalid/corrupt:
  - The job should stop and show a clear failure message explaining what to fix.
- Upload retries should remain:
  - Automatic and bounded for transient network/API failures.

