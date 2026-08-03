# DistroKid automation phases 1–5 (library + orchestration + WAV API)

**Date:** 2026-07-27  
**Status:** implemented (sandbox API deployed; production not touched)

## Summary

Ported AutoDistroKid Playwright upload automation into CAMXORA (no Mixea / no local MP3→WAV). Wired a soft DistroKid stage after long video merge when the Music DistroKid checkbox is on. Platform API now converts/polls Suno WAV, meters 600/mo, and stores fingerprinted upload history. Short/Reel outputs never auto-merge.

## Product impact

- Before: DistroKid was entitlement + checkbox only.
- After:
  - DistroKid page: Connect (Google Sign-In browser), form defaults, local/cloud history, WAV usage.
  - With DistroKid add-on + Music checkbox: after long merge (or long export if merge off), desktop downloads Suno WAVs and uploads WAV + thumbnail via Playwright.
  - DistroKid failures are soft (video/merge success is kept).
  - Short/Reel files stay individual — never auto-merged.

## Technical impact

### Desktop (`camxora_python`)
- Ported automation: browser, element_resolver, form_automator, track_uploader (WAV-only), distrokid session/submit, report
- Orchestrator + upload worker + pipeline coordinator
- Workflow soft DistroKid node
- Reel auto-merge disabled in `is_auto_merge_enabled_for_branch`
- Progress DistroKid soft column/detail overlay from `DistroKidJobStore`

### Platform API
- Migration `076_distrokid_wav` (jobs, usage, history)
- `/distrokid/wav/convert|jobs|usage|sources` + `/distrokid/history*`
- Suno client WAV submit/poll + callback route

## Files touched

- `camxora_python/features/distrokid/**`
- `camxora_python/shared/services/distrokid_pipeline_coordinator.py`
- `camxora_python/shared/services/platform_api.py`
- `camxora_python/features/video/lib/pipeline_merge.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/features/workflow/lib/workflow_steps.py`
- `camxora_python/app/application.py`, `app/router.py`
- `platform_api/clients/suno_client.py`
- `platform_api/services/distrokid_service.py`
- `platform_api/routers/distrokid.py`, `callbacks.py`
- `platform_api/migrations/versions/076_distrokid_wav.py`
- `platform_api/tests/test_distrokid_wav.py`
- `CHANGELOG.md`, `platform_api/CHANGELOG.md`

## Migration / deploy

```bash
# sandbox only (076 + 077 applied)
python scripts/deploy/sync_platform_api_sandbox.py
python scripts/deploy/run_alembic_upgrade_sandbox.py
```

Do **not** deploy production unless explicitly requested.

Desktop: local rebuild / run with Playwright + system Chrome/Edge.

## Tests

- `pytest camxora_python/features/distrokid/tests` — includes batch snapshot, gaps, Progress summary role isolation
- `pytest camxora_python/tests/test_progress_presentation.py` — DistroKid compact/detail helpers
- Platform API DistroKid pytest collection currently blocked by unrelated FastAPI 204 assertion on blog-posts delete when importing `create_app`

## Follow-up: batch snapshot + channel artist (same day)

- `batches.auto_distrokid` + `batches.auto_reel_after_video` snapshotted at Music batch create (`077_batch_auto_distrokid`) — sandbox migrated.
- DistroKid coordinator prefers batch snapshot over live Music toggles (`GET /distrokid/batch-context/{batch_id}`).
- Artist for DistroKid credits defaults to **channel profile name** for Primary/Secondary; DistroKid page artist field is fallback only.
- Legacy batches (pre-077 / missing context) still fall back to live `autoDistroKid` / `autoReelAfterVideo`.

Hardened DistroKid against cross-feature gaps:

1. **Queue + both roles** — DistroKid jobs persist locally and drain sequentially (primary then secondary); no silent skip.
2. **Short gate** — when Music Short is on, DistroKid stays `awaiting_short` until individual reel MP4s exist; Short export completion kicks the queue.
3. **History only after real submit** — manual-review (`auto_submit=false`) does not write success fingerprints; status `awaiting_manual_submit`.
4. **Workflow truth** — DistroKid node reads local job store (not YouTube heuristic).
5. **WAV pairing** — prefer matching existing MP3 stem for `.wav` target; role-scoped sources (no fallback-to-all-roles).
6. **Connect on worker thread** — Google Sign-In no longer blocks the Qt UI thread.
7. **Portal copy** — DistroKid panel no longer says “upload coming next”.
8. **Billing tooltip** — Music DistroKid checkbox mentions wallet `suno/wav` + 600/mo meter.

### Remaining follow-ups

- Force-upload confirm for duplicates (optional; hard-block is fine for now)
- Frozen installer Playwright/browser provisioning
- Admin DistroKid usage view
- Dedicated profile `genre` field (optional; DistroKid genre stays in DistroKid settings)

## Follow-up: DistroKid artist matching (same day)

- DistroKid settings: **Per channel** (default), **One artist**, or **Two artists** (Primary/Secondary role shortcuts).
- **Per channel:** each channel profile has its own DistroKid artist field; reuse the same name across channels (e.g. 2 channels → Artist A, 2 → Artist B).
- Custom artist names; blank fields fall back to batch channel profile names.
- Jobs store `profile_id`; batch-context returns `ok_profile_id` / `alt_profile_id` for resolution.
- Coordinator resolves artist at queue + upload time from saved settings.

## Follow-up: Progress DistroKid soft stage (same day)

- Progress table adds a **DistroKid** column (before YouTube) overlayed from local `DistroKidJobStore` — never drives API/`row.stage` Error.
- Detail panel shows DistroKid status + soft-fail copy.
- Stage filter includes DistroKid (matches rows with an active DistroKid job summary).
- Job statuses refined: `wav_downloading` / `uploading` (+ role-aware Progress/Workflow lookup).
- Workflow DistroKid empty hint + icon/stage badge polish; duplicate skip shown as partial/warning, not hard pipeline fail.
