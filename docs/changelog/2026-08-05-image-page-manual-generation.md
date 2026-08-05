# Image page source controls + Manual Generation

**Date:** 2026-08-05  
**Branch:** `feature/image-prompt-categories-and-replace`  
**Surfaces:** `camxora_python`  
**Spec:** [`docs/IMAGE_PROMPT_CATEGORIES_AND_REPLACE_REQUIREMENTS.md`](../IMAGE_PROMPT_CATEGORIES_AND_REPLACE_REQUIREMENTS.md) §6.1

## Summary

Image workspace surfaces the same Background/Thumbnail source prefs above each preview (synced to Preferences). **Manual Generation** under each prompt and right-click **Regenerate** actions force-reset queue jobs after saving prompts + source modes, using the normal image-job credit/quota path. Clear preflight errors for empty prompt-only and User reference; credit/quota failures surface in the page banner.

## Changes

- Preview cards: Category | User reference | Prompt only combos
- Manual Generation buttons under BG/TH prompts (selected row required)
- Context menu: Retry (failed) vs Regenerate (force, per kind + both)
- `ImageRetryJobsWorker` patches settings before retry so prompt refresh sees latest values
- Client preflight + failed-job error surfacing after regenerate
- Background poll slowed to 12s and made quiet: does not reset source/prompt UI, does not flash “Refreshing…”, reloads previews only when selected job outputs change
- Force regenerate clears locked sample paths so Category mode picks a new reference (fixes “always the same image”)
- Image queue **Deselect**; Manual Generation with no row creates a **Not available** queue row for today (billed image-job path), not a standalone playground preview
