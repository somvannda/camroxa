# Deploy guards: clean worktree, deployable ref, deployed-SHA marker, runtime invariants

**Date:** 2026-10-05

## Why

Several agents deployed production from different worktrees within the same hour,
including a deploy whose source existed in **no commit**. After the fact, nobody
could answer "what is actually live?" without reverse-engineering the codebase into
git blob hashes, and there was no automated check that a newer deploy had not
silently reverted another agent's fix (the AI-routing / recovery-guard work).

## What

New `scripts/deploy/deploy_guards.py`, wired into the production deploy scripts.

Pre-deploy (local git, fail-closed):

- **Clean worktree** — refuse to deploy when `git status --porcelain` is non-empty.
- **Deployable ref** — refuse unless `HEAD` is tagged or is an ancestor of the base
  ref (default `origin/main`), so a stale/WIP branch cannot clobber a newer deploy.

Post-deploy (over SSH):

- **Runtime invariants** — assert the critical paths that must survive every deploy:
  - `platform_api/services/suno_audio_resolver.py`: `_DASHED_UUID_RE`, `RECOVERY_AUDIO_ENABLED`
  - `platform_api/services/ai_routing_service.py` present
  - `platform_api/clients/suno_client.py`: `active_provider_is_musicapi`
  - `platform_api/services/batch_service.py`: `_recover_download_url`
- **Deployed marker** — write `/opt/camxora/repo/.deployed.json`
  (`commit`, `branch`, `tag`, `merged_to_base`, `guards`, `invariants`, `deployed_at`,
  `deployed_by`, `script`) so "what's live" is one `cat`, not a hash hunt.

## Wiring

- `scripts/deploy/sync_platform_api_production.py`
- `scripts/deploy/deploy_production.py`
- `scripts/deploy/check_deploy_guards.py` — standalone preflight
  (`python scripts/deploy/check_deploy_guards.py [production|sandbox]`)

## Escape hatches (deliberate hotfixes)

```
CAMXORA_ALLOW_DIRTY_DEPLOY=1       # allow an uncommitted worktree
CAMXORA_ALLOW_UNMERGED_DEPLOY=1    # allow a HEAD not tagged/merged to the base ref
CAMXORA_DEPLOY_BASE_REF=...        # override base ref (default origin/main)
CAMXORA_DEPLOY_ACTOR=...           # name recorded as the deployer in the marker
```

## Tests

`platform_api/tests/test_deploy_guards.py` (13 tests) — parsing, gate decisions,
env overrides, marker payload/IO, invariant script + enforcement.
