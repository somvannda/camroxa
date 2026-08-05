# Image prompt-only modes (P0)

**Date:** 2026-08-05  
**Branch:** `feature/image-prompt-categories-and-replace`  
**Surfaces:** `platform_api`, `camxora_python`  
**Spec:** [`docs/IMAGE_PROMPT_CATEGORIES_AND_REPLACE_REQUIREMENTS.md`](../IMAGE_PROMPT_CATEGORIES_AND_REPLACE_REQUIREMENTS.md) §11 P0

## Summary

Operators can set **Background source** and **Thumbnail source** independently to **Prompt only** or **Category**. Prompt-only generation sends no sample/style reference; thumbnails composite typography onto the generated background without a style-sample corner box and no longer hard-fail with “Thumbnail style sample is missing.”

## Changes

### platform_api

- `image_source_mode.py` — normalize `imageBackgroundSourceMode` / `imageThumbnailSourceMode` (`prompt_only` | `category`); migrate legacy `backgroundSourceMode=prompt` for background only; kind-specific empty-prompt messages.
- `image_job_service` — skip base/style samples when prompt-only; thumbnail prompt-only uses black overlay input + prompt-only typography instruction.
- `batch_service` — do not attach sample paths when enqueueing prompt-only jobs.
- `thumbnail_composite` — `THUMBNAIL_PROMPT_ONLY_INSTRUCTION` + `enrich_thumbnail_prompt(..., prompt_only=)`.

### camxora_python

- Settings draft/patch dual keys; stop writing legacy `backgroundSourceMode`.
- Preferences: Background source + Thumbnail source combos (Prompt only / Category).

## Out of this slice

Theme categories (P1), personal references (P2), Progress replace/export (P3).
