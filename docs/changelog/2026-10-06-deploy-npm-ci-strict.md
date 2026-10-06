# Deploy scripts: drop the `npm ci || npm install` fallback

## Summary
Now that `website`, `user_portal`, `music_web` (and `admin_portal`) lockfiles are
known-good on the deploy toolchain (Node 20.20.2 / npm 10.8.2 — PR #343), the
deploy no longer needs the silent `npm ci || npm install` safety net. Removing it
makes a future lockfile drift **fail the deploy loudly** instead of silently
rewriting the remote lockfile. This implements the follow-up from
`2026-09-28-music-web-npm-lockfile-emnapi.md`.

## Product impact
None. Build-only; the lockfiles resolve cleanly with `npm ci` (verified on the
server for all three frontends in PR #343).

## Technical impact
- `camxora-sandbox-remote.sh` and `camxora-production-remote.sh`: the four
  frontend build steps now run `npm ci --no-audit --no-fund` only.

## Trade-off
A future Node/npm upgrade on the servers could re-introduce platform drift and
now hard-fails the deploy. That is intentional (loud failure); regenerate the
lockfiles with the server toolchain if it happens.

## Files touched
- `scripts/deploy/camxora-sandbox-remote.sh`
- `scripts/deploy/camxora-production-remote.sh`
