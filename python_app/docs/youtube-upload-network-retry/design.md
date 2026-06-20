# YouTube Upload: Network/DNS Retry (UX)

## Problem
- During upload, the OAuth token request can fail due to DNS resolution issues.
- These failures are usually temporary, but the job was being marked `FAILED`, forcing manual intervention.

## Desired UX
- If DNS/network is temporarily broken:
  - Job automatically retries a few times.
  - Status messaging should indicate it will retry (rather than appearing “hard failed”).
- If the problem persists:
  - Job ends in `FAILED` with a clear error message for Boss to fix network/DNS.

