# Image Preferences UX lock + force regenerate

**Date:** 2026-08-05  
**Branch:** `feature/image-prompt-categories-and-replace`  
**Surfaces:** `platform_api`, `camxora_python`  
**Spec:** [`docs/IMAGE_PROMPT_CATEGORIES_AND_REPLACE_REQUIREMENTS.md`](../IMAGE_PROMPT_CATEGORIES_AND_REPLACE_REQUIREMENTS.md)

## Summary

Preferences keep **Image source mode** (AI Generated / User Provided). Under AI Generated, **Background source** and **Thumbnail source** are independently **Category**, **User reference**, or **Prompt only**. Thumbnail overlay UI is hidden (always AI/composite). User reference returns a clear “not available yet” error until P2. Image queue gains **Regenerate Background + Thumbnail**, which force-resets successful jobs.

## Changes

### Preferences (`camxora_python`)

- Combos: Category | User reference | Prompt only for BG and TH.
- Hide Thumbnail overlay control; always persist `thumbnail_overlay_mode=ai`.
- Hide/disable BG/TH source rows when Image source is User Provided.

### API

- `personal_reference` mode + clear not-ready ValidationError until portal library ships.
- `POST /image-jobs/retry` accepts `force=true` → `reset_image_jobs(include_success=True)`.

### Image queue

- Context menu: **Regenerate Background + Thumbnail** (force retry both jobs).
