# Music portal lockfile missing `@emnapi/*` broke `npm ci` on Linux

**Date:** 2026-09-28
**Branch:** `fix/music-web-lockfile-emnapi`
**Surfaces:** music_web
**Status:** implemented (sandbox)

## Summary

Deploys of `music_web` were relying on the deploy script's
`npm ci || npm install` fallback. On the server, `npm ci` threw
`EUSAGE` ("Missing: `@emnapi/runtime@1.11.3` from lock file",
"Missing: `@emnapi/core@1.11.3` from lock file") and the build only
succeeded because the script silently fell back to `npm install`, which
regenerated `package-lock.json` **on the server** (Linux-canonical).

Root cause is platform/version divergence, not a dependency change. The
committed lockfile was generated on Windows (node 24.13.0 / npm 11.6.2),
while the sandbox builds on Linux (node 22.21.0 / npm 11.7.0). The
Linux/npm 11.7.0 resolver requires two top-level wasm shim packages that
the Windows lockfile never recorded:

- `@emnapi/core@1.11.3` — pulled in by `@napi-rs/wasm-runtime`'s
  `@emnapi/core` peerDep (`^1.7.1`)
- `@emnapi/runtime@1.11.3` — pulled in by `@img/sharp-wasm32`
  (`@emnapi/runtime@^1.7.0`) and by `@napi-rs/wasm-runtime`'s
  `@emnapi/runtime` peerDep (`^1.7.1`)

The same divergence had also mis-marked 16 **direct** dependencies as
`"peer": true` (e.g. `react`, `react-dom`, `typescript`, `tailwindcss`,
`postcss`, `eslint`), which is incorrect for direct deps and a second
source of `npm ci` churn.

## Product impact

- None directly visible to listeners. The music portal build is
  unchanged in version terms: **zero dependency versions changed**.
- Deploy reliability: `npm ci` now succeeds on the Linux server, so builds
  no longer depend on the `npm install` fallback rewriting the remote
  lockfile.

## Technical impact

- `music_web/package-lock.json` replaced with the server-canonical
  (Linux/npm 11.7.0) full-resolution lockfile. Diff: `1 file changed,
  24 insertions(+), 16 deletions(-)`.
  - `+ node_modules/@emnapi/core` @ 1.11.3 (`dev`, `optional`, `peer`;
    deps `@emnapi/wasi-threads@1.2.3`, `tslib@^2.4.0`)
  - `+ node_modules/@emnapi/runtime` @ 1.11.3 (`optional`; dep
    `tslib@^2.4.0`)
  - `+ "peer": true` added to `node_modules/@emnapi/wasi-threads`
    (correct: it is a peer-only chain member)
  - `- "peer": true` removed from 16 entries that are **direct**
    dependencies: `@babel/core`, `@types/react`, `@types/react-dom`,
    `@typescript-eslint/parser`, `acorn`, `browserslist`, `eslint`,
    `eslint-plugin-import`, `jiti`, `postcss`, `react`, `react-dom`,
    `tailwindcss`, `tinyglobby/node_modules/picomatch`, `typescript`,
    `zod`.
- `lockfileVersion` stays 3; package count 494 → 496 (the two added
  `@emnapi` entries). No `package.json` change.

## Files touched

- `music_web/package-lock.json`
- `music_web/CHANGELOG.md`

## Migration / deploy

- No DB migration, no runtime config change.
- Deploy: `python scripts/deploy/rebuild_music_web_sandbox.py`
  (unpacks `music_web`, runs `npm ci` / build, restarts
  `camxora-music`). Sandbox first; production only on explicit request.

## Tests

- Local Windows `npm ci --dry-run` on the fixed lockfile → resolves
  436 packages, exit 0.
- Server verification after deploy: local fixed-lockfile sha256 equals
  the deployed `/opt/camxora/repo/music_web/package-lock.json` sha256
  (`ba25f350764a50a539dbd0b19eba6b62454b1c14710819ad6dae0255b6b601f6`),
  and `npm ci --dry-run --no-audit --no-fund` on the server exits 0
  ("up to date in 2s") with no `Missing:` lines.

## Follow-ups

- Production `music_web` still carries the old lockfile; deploy there
  only on explicit request.
- The deploy scripts keep `npm ci || npm install` as a safety net. It
  masks lockfile drift by rewriting the remote lockfile; consider
  failing loudly instead once the lockfile is known-good across
  platforms.
