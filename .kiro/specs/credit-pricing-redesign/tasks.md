# Implementation Plan: Credit Pricing & Plan Redesign

## Overview

This implementation plan covers the full credit pricing and plan redesign across the Platform API (FastAPI + asyncpg + Alembic + Redis) and Admin Portal (React + Vite + Tailwind + shadcn/ui). Tasks are ordered to build foundational schema and models first, then services and enforcement logic, then API routes, and finally the Admin Portal UI. Property-based tests validate correctness properties alongside implementation.

## Tasks

- [x] 1. Database schema migration and domain models
  - [x] 1.1 Create Alembic migration for plans table changes and new tables
    - Rename `monthly_song_quota` → `monthly_song_limit` in `plans` table
    - Add `monthly_image_limit` (INTEGER, nullable, DEFAULT NULL) to `plans`
    - Add `daily_image_limit_per_channel` (INTEGER, NOT NULL, DEFAULT 7) to `plans`
    - Rename `model_identifier` → `ai_service` in `credit_pricing` table
    - Create `system_settings` table (key VARCHAR PK, value TEXT NOT NULL, updated_at TIMESTAMPTZ)
    - Create `usage_tracking` table with all columns, unique constraint on (user_id, channel_profile_id, operation_type, usage_date), and index on (user_id, operation_type, period_start_date)
    - Ensure backwards-compatible: existing data preserved with sensible defaults
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 1.2 Update domain models and enums
    - Update `Plan` dataclass in `platform_api/models/domain.py` with renamed and new fields
    - Add `UsageRecord` dataclass to `platform_api/models/domain.py`
    - Add `AIService`, `OperationType`, `ServiceAvailability` enums to `platform_api/models/enums.py`
    - Add `MarginDetails` frozen dataclass
    - _Requirements: 1.1, 2.1, 2.3, 4.1_

- [x] 2. Repository layer
  - [x] 2.1 Create UsageTrackingRepository
    - Create `platform_api/repositories/usage_tracking_repository.py`
    - Implement `get_daily_count(user_id, channel_profile_id, operation_type, usage_date)` → int
    - Implement `get_monthly_count(user_id, operation_type, period_start)` → int
    - Implement `increment_usage(user_id, channel_profile_id, operation_type, usage_date, period_start)` with UPSERT logic (atomic increment of daily_count and monthly_count)
    - _Requirements: 6.5, 6.6, 7.5_

  - [x] 2.2 Update PlanRepository with get_user_active_plan method
    - Add `get_user_active_plan(user_id)` method that joins plans → licenses → users to return the user's active plan
    - _Requirements: 6.1, 6.7_

  - [x] 2.3 Update CreditPricingRepository for ai_service rename
    - Rename all references from `model_identifier` to `ai_service` in query methods
    - Add unique constraint enforcement handling for (ai_service, operation_type) duplicate detection
    - _Requirements: 2.1, 2.7, 7.3_

  - [x] 2.4 Create SettingsRepository for system_settings
    - Create `platform_api/repositories/settings_repository.py`
    - Implement `get_setting(key)` → str | None
    - Implement `upsert_setting(key, value)` with updated_at timestamp
    - _Requirements: 3.1, 7.4_

- [x] 3. Checkpoint - Ensure migration and repositories work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Service layer — Credit Pricing and Usage Enforcement
  - [x] 4.1 Update CreditPricingService with margin computation and service availability
    - Add `compute_margin_details(credits_per_operation, external_cost_cents, global_credit_value)` → MarginDetails | None pure function
    - Add `get_service_availability()` method querying Key Pool status per AI service
    - Rename `model_identifier` parameter to `ai_service` across all methods
    - Return `null` margins when Global Credit Value is not configured
    - _Requirements: 2.4, 2.6, 3.4, 3.5, 4.1_

  - [ ]* 4.2 Write property test for margin computation (Property 2)
    - **Property 2: Margin Computation Correctness**
    - Generate random credits_per_operation in [1, 10000], external_cost_cents (non-negative int), global_credit_value in (0, 1.0]
    - Verify sell_price_cents = round(credits × gcv × 100), profit_margin_cents = sell_price − external_cost, profit_margin_percent = round((margin / sell_price) × 100, 2)
    - File: `platform_api/tests/properties/test_margin_computation.py`
    - **Validates: Requirements 2.4**

  - [ ]* 4.3 Write property test for service availability classification (Property 5)
    - **Property 5: Service Availability Classification**
    - Generate random key pool states per provider (empty, all inactive, at least one active)
    - Verify classification: available/degraded/unavailable
    - File: `platform_api/tests/properties/test_service_availability.py`
    - **Validates: Requirements 4.1**

  - [x] 4.4 Create UsageEnforcementService
    - Create `platform_api/services/usage_enforcement_service.py`
    - Implement `check_and_deduct(user_id, channel_profile_id, operation_type, ai_service)` with ordered checks: (1) credit balance, (2) daily limit, (3) monthly limit
    - Implement `get_daily_limit(plan, operation_type)` pure function mapping operation to plan's daily limit field
    - Implement `get_monthly_limit(plan, operation_type)` pure function returning None for unlimited (null monthly limits / Lifetime plans)
    - Integrate Redis daily usage caching with key pattern `daily_usage:{user_id}:{channel_profile_id}:{operation_type}:{YYYY-MM-DD}` and 25-hour TTL
    - Handle plan-limit-zero case (monthly limit = 0 → reject with PLAN_LIMIT_ZERO)
    - Wrap credit deduction + usage increment in a PostgreSQL transaction for atomicity
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 1.5_

  - [ ]* 4.5 Write property test for enforcement check ordering (Property 7)
    - **Property 7: Enforcement Check Ordering**
    - Generate states where multiple enforcement conditions are violated simultaneously
    - Verify the error returned corresponds to the first failing check: (1) INSUFFICIENT_CREDITS, (2) DAILY_QUOTA_EXCEEDED, (3) MONTHLY_QUOTA_EXCEEDED
    - Verify that null monthly limits skip the monthly check regardless of usage count
    - File: `platform_api/tests/properties/test_enforcement_ordering.py`
    - **Validates: Requirements 6.1, 6.7**

  - [ ]* 4.6 Write property test for usage counter isolation (Property 8)
    - **Property 8: Usage Counter Isolation**
    - Generate sequences of generation operations across different (user, channel, operation_type, date) partitions
    - Verify daily count increments only for the specific partition and monthly count increments only for specific (user, operation_type, period_start) partition
    - File: `platform_api/tests/properties/test_usage_counters.py`
    - **Validates: Requirements 6.5, 6.6**

- [x] 5. Service layer — Plan validation and onboarding pricing
  - [x] 5.1 Update PlanService with per-service limit validation
    - Add validation for plan limit fields: monthly_song_limit [0, 100000], monthly_image_limit [0, 100000], daily_song_limit_per_channel [1, 1000], daily_image_limit_per_channel [1, 1000]
    - Ensure changes to active plans apply only to new subscriptions (existing active subscriptions preserve limits until renewal)
    - _Requirements: 1.2, 1.3, 1.5_

  - [ ]* 5.2 Write property test for plan limit validation boundaries (Property 1)
    - **Property 1: Plan Limit Validation Boundaries**
    - Generate random integers, verify monthly limits accepted iff in [0, 100000] and daily limits accepted iff in [1, 1000]
    - File: `platform_api/tests/properties/test_plan_validation.py`
    - **Validates: Requirements 1.2**

  - [x] 5.3 Implement onboarding credit cost deduction logic
    - Use Channel_Setup pricing entry if configured for the provider; fall back to standard Text_Generation or Image_Generation pricing
    - Deduct credits from user wallet on each onboarding step (name, logo, cover, description generation)
    - Return 402 INSUFFICIENT_CREDITS if balance is insufficient
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 5.4 Write property test for onboarding pricing resolution with fallback (Property 6)
    - **Property 6: Onboarding Pricing Resolution with Fallback**
    - Generate random pricing configurations (with/without Channel_Setup entries)
    - Verify correct pricing entry is selected and exact credits_per_operation value is deducted
    - File: `platform_api/tests/properties/test_pricing_resolution.py`
    - **Validates: Requirements 5.5, 3.4**

  - [x] 5.5 Implement Global Credit Value service methods
    - Add `get_global_credit_value()` and `update_global_credit_value(value)` to SettingsService
    - Validate: positive number > 0 and ≤ 1.0, store with up to 6 decimal places
    - _Requirements: 3.1, 3.2, 3.4, 3.5_

  - [ ]* 5.6 Write property test for Global Credit Value validation (Property 3)
    - **Property 3: Global Credit Value Validation**
    - Generate random numeric values, verify acceptance iff strictly > 0 and ≤ 1.0
    - File: `platform_api/tests/properties/test_gcv_validation.py`
    - **Validates: Requirements 3.2**

- [x] 6. Checkpoint - Ensure all service layer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Platform API router layer
  - [x] 7.1 Update Plans router with new schemas and endpoints
    - Update `PlanResponse` schema: add `monthly_image_limit`, `daily_image_limit_per_channel`, rename `monthly_song_quota` → `monthly_song_limit`
    - Update `CreatePlanRequest` and `UpdatePlanRequest` with new fields and Pydantic validation (ranges per Requirement 1.2)
    - Ensure plan CRUD endpoints use updated PlanService and return new fields
    - _Requirements: 1.1, 1.2, 1.4_

  - [x] 7.2 Update Credits router with pricing, margins, and service availability
    - Rename `model_identifier` → `ai_service` in `PricingResponse`, `CreatePricingRequest`, `UpdatePricingRequest`
    - Add computed fields `sell_price_cents`, `profit_margin_cents`, `profit_margin_percent` to `PricingResponse`
    - Add `GET /credits/service-availability` endpoint returning per-service availability list
    - Add `GET /credits/global-credit-value` and `PUT /credits/global-credit-value` endpoints
    - Enforce unique constraint on (ai_service, operation_type) — return 409 on conflict
    - Populate ai_service dropdown from providers with Key Pool entries
    - _Requirements: 2.1, 2.2, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 4.1_

  - [x] 7.3 Integrate UsageEnforcementService into generation router
    - Call `check_and_deduct()` before proceeding with generation
    - Handle 402, 429, 503 error responses with structured JSON envelope
    - Reject with 503 SERVICE_UNAVAILABLE when AI service has no configured keys
    - Attempt failover for "degraded" services before returning 503
    - _Requirements: 4.3, 4.4, 6.1, 6.2, 6.3, 6.4_

  - [x] 7.4 Wire new dependencies in FastAPI DI
    - Register UsageTrackingRepository, UsageEnforcementService, SettingsRepository, SettingsService in `dependencies.py` / `wire_dependencies.py`
    - Connect Redis dependency for daily usage caching
    - _Requirements: 6.5, 7.4, 7.5_

  - [ ]* 7.5 Write unit tests for Plans and Credits routers
    - Test plan CRUD with new fields (valid/invalid ranges)
    - Test pricing CRUD with unique constraint conflict (409)
    - Test GCV endpoints (get/update with validation)
    - Test service availability endpoint
    - _Requirements: 1.2, 2.7, 3.2, 4.1_

- [x] 8. Checkpoint - Ensure all Platform API tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Admin Portal — Plans page updates
  - [x] 9.1 Update Plans page with per-service limit fields
    - Add `monthly_image_limit` numeric input with "null = unlimited" toggle
    - Add `daily_image_limit_per_channel` numeric input
    - Rename "Monthly Quota" column header to "Monthly Song Limit"
    - Add "Monthly Image Limit" and "Daily Image Limit" columns to the plans table
    - Update Create/Edit plan dialogs with new fields and Zod validation (ranges matching backend)
    - Update TanStack Query hooks for the updated plan response schema
    - _Requirements: 1.4, 8.1_

  - [ ]* 9.2 Write unit tests for Plans page form validation
    - Test Zod schema rejects out-of-range values
    - Test unlimited toggle behavior
    - Test form submission with new fields
    - _Requirements: 1.2, 8.1_

- [x] 10. Admin Portal — Credits page updates
  - [x] 10.1 Implement Global Credit Value settings section
    - Add a card section displaying current Global Credit Value
    - Add form to update GCV (React Hook Form + Zod validation: > 0, ≤ 1.0)
    - Add reference calculator: "If credit pack is $X for Y credits, then 1 credit = $Z"
    - Create `useGlobalCreditValue()` hook for fetching and caching via TanStack Query
    - On update: recalculate all displayed margins client-side without page refresh
    - _Requirements: 3.1, 3.2, 3.3, 8.3, 8.5_

  - [x] 10.2 Update credit pricing table with margins and service availability
    - Replace free-text model input with AI Service dropdown (populated from `/credits/service-availability`)
    - Replace free-text operation type with Operation Type dropdown (enum values)
    - Add Sell Price ($), Profit Margin ($), Profit Margin (%) read-only columns
    - Display "Not configured" when GCV is null
    - Add service availability badge (green/yellow/red) beside each AI Service row
    - _Requirements: 2.2, 2.3, 2.5, 4.2, 8.2, 8.4_

  - [x] 10.3 Implement client-side margin computation for instant preview
    - Compute `sell_price = credits_per_operation × globalCreditValue` client-side on form change
    - Recalculate all visible rows when GCV is updated
    - _Requirements: 2.6, 8.5_

  - [ ]* 10.4 Write property test for client-side margin computation (Property 2 - TypeScript)
    - **Property 2: Margin Computation Correctness (client-side)**
    - Generate random credits, cost, GCV with fast-check; verify client-side calculation matches spec formula
    - File: `admin_portal/tests/properties/margin-computation.test.ts`
    - **Validates: Requirements 2.4**

  - [ ]* 10.5 Write property test for credit pack derived value (Property 4)
    - **Property 4: Credit Pack Derived Value**
    - Generate positive price/quantity pairs with fast-check; verify derived GCV = price / quantity with up to 6 decimal places
    - File: `admin_portal/tests/properties/credit-pack-derivation.test.ts`
    - **Validates: Requirements 3.3**

  - [ ]* 10.6 Write unit tests for Credits page components
    - Test service availability badge rendering (green/yellow/red)
    - Test GCV form validation
    - Test margin display with null GCV
    - Test dropdown population from service availability endpoint
    - _Requirements: 4.2, 8.2, 8.4_

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties defined in the design document (8 properties total)
- Unit tests validate specific examples and edge cases
- Platform API uses Python (pytest + Hypothesis for property tests)
- Admin Portal uses TypeScript (Vitest + fast-check for property tests)
- Redis daily usage caching uses 25-hour TTL for automatic expiry after day rollover
- All enforcement checks are wrapped in PostgreSQL transactions for atomicity (credit deduction + usage increment)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "2.2", "2.3", "2.4"] },
    { "id": 3, "tasks": ["4.1", "5.1", "5.5"] },
    { "id": 4, "tasks": ["4.2", "4.3", "5.2", "5.6"] },
    { "id": 5, "tasks": ["4.4", "5.3"] },
    { "id": 6, "tasks": ["4.5", "4.6", "5.4"] },
    { "id": 7, "tasks": ["7.1", "7.2", "7.3", "7.4"] },
    { "id": 8, "tasks": ["7.5"] },
    { "id": 9, "tasks": ["9.1", "10.1"] },
    { "id": 10, "tasks": ["9.2", "10.2", "10.3"] },
    { "id": 11, "tasks": ["10.4", "10.5", "10.6"] }
  ]
}
```
