# Technical Design: AI Model Routing (Key Pool Only + Desktop Integration)

## Goals

- Remove all `.env`/local API key dependencies from runtime generation paths.
- Ensure provider/model selection is always resolved at request time via `AIRoutingService.resolve(operation)`.
- Ensure all providers used by the platform are backed by active keys in the Key Pool.
- Remove desktop-side UI and code paths that allow local AI provider selection or storing API keys.
- Preserve switchability: admin changes take effect on the next request without restarting the desktop app.

## Non-Goals

- Rebuilding the admin portal routing UI (already implemented).
- Changing DB schema for routing assignments or key pool.

## Current Architecture (Verified)

- Admin Portal persists routing assignments in `system_settings` under key `ai_routing_assignments`.
- Platform API resolves routing via `platform_api/services/ai_routing_service.py`:
  - Validates provider capability (service type)
  - Rejects providers without active keys (`NoAvailableKeysError` → HTTP 503)
- Desktop app calls Platform API endpoints (e.g. `/api/v1/generation/draft`) via `python_app/services/generation_proxy.py`.

## Required Code Changes

### 1) Backend: remove env-key fallbacks

**Problem**

Some endpoints still attempt to read provider keys from `Settings` or fall back to `.env` behavior. This violates “Key Pool only” and also breaks at runtime now that key fields were removed from `platform_api/config.py`.

**Fix**

- Ensure all provider API key access happens via Key Pool wrappers or `KeyPoolService.get_key(provider)` with no fallback.
- Ensure missing keys results in `NoAvailableKeysError` (HTTP 503) consistently.

**Files**

- `platform_api/routers/channel_setup.py`
  - Remove the DeepSeek `_call_llm()` helper that reads `settings.deepseek_api_key`.
  - Remove any OpenAI image generation that reads `settings.openai_api_key`.
  - Prefer calling `GenerationService.submit_image(...)` for all image providers (fal/slai/openai/cala) using routing’s provider/sub_model.

- `platform_api/routers/channel_prompts.py`
  - Remove the “Key Pool first then fallback to settings.deepseek_api_key” behavior.
  - Use Key Pool only. If no active key exists, raise `NoAvailableKeysError("deepseek", ...)`.

- `platform_api/services/generation_service.py`
  - Remove OpenAI and CALA image generation fallbacks that pass `api_key=None` or read env settings.
  - Require `KeyPoolServicePort` and use it to obtain a key for the provider.

- `platform_api/routers/health.py`
  - Replace health checks that reference removed settings keys (`suno_api_key`, `fal_api_key`, `slai_api_key`) with Key Pool based health reporting:
    - show active key counts per provider
    - optionally perform lightweight upstream ping only when an active key is present

### 2) Backend: add a text endpoint for lyrics polish (desktop feature)

**Problem**

Desktop lyrics polishing currently uses a locally stored OpenAI key (`openaiApiKey`) and calls OpenAI directly. This must be removed.

**Fix**

- Add `POST /api/v1/generation/polish-lyrics`
- Resolve routing via `AIRoutingService.resolve("lyric")` (Text Generation service type)
- Deduct credits using `UsageEnforcementService.check_and_deduct(... operation_type="lyric", ai_service=routing.provider)`
- Call a new `GenerationService.generate_text(...)` helper that:
  - routes by `provider` (openai/deepseek/slai)
  - uses Key Pool wrappers for keys
  - returns plain text output (no JSON structure required)

### 3) Desktop: remove local AI settings and direct provider calls

**Problem**

Desktop music workflows expose:
- an “OpenAI API Key” input
- a “AI Providers” tab to select DeepSeek/SLAI/Suno
and the coordinator still contains direct calls to provider endpoints.

**Fix**

- Remove all desktop UI + persistence keys that store provider selection and API keys.
- Ensure music draft generation and lyrics polish call Platform API only.
- After this change, “switching AI model” is done exclusively in Admin Portal → Settings → AI Routing.

**Files**

- `python_app/views/music_view.py`
  - Remove the “OpenAI API key” input row.
  - Remove the “AI Providers” tab and its comboboxes.

- `python_app/app/music_ui_handlers.py`
  - Stop saving `openaiApiKey`, `songDraftProvider`, `titleAlbumProvider`, `lyricsProvider`.
  - Keep non-AI settings (paths, performance, YouTube OAuth, etc.) unchanged.

- `python_app/features/music/coordinator.py`
  - Update song generation to use `generate_song_draft(... generation_proxy=...)` for draft/title/album/lyrics.
  - Update polish handler to call a new `GenerationProxy.polish_lyrics(...)` method hitting the Platform API endpoint.

## Validation Plan

- Backend:
  - Run `pytest` under `platform_api/tests`.
  - Confirm that when a provider has zero active keys, the API returns HTTP 503 with a clear error message (no `.env` fallback paths).

- Desktop:
  - Confirm Settings has no AI keys/provider selection UI.
  - Change routing in Admin Portal (e.g., `lyric: deepseek -> openai`) and validate:
    - Song draft generation continues to work.
    - Lyrics polishing uses the new provider on the next click.
