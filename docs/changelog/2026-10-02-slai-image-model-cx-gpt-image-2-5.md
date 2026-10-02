# SLAI image model → `cx/gpt-image-2.5` (replace `slai/gpt-image-2`)

## Summary

SLAI (`api.slai.shop`) retired the image model id **`slai/gpt-image-2`** in
favor of **`cx/gpt-image-2.5`**. The platform registry, SLAI client default,
routing/fallback defaults, admin dropdowns, and live database rows are moved to
the new id so image generation keeps working after the provider change.

The provider cost is unchanged (~150 images / $1 ⇒ ~$0.0067 per image), so the
credit price for SLAI image operations is preserved.

## Product impact

- Background/thumbnail image jobs continue generating through SLAI with the new
  provider model id.
- Admin **Settings → AI Routing** image fallback chain and **Credits** sub-model
  dropdown show `cx/gpt-image-2.5` (SLAI images).
- No change to credit pricing: existing `credit_pricing` / `ai_model_costs`
  rows are renamed, not repriced.

## Technical impact

- `platform_api/ai/registry.py`: `SLAI_IMAGE_MODELS` key/api_id become
  `cx/gpt-image-2.5` (cost tier unchanged).
- `platform_api/clients/slai_client.py`: default payload model is
  `cx/gpt-image-2.5`.
- `platform_api/services/ai_routing_service.py` and
  `admin_portal/src/pages/settings/ai-routing-section.tsx`:
  `DEFAULT_IMAGE_FALLBACK_CHAIN` now points at `cx/gpt-image-2.5`.
- `admin_portal/src/pages/credits/index.tsx`: SLAI sub-model option updated.
- Migration `125_slai_image_model_cx_gpt_image_2_5` rewrites existing
  `system_settings.ai_routing_assignments` / `ai_routing_image_fallback_chain`
  entries and renames `credit_pricing` / `ai_model_costs` rows from the old to
  the new model id (drops a stale old row if the new one already exists).
- Historical migration `083_image_fallback_drop_openai` is left untouched, as
  applied migrations are immutable.

## Files touched

- `platform_api/ai/registry.py`
- `platform_api/clients/slai_client.py`
- `platform_api/services/ai_routing_service.py`
- `platform_api/migrations/versions/125_slai_image_model_cx_gpt_image_2_5.py`
- `platform_api/tests/test_ai_routing_registry.py`
- `platform_api/tests/test_model_cost_estimates.py`
- `platform_api/tests/test_image_provider_fallback.py`
- `platform_api/tests/test_public_usage_rates_service.py`
- `admin_portal/src/pages/settings/ai-routing-section.tsx`
- `admin_portal/src/pages/credits/index.tsx`
- `admin_portal/src/lib/finance-estimates.test.ts`
- `scripts/deploy/fix_channel_image_routing_sandbox.py`
- `scripts/deploy/migrate_ai_routing_sandbox.py`
- `scripts/deploy/remote_apply_routing.py`

## Migration / deploy

1. Deploy `platform_api` and run `alembic upgrade head`
   (`125_slai_image_model_cx_gpt_image_2_5`) on sandbox, then production.
2. Rebuild `admin_portal` so the routing/credits dropdowns show the new id.
3. Restart `camxora-api` and image workers so the client default loads.
4. Verify: `SELECT sub_model FROM credit_pricing WHERE ai_service='slai';`
   returns `cx/gpt-image-2.5`, and generate one background/thumbnail image.

## Follow-ups

- Production's `ai_routing_image_fallback_chain` is three identical SLAI
  entries (pre-existing before this change), so a SLAI-wide outage has no
  FAL/OpenAI fallback. Left as-is here; consider setting it to
  `slai/cx/gpt-image-2.5 → fal/flux-pro` in Admin → AI Routing.

## Tests

- `python -m pytest platform_api/tests/test_ai_routing_registry.py \
  test_model_cost_estimates.py test_image_provider_fallback.py \
  test_public_usage_rates_service.py test_capability_catalog.py -q` → 27 passed.
- `python -m pytest` routing/pricing/image subset → 68 passed.
- `npx vitest --run src/lib/finance-estimates.test.ts` → 8 passed.
- `npx tsc --noEmit` (admin_portal) → clean.
- Sandbox: migrated, admin rebuilt, `/health` 200, admin 200; routing/pricing
  rows verified `cx/gpt-image-2.5`.
- Production: migrated (alembic `125_...`), admin rebuilt, `/health` 200, admin
  200; routing capability audit over production data → **ready, 0 errors,
  0 warnings**.
