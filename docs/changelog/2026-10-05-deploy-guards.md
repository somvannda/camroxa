# Deploy guards: clean worktree, deployable ref, deploy lock, deployed-SHA marker, runtime invariants

**Date:** 2026-10-05

## Why

Several agents deployed production from different worktrees within the same hour,
including a deploy whose source existed in **no commit**. After the fact, nobody
could answer "what is actually live?" without reverse-engineering the deployed code
into git blob hashes, and there was no automated check that a newer deploy had not
silently reverted another agent's fix (the AI-routing / recovery-guard work, `#286`).

This complements the migration-consistency guard (`#292`) — that checks the DB
revision; this checks **what code** ships, **who is deploying at the same time**,
and **that critical paths survived**.

## What

New `scripts/deploy/deploy_guards.py`, wired into the platform_api sync/deploy scripts.

### Pre-deploy (local git, fail-closed — production only)

- **Clean worktree** — refuse to deploy when `git status --porcelain` is non-empty.
- **Deployable ref** — refuse unless `HEAD` is tagged or is an ancestor of the base
  ref (default `origin/main`), so a stale/WIP branch cannot clobber a newer deploy.

### Concurrent-deploy lock (server-side, production only)

- Atomically claims `/opt/camxora/repo/.deploy.lock` (`set -o noclobber`); exits
  non-zero with the current holder when another deploy is in progress.
- **TTL** (default 1h) so a crashed deploy cannot wedge the lock; a stale lock is
  reclaimed automatically. Released by the owning deploy in a `finally` block.

### Post-deploy (over SSH)

- **Runtime invariants** — assert the paths that must survive every deploy:
  - `platform_api/services/suno_audio_resolver.py`: `_DASHED_UUID_RE`, `RECOVERY_AUDIO_ENABLED`
  - `platform_api/services/ai_routing_service.py` present
  - `platform_api/clients/suno_client.py`: `active_provider_is_musicapi`
  - `platform_api/services/batch_service.py`: `_recover_download_url`
  - Fatal on production; **warning only on sandbox** (WIP branches are expected).
- **Deployed marker** — write `/opt/camxora/repo/.deployed.json`
  (`commit`, `branch`, `tag`, `merged_to_base`, `guards`, `invariants`, `deployed_at`,
  `deployed_by`, `script`) so "what's live" is one `cat`, not a hash hunt.

## Wiring

- `scripts/deploy/sync_platform_api_production.py` — gate + lock + invariants + marker
- `scripts/deploy/deploy_production.py` — gate + lock + invariants + marker
- `scripts/deploy/sync_platform_api_sandbox.py` — marker + non-fatal invariants (no gate/lock)
- `scripts/deploy/check_deploy_guards.py` — standalone preflight
  (`python scripts/deploy/check_deploy_guards.py [production|sandbox]`)

## Escape hatches (deliberate hotfixes)

```
CAMXORA_ALLOW_DIRTY_DEPLOY=1        # allow an uncommitted worktree
CAMXORA_ALLOW_UNMERGED_DEPLOY=1     # allow a HEAD not tagged/merged to the base ref
CAMXORA_ALLOW_CONCURRENT_DEPLOY=1   # ignore a held deploy lock
CAMXORA_DEPLOY_BASE_REF=...         # override base ref (default origin/main)
CAMXORA_DEPLOY_ACTOR=...            # name recorded as the deployer in the marker
```

## Tests

`platform_api/tests/test_deploy_guards.py` — parsing, gate decisions, env overrides,
marker payload/IO, invariant script + enforcement, deploy-lock acquisition/release
(including the non-owner no-op), and the sandbox non-fatal path.
