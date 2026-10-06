# Frontend lockfiles: sync website/user_portal so `npm ci` stops erroring

## Summary
Deploys printed `npm ci` errors for `website`, `user_portal`, and (`music_web`)
because their committed `package-lock.json` files were generated with a newer
local Node/npm (24 / 11.6.2) than the server (Node 20.20.2 / npm 10.8.2) and had
drifted from `package.json`. The deploy self-recovered via
`npm ci || npm install`, so builds still succeeded, but the errors were noise and
`npm ci` could not be relied on.

## Product impact
None. Build output only.

## Root cause
The lockfiles pinned `@emnapi/wasi-threads@1.2.2` and omitted top-level
`@emnapi/runtime`/`@emnapi/core`. The server's npm requires
`@emnapi/wasi-threads@1.2.3` plus `@emnapi/runtime@1.11.3` and
`@emnapi/core@1.11.3`, so strict `npm ci` rejected the lockfile while lenient
`npm install` tolerated it.

## Fix
Regenerated `website/package-lock.json` and `user_portal/package-lock.json` with
the **server's** toolchain (Linux, Node 20.20.2 / npm 10.8.2) and validated with
`npm ci` (exit 0). `music_web/package-lock.json` was already in sync.

## Verification
- Server: `npm install --package-lock-only` then `npm ci --dry-run` in
  `website`, `user_portal`, `music_web` → all `gen_exit=0`, `ci_exit=0`.

## Files touched
- `website/package-lock.json`
- `user_portal/package-lock.json`
