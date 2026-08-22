# Repo-root hygiene rebased onto current GitHub main

**Date:** 2026-08-19  
**Surfaces:** repo root / docs only (no running API or portal code)  
**Branch:** `chore/repo-root-hygiene` (now at `81c36308`, same as `origin/main`)

## Summary

This branch had **no unique commits**. The cleanup lived as uncommitted file
moves on a checkout that was **54 commits behind** GitHub `main`. A deploy
script packs `platform_api` (and other dirs) from **local disk**, so deploying
from that old tree would have shipped pre–Music-Web / pre–blog-auth API.

HEAD is now `81c36308` (PR #89). Hygiene is only root archive/gitignore/deletes.
Unfinished leftover files were not staged.

## Product impact

None for Music Web vs Studio billing (those stay separate). No UI or API
behavior change. Debug notes moved under `archive/`; accidental nested
`MusicGenerator/` and `auth_tokens.dat` are gitignored.

## Technical impact

- `chore/repo-root-hygiene` fast-forwarded to `origin/main`.
- Root debug markdown and `SLAI-IMG.json` moved to `archive/`.
- Removed leftover root scripts (`clean_home.py`, `clean_py.py`, `test_import.py`)
  and empty root `package-lock.json`.
- `.gitignore` ignores `/MusicGenerator/`, `auth_tokens.dat`, `camxora_rust/`,
  and `.leftover/`.

## Files touched

- `.gitignore`
- `.dev-pids` (removed from git)
- `MusicGenerator/auth_tokens.dat` (removed from git)
- `archive/debug-notes/*.md` (renames)
- `archive/http-collections/SLAI-IMG.json` (rename)
- `clean_home.py`, `clean_py.py`, `test_import.py`, `package-lock.json` (deleted)

Not included: DistroKid, desktop GUI test fixes. Unfinished local files were
moved to gitignored `.leftover/` so deploy tarballs cannot pick them up.

## Migration/deploy

No sandbox or production deploy. Hygiene is not in `DEPLOY_DIRS`. Runtime
code on disk now matches `origin/main` (`81c36308`). Production stays
untouched until an explicit production deploy from merged `main`.

## Tests

- `git rev-parse HEAD` = `origin/main` = `81c36308`
- Staged diff is hygiene paths only

## Follow-ups

- Commit/PR this hygiene set when asked.
- Production still runs the previous prod cut until “deploy to production”.
