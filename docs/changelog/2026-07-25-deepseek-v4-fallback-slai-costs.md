# DeepSeek V4 migration + text fallback + SLAI cost tiers

**Date:** 2026-07-25  
**Status:** implemented (sandbox deployed)

## Summary

DeepSeek retired `deepseek-chat` / `deepseek-reasoner` on 2026-07-24, which caused all first-try lyric drafts to fail. Text fallback to SLAI/OpenAI did not run because permanent HTTP 400s stopped the chain. This change registers DeepSeek V4 models, expands sibling models within a provider before cross-provider fallback, advances text fallback on any provider error (matching image behavior), and refreshes SLAI text/image seed cost tiers from observed provider pricing.

Also fixed admin Credits **Edit Pricing** for `local` rows: COGS `0` was rejected with HTTP 422 because cost validation required ≥0.0001 credits.

## Product impact

**Before**
- Draft generation failed immediately on retired `deepseek-chat`.
- SLAI/OpenAI fallback never ran for invalid-model 400s.
- Admin cost_tier strings for SLAI text models were stale; SLAI image was ~$0.01/img.
- Editing local Manual/Studio/Merge pricing with Cost Credits `0` failed with 422.

**After**
- Default DeepSeek model is `deepseek-v4-flash` (legacy aliases kept).
- Sibling models within a provider are tried before the next provider; 400s still advance.
- SLAI text USD/1K and image (~$0.0067/img = 150 images / $1) seed tiers updated.
- Local pricing accepts Cost Credits `0` (true $0 COGS).

## Technical impact

- DeepSeek V4 registry + text fallback expansion + advance-on-any-error gateway.
- `_pricing_units_from_request` allows `external_cost_cents == 0`.

## Files touched

- `platform_api/ai/registry.py`, `types.py`, text gateway, response parser
- `platform_api/services/ai_routing_service.py`, `generation_service.py`
- `platform_api/routers/channel_prompts.py`, `credits.py`
- `admin_portal/src/pages/credits/index.tsx`
- related tests + changelogs

## Migration / deploy

1. Deploy/restart `camxora-api` (sandbox done for credits.py + prior DeepSeek files).
2. Retry Credits → Edit Pricing for `local` / Manual export with Cost Credits `0`.
3. Optional: rebuild admin portal for clearer 422 toasts.

## Tests

- Routing/fallback/cost estimate suite: 32 passed
- `test_pricing_zero_cost.py` + `test_local_platform_operations.py`: 5 passed

## Follow-ups

- Confirm admin UI DeepSeek model labels; watch draft batches after V4 cutover.
