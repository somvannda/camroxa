# v1.0.9: unified release branch (desktop + backend) + Alembic head merge

**Date:** 2026-08-01
**Status:** shipped — deployed to sandbox and production, desktop installers built for both

## Summary

Two problems, one fix. First: sandbox's `alembic_version` table had **two independent,
un-merged heads** (`075_batch_channel_pipeline_complete` and the parked/unreleased
`077_batch_auto_distrokid` from `feature/distrokid`) — a bare `alembic upgrade head`
already can't run on sandbox today, regardless of any other work. Second: the v1.0.9
desktop work (visualizer/spectrum overhaul, "Change Run Folder & Resume", image B2
archival, all the v1.0.5–v1.0.9 stability fixes) had been built on `fix/startup-freeze-hardening`,
a branch based on the old `v1.0.4` tag that had drifted from the current
`fix/album2-progress-filters` tip — missing later work like a "freeze completed Progress
when run folders are moved" feature and an untracked `platform_api/data/` module a live
migration depends on.

Initially it looked like reconciling these would require a full git branch merge (pulling
in unrelated history from both long-diverged lines) or shipping two branches in parallel
(backend-only + old-base desktop). Both were empirically tested and turned out to be
unnecessary: porting the **actual file diffs** (not the git history) from
`fix/startup-freeze-hardening` onto a fresh branch cut from the current tip applied
cleanly for the overwhelming majority of files — including the entire ~10,000-line
visualizer/spectrum rendering overhaul — with only 3 real text conflicts (all in files both
lines had independently touched for different, overlapping features) plus 2 binary test
fixtures that needed a plain file copy instead of a patch.

## Product impact

- Desktop v1.0.9 ships as one coherent build with **both** lines of recent work: the
  visualizer/spectrum rendering overhaul, "Change Run Folder & Resume" recovery flow, all
  the startup-freeze/network-timeout/disk-space hardening from v1.0.5–v1.0.8, **and** the
  "freeze completed Progress when run folders are moved" fix and Progress page filter/limit
  improvements that had landed separately on the current tip. Previously, building from the
  old branch alone would have shipped v1.0.9 *without* that last feature.
- Backend gets the matching support: batch MP3 re-download plan (Suno-first, Backblaze
  fallback), auto-pull scoping via `pipeline_complete`, and background/thumbnail image B2
  archival — needed for "Change Run Folder & Resume" to work end-to-end once deployed.
- No behavior change from the merge migration itself (schema no-op).

## Technical impact

- New migration `078_merge_pipeline_complete_and_distrokid`: pure Alembic bookkeeping
  merge (`down_revision = ("077_batch_auto_distrokid", "075_batch_channel_pipeline_complete")`,
  empty `upgrade()`/`downgrade()`). Does **not** wire up DistroKid's router/services — those
  remain unregistered in `main.py` by design; DistroKid ships nothing new here.
- `079_image_job_storage_key` (renamed from a prior local `076_image_job_storage_key`
  once `078` existed) now chains after the merge revision.
- Branch `release/desktop-1.0.9` (renamed from an interim `chore/v1.0.9-backend-support`
  once desktop was folded in), cut from `fix/album2-progress-filters` tip (`7eec7d0`),
  carrying:
  - Backend: `batch_repo.py` (`list_suno_audio_for_batch`, `list_pending_suno_downloads`
    `pipeline_complete` scoping, `update_image_job_storage_key`), `batch_service.py`
    (`build_batch_redownload_plan`, `_resolve_redownload_storage_keys`),
    `routers/music_downloads.py` (`POST /music/downloads/batch-redownload-plan`),
    `streaming_repo.py` (`get_track_storage_keys_for_suno_tasks`), `storage_service.py`
    (`download_bytes`), `image_job_service.py` (B2 archive-on-success + B2 fallback on
    read), `models/domain.py` (`ImageJob.storage_key`).
  - Desktop: the full `camxora_python` diff from `fix/startup-freeze-hardening`
    (~104 files, ~10,400 insertions) applied via `git apply --3way`, with 3 real conflicts
    resolved by hand (see below) and 2 new binary test fixtures copied directly (git can't
    3-way-patch binaries without a full index line).
- **3 real conflicts, all resolved in favor of whichever side's logic was more complete:**
  - `shared/lib/image_workspace.py`: current tip already had a more complete Secondary-album
    fallback (`"{Primary} II"` synthesis) than the incoming branch's simpler "leave empty"
    approach — kept the current tip's version, discarded the incoming hunk.
  - `features/progress/widgets/operational_rows_card.py` /
    `features/progress/views/progress_view.py`: both branches had independently added
    "freeze Update timestamp on terminal stage" logic that was 99% identical, differing only
    by whether `"completed"` was included alongside `"done"`/`"error"`; kept the
    superset (`{"done", "completed", "error"}`). The "Change Run Folder & Resume" signal,
    context-menu action, and full worker-wiring in `progress_view.py` merged in cleanly
    around this once the conflicting hunk was resolved.
- **Deliberately excluded** from this port: an unrelated "export doesn't need to wait for
  thumbnail" change (`routers/progress.py`, `services/channel_asset_service.py`) that was
  also committed on `fix/startup-freeze-hardening`'s history but is out of scope here and
  may already differ on the current tip.
- `feature/pipeline-stuck-alerts` (admin stuck-batch detection/alerting) remains fully
  independent and deferred — no migrations, no dependency on v1.0.9.
- **Pitfall hit and fixed along the way:** the first `git apply --3way` attempt reported
  "Applied patch to X cleanly" for ~110 files but silently wrote **none** of them to disk —
  two unrelated binary fixture files (`tests/fixtures/golden_frames/minimal/{bg.png,test_tone.wav}`)
  caused `git apply` to abort the entire patch without a clear top-level error. Excluding
  those two paths from the patch (and copying them directly instead) let the real apply go
  through for everything else.
- **Second pitfall:** a handful of new/untracked files in the source worktree
  (`shared/lib/disk_space.py`, several new test files) aren't part of `git diff` output at
  all (untracked, not just uncommitted) — these had to be identified separately via
  `git status --porcelain` and copied by hand.

## Files touched

See `platform_api/CHANGELOG.md` (unchanged from the prior backend-only pass) for the
backend list. Desktop: effectively the full `camxora_python/` diff between the shared
ancestor (`32c552b`) and `fix/startup-freeze-hardening`'s working tree — too large to
enumerate here; see `git diff` on `release/desktop-1.0.9` vs `fix/album2-progress-filters`.

## Migration / deploy

Completed for both environments:

1. **Sandbox** — synced `platform_api` (`sync_platform_api_sandbox.py`), ran
   `alembic upgrade head` (`run_alembic_upgrade_sandbox.py`). Sandbox was already on
   `075_batch_channel_pipeline_complete`; upgrade path was `075 + 077 -> 078 (merge) -> 079`.
   `alembic_version` confirmed at `079_image_job_storage_key` (single head), `/health` → 200.
2. **Production** — synced `platform_api` (`sync_platform_api_production.py`), ran
   `alembic upgrade head` via new `run_alembic_upgrade_production.py` (mirrors the sandbox
   script; added to this branch). Production was still on `074_suno_audio_ids` (had never
   picked up the pipeline-complete *or* DistroKid migrations), so the upgrade path ran the
   full chain: `074 -> 075_distrokid_addon -> 076_distrokid_wav -> 077_batch_auto_distrokid
   -> 078 (merge) -> 079`. This adds DistroKid's dormant schema (add-on entitlement columns,
   WAV job tables) to production — additive only, no behavior change, since DistroKid's
   router/services stay unregistered in `main.py`. `alembic_version` confirmed at
   `079_image_job_storage_key`, `/health` → 200, journalctl showed a clean migration run
   with no errors.
3. Desktop installers built from `release/desktop-1.0.9` for both environments:
   - Sandbox: `CamxoraSetup-1.0.9-sandbox.exe` (`api.sandbox.camxora.com`)
   - Production: `CamxoraSetup-1.0.9-production.exe` (`api.camxora.com`)
   - Both under `camxora_python/dist/installer/`, renamed on disk immediately after each
     build since Inno Setup's `OutputBaseFilename` is version-only and would otherwise let
     the production build silently overwrite the sandbox one (known pre-existing gap; not
     fixed here — see Follow-ups).
4. Branch pushed to origin as `release/desktop-1.0.9`; tagged `v1.0.9` (no prior collision —
   existing tags stopped at `v1.0.4`).
5. **Separate, pre-existing hygiene gap (not blocking):** `platform_api/data/music_genre_catalog.py`
   (used by migration `063`) exists on disk on sandbox/production and in the local root
   workspace, but is **not committed to git on any branch**. Fine for now (tarball-based
   deploys carry it along from local disk), but should be committed on `main` separately.

## Tests

- `alembic heads`: single head, `079_image_job_storage_key`.
- `platform_api/tests/test_batch_service.py` + `test_image_job_service.py` (the two files
  with new/changed logic): 38 passed, 1 failed
  (`test_execute_batch_submits_suno_for_successful_drafts_when_enabled`) — confirmed failing
  identically on the unpatched base branch via `git stash`. New tests for
  `build_batch_redownload_plan` (Suno-first/Backblaze-fallback) and image B2 archival/fallback
  all pass.
- **Known pre-existing blocker, not caused by this change:** a large share of
  `platform_api/tests` (all router-level test files, since they import the full FastAPI app)
  fail to even *collect* — `AssertionError: Status code 204 must not have a response body` —
  because a `DELETE` route with `status_code=204` declares a response body, which the
  installed FastAPI version now rejects at import time. This blocks router tests app-wide;
  it needs its own dedicated fix (find and correct the offending `204` route) before the
  router test suite can run again at all.
- `camxora_python/tests` (full suite, 838 collected after fixing the untracked-file
  collection gap): 831 passed, 1 skipped, 6 failed — all 6 confirmed failing identically on
  the unpatched base branch via `git stash`. Zero new regressions.

## Follow-ups

- Commit `platform_api/data/` to git (currently untracked, only surviving via tarball
  syncs).
- Fix the pre-existing `blog_posts.py` `DELETE .../{post_id}` `status_code=204` FastAPI
  assertion so router-level tests can run at all.
- The 6 pre-existing desktop test failures and other pre-existing backend test failures
  (confirmed via `git stash` to predate this branch) are unrelated to this work but still
  open; worth a dedicated cleanup pass.
- `feature/pipeline-stuck-alerts` still parked, independent, portable the same way whenever
  prioritized.
- Installer filename collision between environments (`CamxoraSetup-{version}.exe` for both
  sandbox and production) is a standing gap in `installer/Camxora.iss` — worth adding
  `-sandbox`/`-production` to `OutputBaseFilename` directly so a rebuild can't silently clobber
  the other environment's installer on disk.
- Production DB now carries DistroKid's dormant schema (columns/tables from `075`/`076`/`077`)
  even though the feature is unreleased — intentional per the merge-migration design, but
  worth a reminder when DistroKid actually ships that its own migration lineage is already
  applied everywhere.
