# Verified source deploys — production can only ship a commit of `main`

**Date:** 2026-11-03
**Area:** deploy tooling (`scripts/deploy/`), project rules
**Why:** repeated "the deploy reverted my fix" incidents.

## Problem

Every deploy packaged **whatever files were in the working tree of the worktree
the script was launched from**, then `tar -xzf`'d them over `/opt/camxora/repo`.
Consequences seen in production:

- deploying from an old branch/worktree shipped old code and silently reverted
  newer commits (and the image thumbnail / background ordering change, which
  only ever existed on the server, disappeared);
- a **tag excused an unmerged HEAD**, so `feat/postforme-publishing` was live
  from 2026-11-02 while not being on `main`;
- `tar` never deletes, so files removed upstream lingered and could shadow the
  new module;
- nobody could answer "which commit is live?" — `.deployed.json` recorded the
  local HEAD, not the bytes that landed.

## Change

Production now ships **one commit**, packaged from git, and the server proves it.

| Piece | What it does |
|-------|--------------|
| `scripts/deploy/release_source.py` | `git archive` of one commit (only committed content, LF-normalized) + `.deploy-manifest.json` with sha256 per shipped file; self-verifies the archive |
| `scripts/deploy/verify_release_manifest.py` | stdlib-only verifier: re-hashes every file on the server, aborts on missing/mismatched, prunes files the previous deploy shipped that this one does not |
| `scripts/deploy/deploy_production.py` | fetch → resolve `origin/main` → gate → package → verify on the server; records source provenance |
| `scripts/deploy/deploy_guards.py` | `require_merged` makes `origin/main` ancestry mandatory for production; a tag no longer bypasses it; the gate judges the **source commit**, not HEAD |
| `camxora-production-remote.sh`, `camxora-sandbox-remote.sh` | verify the manifest right after extraction and **stop before builds/restarts** on mismatch |
| `sync_platform_api_production.py`, `sync_music_web_production.py`, `deploy_music_streaming_production.py` | same commit-based packaging and scoped verification |
| `AGENTS.md`, `.cursor/rules/*` | the rules are now explicit for every agent/worktree |

Runtime state that is not code (`uploads/`, `dist/`, `.next/`, `.env`,
`musicapi/`) is never in a manifest, so it is never pruned, and the `musicapi`
checkout keeps being restored from the previous deploy.

## Multi-agent effect

Because the source is a commit, the state of any agent's worktree cannot change
what production runs. Only what is merged to `origin/main` can ship, and a
concurrent deploy is refused by the server lock.

## Escape hatches (deliberate, recorded)

`CAMXORA_DEPLOY_SOURCE=worktree`, `CAMXORA_DEPLOY_SOURCE_REF=<ref>`,
`CAMXORA_ALLOW_UNMERGED_DEPLOY=1`, `CAMXORA_ALLOW_DIRTY_DEPLOY=1`,
`CAMXORA_ALLOW_CONCURRENT_DEPLOY=1`. Each is recorded in `.deployed.json`
(`source_mode`, `merged_to_base`, `dirty`).

## Tests

`platform_api/tests/test_release_source.py` covers: untracked files never ship,
the archive follows the commit (not the worktree), LF normalization, drift
detection, stale-file pruning that leaves runtime files alone, and the
production rule that a tag no longer excuses an unmerged branch.

`platform_api/tests/test_deploy_hygiene.py` covers the CI gate: tarball
extraction / `sftp.put` / `cp` / pathlib edits into `/opt/camxora/repo` are
rejected unless the script uses the verified-source pipeline, while read-only
checks and runtime paths (`.env`, `uploads/`, `.next/`, `.deployed.json`) are
not flagged.

## Closing the other hole

Deploy scripts are not the only way old code can reach production: ~99 legacy
`*production*.py` one-shot scripts still patch `/opt/camxora/repo` directly.

- `scripts/deploy/check_deploy_hygiene.py` scans them. CI fails any PR that adds
  or edits one without the verified pipeline; pre-existing one-shot scripts are
  reported and allowlisted in `--strict` so the check stays actionable.
- `python scripts/deploy/check_deploy_guards.py production --verify-live` now
  re-hashes the live checkout against the deployed manifest, so any in-place
  server edit (or a legacy script that ran) shows up as drift instead of
  silently surviving until it is blamed on a later deploy.
- Per-surface syncs were converted too: `sync_admin_portal_production.py` now
  packages `origin/main` (it used to tar the local `admin_portal` directory),
  and `deploy_musicapi_production.py` requires `HEAD == origin/main` because its
  remote pipeline still stages the working tree.

## Follow-up (same day, from the first live deploy)

The first real deploy exposed two gaps, fixed here:

- **`*.egg-info` broke verification.** The five `platform_api/platform_api.egg-info/*`
  files are tracked in git (even though `.gitignore` says `*.egg-info/`), so they
  were in the manifest — and `pip install -e .` regenerates them right after the
  extract, so `--verify-live` reported `DEPLOY_VERIFY_FAILED` on hashes the
  deploy itself changed. Generated packaging metadata is now excluded from the
  archive and manifest.
- **The lock and marker lived inside the swapped checkout.** A full deploy moves
  `repo/` to `repo.bak.*` before extracting, which moved `.deploy.lock` and
  `.deployed.json` with it: the lock stopped refusing concurrent deploys for the
  duration of the run, and `--verify-live` reported `no-manifest` mid-deploy.
  Both now live beside the checkout (`/opt/camxora/.deploy.lock`,
  `/opt/camxora/.deployed.json`).
- **The post-deploy health probe was too eager.** A single `curl` after
  `sleep 3` logged `WARN: API health check failed` while the 4 uvicorn workers
  were still booting, even though the API answered 200 seconds later. It now
  polls for up to 60 s and only warns if the API is genuinely down.

## Not changed

Production still runs `2fca5548` (`feat/postforme-publishing`, 2026-11-02) until
merged `main` is deployed with this change. The lost thumbnail change needs to
be recovered from its worktree, merged to `main`, and deployed.
