# Music Web — Suno Advanced Options & Auto-Generate

**Date:** 2026-08-15  
**Surfaces:** `platform_api`, `music_web`  
**Branch:** `feature/music-web-suno-create-shell`

## Summary

Enhanced the music web Create page with advanced Suno API options, model version selection, and auto-generation of lyrics and titles using the draft API.

## Product impact

### Version Selection
- Users can now choose between Suno V5 and V5.5 models via a dropdown selector in the Create interface

### Auto-Generate Lyrics & Title
- New "Auto-generate lyrics & title" button in Advanced mode
- Uses Suno's lyrics generation API to create both lyrics and title from a style description
- Provides quick creative starting points for users

### Advanced Options Panel
- Collapsible "Advanced Options" section with fine-tuning controls:
  - **Negative Tags**: Specify unwanted musical elements (e.g., "choir, backing vocals, falsetto")
  - **Vocal Gender**: Bias toward male or female vocals (m/f or auto)
  - **Style Weight** (0-1): Control how strictly the model adheres to style prompt
  - **Weirdness/Creativity** (0-1): Adjust creative deviation and novelty
  - **Audio Weight** (0-1): Balance audio consistency with other controls

## Technical impact

### Backend Changes
- **`platform_api/clients/suno_client.py`**: Added parameters for `negative_tags`, `vocal_gender`, `style_weight`, `weirdness_constraint`, `audio_weight` to `submit_task()` method
- **`platform_api/ports/generation_port.py`**: Updated `SunoRequest` dataclass with new optional fields
- **`platform_api/services/generation_service.py`**: Updated `SunoClientProtocol` and `_call_suno()` to pass new parameters through the call chain
- **`platform_api/services/web_music_service.py`**: 
  - Added parameters to `generate()` method
  - Added new `generate_draft()` method for lyrics/title generation
  - Construct `SunoRequest` with all new optional parameters
- **`platform_api/routers/web_music.py`**: 
  - Updated `WebMusicGenerateRequest` with new fields (validated via Pydantic)
  - Added `POST /web-music/generate-draft` endpoint for auto-generation
  - Model pattern now accepts both `V5` and `V5_5`

### Frontend Changes
- **`music_web/src/lib/web-music-api.ts`**: Updated TypeScript types to include new parameters
- **`music_web/src/components/create-page-client.tsx`**: 
  - Added state for all new options (model, negativeTags, vocalGender, etc.)
  - Replaced static "V5" text with dynamic version selector dropdown
  - Added "Auto-generate lyrics & title" button with loading state
  - Created collapsible Advanced Options panel with all tuning controls
  - Updated `onCreate()` to pass all parameters to API

## Files touched

- `platform_api/clients/suno_client.py`
- `platform_api/ports/generation_port.py`
- `platform_api/services/generation_service.py`
- `platform_api/services/web_music_service.py`
- `platform_api/routers/web_music.py`
- `music_web/src/lib/web-music-api.ts`
- `music_web/src/components/create-page-client.tsx`

## API Changes

### New Endpoint
```
POST /api/v1/web-music/generate-draft
Body: { "prompt": string }
Response: { "lyrics": string, "title": string }
```

### Updated Endpoint
```
POST /api/v1/web-music/generate
Added optional fields:
- negative_tags: string | null
- vocal_gender: "m" | "f" | null
- style_weight: number (0.0-1.0) | null
- weirdness_constraint: number (0.0-1.0) | null
- audio_weight: number (0.0-1.0) | null
- model: "V5" | "V5_5" (previously only "V5")
```

## Migration / deploy

No database migrations required.

1. `python scripts/deploy/sync_platform_api_sandbox.py`
2. `python scripts/deploy/rebuild_music_web_sandbox.py`

Smoke test: Create page should show V5/V5.5 selector, Advanced Options panel, and auto-generate button in advanced mode.

## Follow-ups

- Consider adding tooltips explaining what each advanced option does
- Add preset combinations for common use cases (e.g., "More Creative", "Stay On Style")
- Track usage metrics for advanced options to inform future UX improvements
