# SLAI image model `cx/gpt-6-sol-image`

**Date:** 2026-11-06
**Surface:** `platform_api`, `admin_portal`
**Migration:** `184_slai_gpt_6_sol_image`

## What

SLAI's `cx/gpt-6-sol-image` is now a first-class SLAI image model:

| Place | Change |
|---|---|
| `platform_api/ai/registry.py` | Added to `SLAI_IMAGE_MODELS`, so `PROVIDER_SUB_MODELS["slai"]` exposes it as an image choice |
| `admin_portal/src/pages/credits/index.tsx` | Added to the SLAI sub-model list (Credit Pricing + AI Model Costs forms) |
| `platform_api/services/ai_routing_service.py` | Added to `DEFAULT_IMAGE_FALLBACK_CHAIN` after `cx/gpt-image-2.5` |
| `admin_portal/src/pages/settings/ai-routing-section.tsx` | Same default image fallback chain in the UI |
| `platform_api/migrations/versions/184_slai_gpt_6_sol_image.py` | Clones the `cx/gpt-image-2.5` `credit_pricing` / `ai_model_costs` rows and inserts the model into the stored image fallback chain |

## Price

The credit price and provider cost are **cloned from `cx/gpt-image-2.5`**
(production list price: 6 credits for background images, 8 for thumbnails;
provider cost ~$0.0067/img). That keeps the new model billable immediately on
each install's configured Global Credit Value.

SLAI has not published a separate rate for this model yet. When it does, edit
the `cx/gpt-6-sol-image` rows on Admin → Credits (Credit Pricing and AI Model
Costs) and consider updating the registry `cost_tier`.

## Routing

The model is selectable in AI Routing on every image operation. The primary
assignment is **not** changed; the new model is added as an SLAI fallback after
`cx/gpt-image-2.5`, before `fal`.

## Verification

```bash
python -m pytest tests/test_ai_routing_registry.py tests/test_model_cost_estimates.py -q
```
