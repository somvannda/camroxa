# Music plan preflight now prices video export + merge

**Date:** 2026-09-24
**Branch:** `fix/preflight-video-merge-credits`
**Surfaces:** platform_api, camxora_python (desktop), camxora (legacy Electron)
**Status:** implemented; sandbox deploy

## Summary

The music-plan preflight only estimated **draft + Suno + images**. Video export and
merge are charged later, per stage, at export time. A plan could therefore pass
preflight, run music + images to completion (e.g. 15/15 backgrounds/thumbnails),
then stall at the export stage with `Auto-video blocked (billing)` because the
wallet ran dry. The desktop Automation card also hard-coded Video/Merge credits
as `Later`.

## Change

- `platform_api/services/batch_service.py` — `preflight_music_plan` accepts
  `auto_video_after_suno` / `auto_merge_after_video` / `auto_reel_after_video`,
  prices `local/video` + `local/video_merge`, and adds them to
  `total_wallet_cost`. Counting: `video_ops = total_songs x 2` (one track per
  channel), `merge_ops = batch_count x 2` (one merge per album/channel), each
  doubled with Auto-Reel. Account-wide **daily** video/merge caps are enforced
  upfront with a reason naming the limit. Shortfall reasons name the video/merge
  portion.
- `platform_api/services/billing_mode_service.py` — `subscription_covers_batch`
  also checks the plan's monthly `video` (incl. `video_manual`) and `merge`
  meters.
- `platform_api/routers/credits.py` — `/credits/operation-costs` returns
  `video` + `video_merge` unit prices.
- `platform_api/services/usage_enforcement_service.py` + `create_batch` —
  single batch create (`POST /batches`) prices per-batch video/merge and enforces
  daily video/merge caps via `preflight_batch_cost`.
- `camxora_python/shared/lib/music_costs.py` + Music view / Automation card —
  video/merge included in the estimate; card shows `N export · M merge` and real
  credits instead of `Later`; preflight request sends the automation flags.
- `camxora_python/features/create` — Create Auto Video/Merge now has an upfront
  gate (quota first, then wallet) and charges `consume_video_operation` per
  Version folder (video) / per Version (merge), refunding on failure.
- `camxora/src/renderer/src/features/music/MusicWorkspacePage.tsx` — legacy
  Electron cost estimate includes video/merge (parity). That app already has
  pre-existing type/test failures on `main`; no new errors are introduced.

## Not included (follow-up)

- Conservative partial-subscription behavior: when any meter is exhausted the
  whole plan is blocked unless the wallet covers the full total (consistent with
  the existing song/image preflight).
- Production deploy (sandbox only here).

## Tests

- `platform_api/tests/test_batch_service.py` — preflight counts/costs, wallet
  shortfall, daily video cap, batch-create preflight.
- `platform_api/tests/test_billing_mode_service.py` — video/merge meters;
  manual exports share the meter.
- `camxora_python/tests/test_music_costs.py`, `test_automation_card.py` —
  video/merge estimate and card display.
- `camxora_python/tests/test_create_generate.py` — op estimate + Create gate.
- Local run: platform 108 passed; desktop 37 passed.
