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

## Not changed

Production still runs `2fca5548` (`feat/postforme-publishing`, 2026-11-02) until
merged `main` is deployed with this change. The lost thumbnail change needs to
be recovered from its worktree, merged to `main`, and deployed.
