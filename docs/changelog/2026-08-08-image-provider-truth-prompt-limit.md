# Image provider truth + hard prompt allowance

## Summary

Hardens image generation so over-long prompts are rejected with the exact API error (no truncation, no fail-absorb burn), and admin/ledger provider fields stop lying when jobs fail or fall back. Image prompt hard gate is **5000** characters (aligned with SLAI sandbox probe accept edge; Fal/OpenAI allow more). Text/LLM limits are unchanged.

## Product impact

- Current desktop users still see: `Image prompt exceeds maximum length of 5000 characters.` when generating (image-only gate; text/LLM limits unchanged).
- Over-long prompts no longer auto-retry or burn the daily fail/absorb budget.
- Usages / User Spent / Finance show **Provider** and **Model** separately (SLAI vs GPT-named models).
- Pipeline image jobs show provider, prompt length, and error for faster failure diagnosis.
- Image jobs and ledger record routed vs executed provider truth; profile `image_config.provider` is ignored for execution.
- Default image fallback chain is `slai → fal` (unused OpenAI image hop removed from defaults + stored settings).

## Technical impact

- Validate prompt length before wallet hold / `provider_invoked`.
- Persist job `provider` on failure (not only success).
- Ledger metadata adds `routed_provider` / `executed_provider` (keeps `provider` for backward compatibility).
- Migration `083_image_fallback_drop_openai` strips OpenAI from stored image fallback chain.

## Files touched

- `platform_api/services/image_job_service.py`
- `platform_api/services/usage_enforcement_service.py`
- `platform_api/services/batch_service.py`
- `platform_api/services/ai_routing_service.py`
- `platform_api/services/admin_pipeline_service.py`
- `platform_api/routers/admin_pipeline.py`
- `platform_api/migrations/versions/083_image_fallback_drop_openai.py`
- `platform_api/tests/test_image_job_auto_retry.py`
- `platform_api/tests/test_batch_service.py`
- `admin_portal/src/lib/usage-labels.ts`
- `admin_portal/src/pages/usage/index.tsx`
- `admin_portal/src/pages/user-spent/index.tsx`
- `admin_portal/src/pages/finance/index.tsx`
- `admin_portal/src/pages/pipeline/index.tsx`
- `admin_portal/src/types/pipeline.ts`

## Migration / deploy

- Deploy **platform_api** + run Alembic upgrade on sandbox.
- Deploy **admin_portal** rebuild on sandbox.
- No desktop release required for the generate-time alert.

## Tests

- `test_non_retryable_detects_fail_budget` covers prompt-length marker.
- Batch routing fixture exposes `resolve_image_chain`.
- Manual: enqueue image with prompt >5000 → exact error, attempt_count stays 1, no absorb spike; admin Usages shows Provider/Model split.
