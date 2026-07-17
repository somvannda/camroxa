# Implementation Plan: AI Model Routing

## Overview

Implement a configurable AI model routing system that allows admins to assign AI providers per operation via the Settings page, with the platform API resolving those assignments at request time. The implementation spans the platform API (Python/FastAPI) and admin portal (React/TypeScript).

## Tasks

- [x] 1. Define routing registry constants and data models
  - [x] 1.1 Create the AI routing service module with registry constants
    - Create `platform_api/services/ai_routing_service.py`
    - Define `ServiceType` StrEnum (`text_generation`, `image_generation`, `music_generation`)
    - Define `Operation` StrEnum with all 12 operations
    - Define `OPERATION_SERVICE_TYPE`, `PROVIDER_CAPABILITIES`, `PROVIDER_SUB_MODELS`, `DEFAULT_PROVIDER`, `DEFAULT_SUB_MODEL` frozen dicts
    - Define `RoutingResult` frozen dataclass
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2_

  - [x] 1.2 Create Pydantic request/response schemas for AI routing
    - Define `OperationAssignment`, `SaveAssignmentsRequest`, `ProviderOption`, `AssignmentResponse`, `ProvidersResponse` models
    - Add provider name validation pattern
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 1.3 Create TypeScript type definitions for admin portal
    - Create `admin_portal/src/types/ai-routing.ts`
    - Define `OperationAssignment`, `ProviderOption`, `AssignmentsResponse`, `ProvidersResponse` interfaces
    - _Requirements: 6.1, 6.3_

- [x] 2. Implement core routing service logic
  - [x] 2.1 Implement the AIRoutingService class
    - Implement `resolve(operation)` method: load assignments from settings repo, validate capability, check key pool, return `RoutingResult`
    - Implement `get_all_assignments()` method: return all operations grouped by service type with defaults filled in
    - Implement `save_assignments(assignments)` method: validate capability and persist atomically
    - Implement `get_available_providers()` method: filter providers by capability AND active keys
    - Implement `_load_assignments()` helper
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 3.3, 3.4_

  - [ ]* 2.2 Write property test: Resolve returns stored assignment
    - **Property 1: Resolve returns stored assignment**
    - **Validates: Requirements 4.1, 4.2**

  - [ ]* 2.3 Write property test: Default fallback when no assignment exists
    - **Property 2: Default fallback when no assignment exists**
    - **Validates: Requirements 3.3, 4.3**

  - [ ]* 2.4 Write property test: No active keys produces 503 error
    - **Property 3: No active keys produces 503 error**
    - **Validates: Requirements 4.4**

  - [ ]* 2.5 Write property test: Available providers filtered by capability and active keys
    - **Property 4: Available providers are filtered by capability and active keys**
    - **Validates: Requirements 2.3, 2.4**

  - [ ]* 2.6 Write property test: Assignment persistence round-trip
    - **Property 5: Assignment persistence round-trip**
    - **Validates: Requirements 3.4, 6.2**

  - [ ]* 2.7 Write property test: GET assignments returns all operations
    - **Property 6: GET assignments returns all operations**
    - **Validates: Requirements 6.1**

- [x] 3. Checkpoint - Ensure all routing service tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Create admin API router and wire dependencies
  - [x] 4.1 Create the AI routing admin router
    - Create `platform_api/routers/ai_routing.py`
    - Implement `GET /admin/ai-routing` endpoint returning grouped assignments
    - Implement `PUT /admin/ai-routing` endpoint accepting and persisting full assignments
    - Implement `GET /admin/ai-routing/providers` endpoint returning available providers per service type
    - Apply `AdminAuthDep` to all endpoints
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 4.2 Register AI routing service in dependency injection
    - Add `AIRoutingService` to `platform_api/dependencies.py` (or `wire_dependencies.py`)
    - Create FastAPI `Depends()` factory for `AIRoutingServiceDep`
    - Register the router in the app factory (`main.py`)
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ]* 4.3 Write integration tests for admin AI routing endpoints
    - Test GET returns all operations with defaults when no assignments saved
    - Test PUT saves and GET reflects saved assignments
    - Test GET /providers returns only providers with active keys
    - Test unauthorized access returns 401
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 5. Integrate routing into channel_setup router
  - [x] 5.1 Inject AIRoutingService into channel_setup endpoints
    - Add `AIRoutingServiceDep` parameter to channel setup router dependencies
    - Replace hardcoded `"deepseek"` in `generate-names` with `routing_service.resolve("channel_name")`
    - Replace hardcoded provider in `generate-description` with resolves for `channel_description`, `channel_keywords`, `channel_tags`
    - Replace hardcoded provider in `generate-logo` with `routing_service.resolve("channel_logo")`
    - Replace hardcoded provider in `generate-covers` with `routing_service.resolve("channel_cover")`
    - Pass `routing.sub_model` to provider client calls
    - _Requirements: 4.1, 4.2, 4.5_

  - [x] 5.2 Update credit pricing calls in channel_setup to use resolved provider and operation name
    - Change `ai_service` from hardcoded provider to `routing.provider`
    - Change `operation_type` from generic `"text_generation"` / `"image_generation"` to specific operation name (e.g., `"channel_name"`)
    - Add `fallback_operation_type` parameter for backward compatibility
    - _Requirements: 5.3, 5.4_

- [x] 6. Integrate routing into generation router
  - [x] 6.1 Inject AIRoutingService into generation router
    - Add `AIRoutingServiceDep` parameter to generation image endpoint
    - Resolve `background_image` and `thumbnail_image` operations from routing service
    - Override any client-supplied `provider` field with the admin-assigned one
    - Pass `routing.sub_model` to provider client calls
    - Update credit pricing calls to use resolved provider and specific operation name
    - _Requirements: 4.6, 5.3_

  - [x] 6.2 Handle music and lyric operations routing
    - Resolve `lyric`, `title`, `album` operations in relevant generation endpoints
    - Resolve `music` operation for Suno-based generation
    - Update credit pricing calls accordingly
    - _Requirements: 4.1, 4.2, 5.3_

- [x] 7. Checkpoint - Ensure backend routing integration works
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Build admin portal AI routing UI
  - [x] 8.1 Create React Query hooks for AI routing
    - Create `admin_portal/src/hooks/use-ai-routing.ts`
    - Implement `useAIRoutingAssignments()` hook (GET assignments)
    - Implement `useAIRoutingProviders()` hook (GET available providers)
    - Implement `useSaveAIRoutingAssignments()` mutation hook (PUT assignments)
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 8.2 Create AI Routing section component for Settings page
    - Create `admin_portal/src/pages/settings/ai-routing-section.tsx`
    - Render operations grouped by service type (Text Generation, Image Generation, Music Generation)
    - For each operation: render a label, provider dropdown, and conditional sub-model dropdown
    - Filter provider dropdown to show only providers that support the service type AND have active keys
    - Show/hide sub-model dropdown based on whether selected provider has sub-models
    - Show defaults (DeepSeek for text, FAL for image, Suno for music) when no assignment exists
    - Implement "Save All Assignments" button calling PUT endpoint
    - Add note with link: "Credit costs are configured on the Credits page"
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 2.3, 2.4_

  - [x] 8.3 Integrate AI Routing section into the Settings page
    - Import and render `AIRoutingSection` within the existing Settings page layout
    - Position as a new Card section on the Settings page
    - _Requirements: 3.1_

- [x] 9. Update Credits page operation type dropdown
  - [x] 9.1 Update Credits page to include specific operation names in the dropdown
    - Add all 12 specific operations (`channel_name`, `channel_description`, `channel_keywords`, `channel_tags`, `channel_logo`, `channel_cover`, `lyric`, `title`, `album`, `background_image`, `thumbnail_image`, `music`) to the operation type dropdown
    - Keep old generic types visible but marked as legacy/superseded
    - _Requirements: 5.1, 5.6_

- [x] 10. Final checkpoint - Full integration verification
  - Ensure all tests pass, ask the user if questions arise.

  - [ ]* 10.1 Write property test: Pricing key composition matches resolved provider
    - **Property 7: Pricing key composition matches resolved provider**
    - **Validates: Requirements 5.3**

- [ ] 11. Enforce "Key Pool + AI Routing only" (no env fallbacks)
  - [ ] 11.1 Remove env-key fallbacks in Platform API routers/services
    - Remove `.env`/Settings-based API key access in:
      - `platform_api/routers/channel_setup.py` (text + image generation)
      - `platform_api/routers/channel_prompts.py` (DeepSeek fallback)
      - `platform_api/routers/health.py` (provider health checks)
      - `platform_api/services/generation_service.py` (OpenAI/CALA image key fallback)
    - Ensure missing keys always returns a clear 503 (`NoAvailableKeysError`) instead of attempting a fallback.
  - [ ] 11.2 Add user-facing text-generation endpoint for desktop workflows (lyrics polish)
    - Add `/api/v1/generation/polish-lyrics` using `AIRoutingService.resolve("lyric")`
    - Use Key Pool keys for the resolved provider and deduct credits under `operation_type="lyric"`

- [ ] 12. Remove desktop local AI configuration (API Keys + AI Providers)
  - [ ] 12.1 Remove Settings UI tabs/fields for AI keys and provider selection
    - Remove "OpenAI API key" input and the entire "AI Providers" tab from `python_app/views/music_view.py`
    - Stop persisting `openaiApiKey`, `songDraftProvider`, `titleAlbumProvider`, `lyricsProvider` in `python_app/app/music_ui_handlers.py`
  - [ ] 12.2 Remove/disable desktop-side direct provider calls
    - Update `python_app/features/music/coordinator.py` to generate drafts via Platform API only (no DeepSeek/SLAI/OpenAI direct calls)
    - Update lyrics polish to call Platform API (no OpenAI key input)

- [ ] 13. Verification
  - [ ] 13.1 Backend: run platform_api tests
  - [ ] 13.2 Desktop: smoke-test that changing routing in Admin Portal immediately affects:
    - song draft generation
    - lyrics polishing

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The platform API uses Python (FastAPI + asyncpg + Pydantic v2)
- The admin portal uses TypeScript (React + TanStack Query + shadcn/ui)
- Existing patterns (dependency injection, repository pattern, React Query hooks) are followed

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.3"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5", "2.6", "2.7"] },
    { "id": 3, "tasks": ["4.1", "4.2"] },
    { "id": 4, "tasks": ["4.3", "5.1", "6.1"] },
    { "id": 5, "tasks": ["5.2", "6.2"] },
    { "id": 6, "tasks": ["8.1"] },
    { "id": 7, "tasks": ["8.2", "9.1"] },
    { "id": 8, "tasks": ["8.3"] },
    { "id": 9, "tasks": ["10.1"] }
  ]
}
```
