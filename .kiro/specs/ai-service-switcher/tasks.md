# Implementation Plan: AI Service Switcher

## Overview

This implementation plan covers the AI Service Switcher feature across the Platform API (Python/FastAPI) and Admin Portal (React/TypeScript). The feature introduces a `ServiceRouter` that resolves providers from `system_settings` at request time, replacing hardcoded provider logic. Tasks are ordered: core routing infrastructure first, then GenerationService refactoring, then API endpoints, and finally the Admin Portal UI page. Property-based tests validate routing correctness properties alongside implementation.

## Tasks

- [ ] 1. Create ServiceRouter core module
  - [ ] 1.1 Implement ServiceRouter class with provider capability registry
    - Create `platform_api/services/service_router.py`
    - Define `RoutingConfig` frozen dataclass with fields: `provider`, `model`, `fallback_provider`
    - Define `PROVIDER_CAPABILITIES` static dict mapping providers to supported operation types
    - Define `DEFAULT_PROVIDERS` dict for backward-compatible defaults (suno→music, deepseek→text, slai→image)
    - Define `DEFAULT_MODELS` dict per provider (suno→V5, deepseek→deepseek-chat, openai→gpt-5.5, slai→cgpt-web/gpt-5.5-pro, fal→flux-pro)
    - Implement `resolve(operation_type)` — reads `routing:{operation_type}` from SettingsRepository, parses JSON, returns RoutingConfig; falls back to DEFAULT_PROVIDERS if not configured
    - Implement `validate_assignment(provider, operation_type)` — raises ValidationError if provider not in PROVIDER_CAPABILITIES for that operation type
    - Implement `get_capabilities()` — returns the static PROVIDER_CAPABILITIES dict
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.4_

  - [ ] 1.2 Implement ServiceRouter update_routing method with validation
    - Implement `update_routing(operation_type, provider, model, fallback)` method
    - Validate provider supports operation_type via PROVIDER_CAPABILITIES
    - Validate fallback provider (if set) supports operation_type and differs from primary
    - Validate provider has active keys in Key Pool (query KeyPoolService)
    - Persist routing config as JSON to system_settings with key `routing:{operation_type}`
    - Return the updated RoutingConfig
    - _Requirements: 1.3, 1.4, 4.1, 4.4_

  - [ ]* 1.3 Write property tests for ServiceRouter resolve and validation
    - **Property 1: Routing Resolution Consistency**
    - For any valid (provider, operation_type) pair in PROVIDER_CAPABILITIES, after update_routing is called, resolve returns a RoutingConfig matching what was set
    - For any operation_type with no stored config, resolve returns DEFAULT_PROVIDERS[operation_type]
    - **Validates: Requirements 1.1, 1.2, 3.1, 3.2**
    - File: `platform_api/tests/properties/test_service_router.py`

  - [ ]* 1.4 Write property test for fallback validation
    - **Property 2: Fallback Never Equals Primary**
    - Generate random (provider, fallback, operation_type) tuples; verify validate_assignment rejects when fallback == primary
    - Verify fallback must support the operation_type via PROVIDER_CAPABILITIES
    - **Validates: Requirements 4.4**
    - File: `platform_api/tests/properties/test_service_router.py`

- [ ] 2. Refactor GenerationService to use dispatch pattern
  - [ ] 2.1 Add ServiceRouter dependency and dispatch methods to GenerationService
    - Inject `ServiceRouter` into GenerationService constructor (update `dependencies.py`)
    - Implement `_dispatch_text(provider, model, ...)` routing to deepseek/slai/openai clients
    - Implement `_dispatch_image(provider, model, ...)` routing to slai/fal clients
    - Implement `_dispatch_music(provider, model, ...)` routing to suno client
    - _Requirements: 3.1, 3.2, 3.3, 3.5_

  - [ ] 2.2 Refactor text generation methods to use ServiceRouter
    - Update `submit_draft()` and related text generation paths to call `self._service_router.resolve("text_generation")` at request start
    - Replace hardcoded deepseek/slai calls with `_dispatch_text(routing.provider, routing.model, ...)`
    - Implement fallback logic: on ExternalServiceError, retry with `routing.fallback_provider` if configured
    - Limit fallback to one attempt per request
    - _Requirements: 3.1, 3.4, 4.1, 4.2, 4.3, 4.5, 9.1, 9.2_

  - [ ] 2.3 Refactor image generation methods to use ServiceRouter
    - Update `submit_image()` to call `self._service_router.resolve("image_generation")` at request start
    - Replace provider selection logic with `_dispatch_image(routing.provider, routing.model, ...)`
    - Implement fallback logic for image generation (slai ↔ fal)
    - _Requirements: 3.3, 4.1, 4.2, 4.3, 9.1, 9.2_

  - [ ] 2.4 Refactor music generation methods to use ServiceRouter
    - Update music generation path to call `self._service_router.resolve("music_generation")` at request start
    - Route through `_dispatch_music(routing.provider, routing.model, ...)`
    - Ensure callback-based Suno flow remains provider-agnostic (uses external_task_id)
    - _Requirements: 3.2, 9.3_

  - [ ]* 2.5 Write unit tests for GenerationService dispatch and fallback
    - Test dispatch routes to correct client based on resolved provider
    - Test fallback triggers on ExternalServiceError and routes to fallback provider
    - Test fallback only attempted once per request
    - Test error raised when no fallback configured and primary fails
    - _Requirements: 3.1, 4.2, 4.3, 4.5_

- [ ] 3. Update Channel Setup router to use ServiceRouter
  - [ ] 3.1 Replace hardcoded providers in channel_setup router
    - Update `generate_names()`, `generate_logo()`, `generate_cover()`, `generate_description()` functions
    - Replace hardcoded `"deepseek"` / `"slai"` references with ServiceRouter.resolve() calls
    - Pass resolved provider and model to CreditService.execute_with_credits
    - _Requirements: 3.1, 3.4, 7.1_

  - [ ]* 3.2 Write unit tests for channel_setup routing integration
    - Test that channel setup functions use resolved provider from ServiceRouter
    - Test correct credits charged for resolved provider
    - _Requirements: 3.1, 7.1_

- [ ] 4. Checkpoint - Ensure core routing and dispatch tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Create Service Routing API endpoints
  - [ ] 5.1 Create service_routing router with GET endpoint
    - Create `platform_api/routers/service_routing.py`
    - Implement `GET /api/v1/service-routing` returning all routing configs with provider status
    - For each operation_type: resolve current config, query Key Pool for provider health (total keys, active keys, availability status), check credit pricing exists
    - Return response schema: routes array with operation_type, provider, model, fallback_provider, provider_status, fallback_status, has_pricing
    - Include capabilities dict in response
    - Restrict to admin-authenticated users
    - _Requirements: 8.1, 8.4, 10.1_

  - [ ] 5.2 Implement PUT endpoint for updating routing config
    - Implement `PUT /api/v1/service-routing` accepting operation_type, provider, model, fallback_provider
    - Call ServiceRouter.update_routing with full validation
    - Return 422 with specific error details for: unsupported provider, capability mismatch, no active keys, fallback == primary
    - Restrict to admin-authenticated users
    - _Requirements: 8.2, 8.3, 8.4_

  - [ ] 5.3 Implement GET capabilities endpoint
    - Implement `GET /api/v1/service-routing/capabilities` returning the provider capability matrix
    - Return the static PROVIDER_CAPABILITIES dict from ServiceRouter
    - Restrict to admin-authenticated users
    - _Requirements: 2.3_

  - [ ] 5.4 Wire ServiceRouter and service_routing router into FastAPI app
    - Register ServiceRouter in `platform_api/dependencies.py` with SettingsRepository + KeyPoolService injection
    - Include `service_routing` router in main app with `/api/v1` prefix
    - _Requirements: 8.4_

  - [ ]* 5.5 Write unit tests for service routing API endpoints
    - Test GET returns all operation types with correct status
    - Test PUT validates capability constraints (422 on mismatch)
    - Test PUT validates active keys requirement
    - Test PUT validates fallback != primary
    - Test endpoints require admin auth
    - _Requirements: 8.2, 8.3, 8.4_

- [ ] 6. Checkpoint - Ensure all API endpoint tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Admin Portal — Service Switcher page
  - [ ] 7.1 Create service routing API hooks and types
    - Create `admin_portal/src/types/service-routing.ts` with TypeScript types: RoutingRoute, RoutingCapabilities, ServiceRoutingResponse, UpdateRoutingRequest
    - Create `admin_portal/src/hooks/use-service-routing.ts` with TanStack Query hooks: useServiceRouting (GET), useUpdateRouting (PUT mutation), useRoutingCapabilities (GET)
    - Use existing Axios client pattern for API calls
    - _Requirements: 5.1, 8.1_

  - [ ] 7.2 Create ServiceRoutingCard component
    - Create `admin_portal/src/pages/service-routing/service-routing-card.tsx`
    - Display operation type with icon (🎵 music, 📝 text, 🖼️ image)
    - Provider dropdown filtered by capability + key availability
    - Model text input pre-filled with provider default
    - Fallback dropdown (same filtering, excludes primary)
    - Availability badge (green/yellow/red) for primary and fallback
    - Pricing status indicator (✅ configured, ⚠️ missing)
    - Save button per card with optimistic update via TanStack Query
    - Warning confirmation dialog when selecting "unavailable" provider
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.3, 6.4, 10.2, 10.3_

  - [ ] 7.3 Create Service Switcher page and add navigation
    - Create `admin_portal/src/pages/service-routing/index.tsx` as the page container
    - Display page title "AI Service Routing" with three ServiceRoutingCard components
    - Add "Service Routing" nav item to admin sidebar/navigation
    - Use shadcn/ui Card, Select, Input, Badge, Button, AlertDialog components
    - Style with Tailwind (consistent with existing admin pages)
    - _Requirements: 5.1, 5.2, 5.3, 7.3_

  - [ ]* 7.4 Write unit tests for Service Switcher page
    - Test routing cards render with correct data from API
    - Test provider dropdown filters by capability
    - Test fallback dropdown excludes primary provider
    - Test availability badge shows correct color based on status
    - Test warning dialog appears when selecting unavailable provider
    - Test save calls PUT endpoint with correct payload
    - Mock API with MSW
    - _Requirements: 5.2, 5.4, 5.5, 10.2, 10.3_

- [ ] 8. Credit pricing integration with resolved provider
  - [ ] 8.1 Validate credit pricing exists for resolved provider in GenerationService
    - Before dispatching to provider client, verify credit pricing entry exists for (resolved_provider, operation_type)
    - If no pricing entry exists, return 503 with descriptive error message about missing pricing configuration
    - Ensure CreditService.execute_with_credits uses the resolved provider's ai_service for pricing lookup
    - _Requirements: 7.1, 7.2_

  - [ ] 8.2 Add pricing status indicator to service routing GET endpoint
    - For each route in the GET response, query credit_pricing table for (provider, operation_type)
    - Return `has_pricing: true/false` field per route
    - _Requirements: 7.3_

- [ ] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal routing correctness (Hypothesis for Python, fast-check for TypeScript)
- Unit tests validate specific dispatch logic and edge cases
- Platform API uses Python 3.11+ (pytest + Hypothesis for property tests)
- Admin Portal uses TypeScript (Vitest + fast-check for property tests)
- The ServiceRouter is pure logic (no side effects beyond settings read/write) — easy to unit test
- Existing infrastructure reused: system_settings table, SettingsRepository, Key Pool, Credit Pricing, AIService/OperationType enums
- No database migration needed — routing config stored in existing system_settings table
- Provider resolution happens once at request start (in-progress safety) per Requirement 9

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "1.4", "2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4"] },
    { "id": 4, "tasks": ["2.5", "3.1"] },
    { "id": 5, "tasks": ["3.2", "5.1", "5.2", "5.3", "5.4"] },
    { "id": 6, "tasks": ["5.5", "7.1"] },
    { "id": 7, "tasks": ["7.2", "8.1", "8.2"] },
    { "id": 8, "tasks": ["7.3"] },
    { "id": 9, "tasks": ["7.4"] }
  ]
}
```
