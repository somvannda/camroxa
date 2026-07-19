# AI routing real costs + Suno lyrics sanitization UX

**Date:** 2026-07-18  
**Status:** implemented

## Summary

AI Routing in the admin portal now shows stored USD costs from `ai_model_costs` (e.g. `$0.004` for Suno lyrics) instead of registry estimate strings. Sub-model dropdowns are filtered per operation so Suno `lyrics` only appears on the Lyric row, and provider changes reset to the first valid model for that operation.

Desktop and API share Suno lyrics risk scanning: hard-block terms (red), risky patterns (yellow), debounced highlights in the song editor, plus `POST /generation/lyrics-suno-check`.

## Product impact

- **Before:** Admin AI Routing showed registry strings like `~2 Suno credits (~$0.01)`; Title row could show stale Suno lyric model after switching provider.
- **After:** Operation rows show real DB costs when configured; Suno lyrics model is lyric-only; desktop lyrics editor highlights Suno block/warn terms with a summary banner.

## Technical impact

- **API:** `AIRoutingService.get_available_providers()` loads `ai_model_costs` and returns `cost_usd`, `cost_usd_by_operation`, and `operations` per sub-model. New `POST /generation/lyrics-suno-check`.
- **Admin:** Types and `ai-routing-section.tsx` format USD costs per operation; normalize invalid sub-models on load.
- **Desktop:** Local mirror of sanitize/risk scan; `lyrics_suno_highlighter.py` + debounced scan in `song_editor_card.py`; learned terms from Suno errors when loading history.

## Files touched

- `platform_api/services/ai_routing_service.py`
- `platform_api/dependencies.py`
- `platform_api/ai/registry.py`
- `platform_api/services/suno_lyrics_sanitize.py`
- `platform_api/routers/generation.py`
- `platform_api/tests/test_ai_routing_providers.py`
- `platform_api/tests/test_ai_routing_registry.py`
- `platform_api/tests/test_model_cost_estimates.py`
- `platform_api/tests/test_suno_lyrics_sanitize.py`
- `admin_portal/src/types/ai-routing.ts`
- `admin_portal/src/pages/settings/ai-routing-section.tsx`
- `camxora_python/shared/lib/suno_lyrics_sanitize.py`
- `camxora_python/features/music/widgets/lyrics_suno_highlighter.py`
- `camxora_python/features/music/widgets/song_editor_card.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/tests/test_suno_lyrics_sanitize.py`

## Migration / deploy

- No DB migration. Ensure `ai_model_costs` rows exist for routed models (Suno lyrics lyric op at `$0.004` expected).
- Deploy platform API + admin portal + desktop app together for consistent cost display and lyrics scan.

## Tests

- `pytest platform_api/tests/test_suno_lyrics_sanitize.py platform_api/tests/test_ai_routing*.py -q`
- `pytest camxora_python/tests/test_suno_lyrics_sanitize.py -q`

## Follow-ups

- Optional: call `/generation/lyrics-suno-check` from desktop for server-side preview parity when offline scan is insufficient.
- Consider syncing learned terms to a user/workspace cache across sessions.
