# Implementation Plan: Cost Breakdown Estimator

## Overview

This implementation plan covers the cost breakdown estimator feature spanning the Platform API (FastAPI backend) and Admin Portal (React SPA). The plan follows a backend-first approach: Pydantic response schemas, then service layer with calculation logic, then API endpoint, and finally the frontend types, hooks, and page components wired together.

## Tasks

- [ ] 1. Set up backend schemas and service structure
  - [ ] 1.1 Create Pydantic response schemas for cost estimation
    - Create `platform_api/models/cost_estimate_schemas.py` with `ModelCostEntrySchema`, `ProviderCostGroupSchema`, `BatchCostBreakdownSchema`, `PlanCostAnalysisSchema`, `CostDistributionEntrySchema`, `CostEstimateResponseSchema`
    - Each schema uses Pydantic v2 BaseModel with appropriate field types and defaults
    - `CostEstimateResponseSchema` includes `warnings: list[str] = Field(default_factory=list)` and `average_margin_percentage: float | None = None`
    - _Requirements: 5.3_

  - [ ] 1.2 Create CostEstimateService with calculation logic
    - Create `platform_api/services/cost_estimate_service.py` with `CostEstimateService` class
    - Constructor accepts `pool` (asyncpg connection pool) dependency
    - Implement `async calculate(songs_per_batch: int = 1, images_per_song: int = 1) -> CostEstimateResponseSchema`
    - Implement `_get_operation_cost(costs, operation_type) -> float` — returns cost for first matching operation type or 0.0
    - Implement `_group_costs_by_provider(costs) -> list[ProviderCostGroupSchema]` — groups entries by ai_service, computes subtotals, sorts by (ai_service, sub_model, operation_type)
    - Implement `_calculate_batch_cost(costs, songs_per_batch, images_per_song) -> BatchCostBreakdownSchema`
    - Implement `_calculate_plan_analysis(plan, per_song_cost, per_image_cost) -> PlanCostAnalysisSchema`
    - Implement `_calculate_distribution(costs, songs_per_batch, images_per_song) -> list[CostDistributionEntrySchema]`
    - Operation type mapping: `lyric` → text_generation, `music` → music_generation, `background_image` → image_generation
    - Per-song cost = cost of `lyric` + cost of `music`; per-image cost = cost of `background_image`
    - Batch total = (per_song_cost × songs_per_batch) + (per_image_cost × images_per_song × songs_per_batch)
    - Plan total cost cents = round((song_limit × per_song_cost + image_limit × per_image_cost) × 100)
    - Margin = price_cents − total_cost_cents; margin_pct = round((margin / price_cents) × 100, 2)
    - Unlimited plans (null song/image limit) or zero-price plans: set is_margin_applicable=False, margins=None
    - Average margin percentage = mean of calculable margins, rounded to 2 decimal places; None if no calculable plans
    - Cost distribution: percentage per provider sorted descending, percentages sum to 100% (adjusted via largest-remainder method)
    - Populate warnings array for: empty model costs table, missing lyric/music/background_image operation types
    - _Requirements: 1.1, 1.3, 2.1, 2.4, 2.5, 3.1, 3.2, 3.3, 3.5, 3.6, 4.1, 4.4, 4.5, 5.3, 5.4, 7.1, 7.2_

- [ ] 2. Implement API endpoint and wiring
  - [ ] 2.1 Create cost estimates router with GET endpoint
    - Create `platform_api/routers/cost_estimates.py` with a single `GET /api/v1/admin/cost-estimates` endpoint
    - Accept query parameters: `songs_per_batch: int = Query(default=1, ge=1, le=100)`, `images_per_song: int = Query(default=1, ge=1, le=100)`
    - Apply `require_admin` dependency for JWT + admin role check (existing pattern from other admin routes)
    - Call `CostEstimateService.calculate()` with the query params and return the result
    - FastAPI handles 422 validation error automatically for out-of-range params
    - _Requirements: 5.1, 5.2, 5.5_

  - [ ] 2.2 Register router and service dependency in FastAPI app
    - Add `CostEstimateService` instantiation in `platform_api/dependencies.py` (inject pool)
    - Register the new router in `platform_api/main.py` with prefix `/api/v1/admin` and tag `admin`
    - _Requirements: 5.1_

  - [ ]* 2.3 Write property tests for CostEstimateService
    - **Property 1: Model costs ordering invariant**
    - **Validates: Requirements 1.1**
    - Use Hypothesis to generate random model cost lists, verify entries are sorted by (ai_service, sub_model, operation_type)

  - [ ]* 2.4 Write property test for provider grouping subtotal
    - **Property 2: Provider grouping subtotal correctness**
    - **Validates: Requirements 1.3**
    - Generate random cost entries, verify subtotal_usd per group equals sum of entries, every entry appears in exactly one group

  - [ ]* 2.5 Write property test for batch cost formula
    - **Property 3: Batch cost formula**
    - **Validates: Requirements 2.1, 3.2**
    - For any valid songs_per_batch (1–100), images_per_song (1–100), and non-negative per-op costs, verify total = (text_gen + music_gen) × songs_per_batch + image_gen × images_per_song × songs_per_batch

  - [ ]* 2.6 Write property test for missing operation types
    - **Property 4: Missing operation types produce zero cost and warning**
    - **Validates: Requirements 2.5, 3.6**
    - For any subset of required operations missing, verify 0.0 cost and corresponding warning string

  - [ ]* 2.7 Write property test for active plans filtering
    - **Property 5: Only active plans included in response**
    - **Validates: Requirements 3.1**
    - Generate plans with mixed is_active values, verify only active plans appear in plan_analyses

  - [ ]* 2.8 Write property test for plan total cost formula
    - **Property 6: Plan total cost formula**
    - **Validates: Requirements 3.3**
    - For any plan with numeric limits, verify estimated_total_cost_cents = round((S × per_song + I × per_image) × 100)

  - [ ]* 2.9 Write property test for unlimited/zero-price plan exclusion
    - **Property 7: Unlimited and zero-price plans excluded from margin**
    - **Validates: Requirements 3.5, 4.5**
    - Verify is_margin_applicable=False, margins=None for unlimited or zero-price plans

  - [ ]* 2.10 Write property test for profit margin calculation
    - **Property 8: Profit margin percentage calculation**
    - **Validates: Requirements 4.1, 4.2**
    - For any margin-applicable plan, verify margin_cents = price_cents − total_cost_cents, margin_pct = round((margin / price) × 100, 2)

  - [ ]* 2.11 Write property test for average margin
    - **Property 9: Average margin is arithmetic mean**
    - **Validates: Requirements 4.4**
    - For any set of plans with calculable margins, verify average = mean of margin percentages rounded to 2dp; None if no calculable plans

  - [ ]* 2.12 Write property test for input validation
    - **Property 10: Input validation rejects out-of-range parameters**
    - **Validates: Requirements 5.5**
    - For any songs_per_batch or images_per_song outside [1, 100], verify 422 response

  - [ ]* 2.13 Write property test for cost distribution sum
    - **Property 11: Cost distribution percentages sum to 100%**
    - **Validates: Requirements 7.1**
    - For any non-zero batch cost, verify sum of percentages equals 100.0 within ±0.1

  - [ ]* 2.14 Write property test for cost distribution ordering
    - **Property 12: Cost distribution sorted by cost descending**
    - **Validates: Requirements 7.2**
    - Verify each entry's cost_usd ≥ next entry's cost_usd

- [ ] 3. Checkpoint - Backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement frontend types and data hook
  - [ ] 4.1 Create TypeScript interfaces for cost estimation
    - Create `admin_portal/src/types/cost-estimates.ts` with `ModelCostEntry`, `ProviderCostGroup`, `BatchCostBreakdown`, `PlanCostAnalysis`, `CostDistributionEntry`, `CostEstimateResponse` interfaces
    - Match the API response schema exactly
    - _Requirements: 5.3_

  - [ ] 4.2 Create useCostEstimates hook
    - Create `admin_portal/src/hooks/use-cost-estimates.ts`
    - Use TanStack Query with `queryKey: ['cost-estimates', songsPerBatch, imagesPerSong]`
    - Call `GET /api/v1/admin/cost-estimates` with `songs_per_batch` and `images_per_song` query params via Axios
    - Set `keepPreviousData: true` and `staleTime: 30_000`
    - Export `useCostEstimates(songsPerBatch: number, imagesPerSong: number)`
    - _Requirements: 5.1, 6.2_

- [ ] 5. Implement frontend page components
  - [ ] 5.1 Create BatchAssumptionsCard component
    - Create input controls for songs_per_batch (default 1) and images_per_song (default 1)
    - Accept only integers 1–100; reject empty, decimal, non-numeric
    - Show inline validation error for invalid values, preserve invalid text, use previous valid value for calculations
    - Debounce changes at 300ms before triggering re-fetch
    - Reset to defaults on page mount (ephemeral state)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ] 5.2 Create ModelCostsSummaryCard component
    - Display grouped table by ai_service with entries showing ai_service, sub_model, operation_type, cost_usd (max 8 decimal places, trailing zeros removed)
    - Show subtotal row per provider group
    - Show empty state message when no records exist, directing to settings page
    - _Requirements: 1.2, 1.3, 1.4_

  - [ ] 5.3 Create BatchCostBreakdownCard component
    - Display per-operation cost breakdown (text_generation, music_generation, image_generation) with total
    - Format cost values in USD to 2 decimal places
    - Show warning indicator next to any operation with $0.00 cost (missing operation type)
    - _Requirements: 2.2, 2.3, 2.5_

  - [ ] 5.4 Create CostDistributionCard component
    - Display horizontal bar chart or stacked bar showing percentage contribution per provider
    - Sort providers by cost descending (most expensive first)
    - Percentages to 1 decimal place
    - Tooltip on hover showing USD amount (2dp) and percentage (1dp) within 200ms
    - Empty state when total batch cost is zero
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ] 5.5 Create PlanCostAnalysisCard component
    - Display table with: plan name, subscription price (USD), song quota, image quota, estimated total AI cost (USD), per-song cost, per-image cost, profit margin (USD), profit margin percentage
    - Show "Unlimited" for null quotas; omit total cost for unlimited quota types
    - Highlight rows with negative profit margin using a warning indicator
    - Show "N/A" label for unlimited/zero-price plans where margin is not applicable
    - Display summary row with average margin percentage across calculable plans
    - _Requirements: 3.4, 3.5, 4.2, 4.3, 4.4, 4.5_

  - [ ] 5.6 Create CostEstimatesPage and wire all components
    - Create `admin_portal/src/pages/cost-estimates/index.tsx` as the main page component
    - Compose: BatchAssumptionsCard, ModelCostsSummaryCard, BatchCostBreakdownCard, CostDistributionCard, PlanCostAnalysisCard
    - Manage assumption state (songs_per_batch, images_per_song) at page level, pass to useCostEstimates hook
    - Handle loading and error states
    - _Requirements: 1.1, 6.5_

  - [ ] 5.7 Add route and navigation entry for cost estimates page
    - Add route in `admin_portal/src/App.tsx` for `/cost-estimates` path pointing to the new page
    - Add sidebar navigation entry for "Cost Estimates" under the admin section
    - _Requirements: 1.1_

- [ ] 6. Checkpoint - Frontend complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Frontend tests
  - [ ]* 7.1 Write unit tests for CostEstimatesPage
    - Test page renders all card components
    - Test default assumption values (1, 1) on mount
    - Test loading state displays skeleton/spinner
    - Test error state displays error message
    - Mock API response via MSW
    - _Requirements: 6.3, 6.5_

  - [ ]* 7.2 Write unit tests for BatchAssumptionsCard
    - Test input validation (rejects <1, >100, empty, decimal, non-numeric)
    - Test inline validation error display
    - Test debounce fires after 300ms
    - Test reset to defaults on mount
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 7.3 Write unit tests for PlanCostAnalysisCard
    - Test renders "Unlimited" for null quotas
    - Test negative margin row highlighted with warning
    - Test "N/A" for non-applicable margins
    - Test average margin summary row
    - _Requirements: 3.4, 3.5, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 7.4 Write unit tests for CostDistributionCard
    - Test empty state when batch cost is zero
    - Test providers sorted by cost descending
    - Test tooltip content on hover
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ] 8. Final checkpoint - All tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend is implemented first to allow frontend integration testing against real endpoints
- No database migrations needed — reads from existing `ai_model_costs` and `plans` tables
- Operation type mapping: `lyric` → text_generation, `music` → music_generation, `background_image` → image_generation
- The service uses graceful degradation: missing costs return zero values with warnings, not errors

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "4.1"] },
    { "id": 2, "tasks": ["2.1", "4.2"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "2.5", "2.6", "2.7", "2.8", "2.9", "2.10", "2.11", "2.12", "2.13", "2.14"] },
    { "id": 4, "tasks": ["5.1", "5.2", "5.3", "5.4", "5.5"] },
    { "id": 5, "tasks": ["5.6"] },
    { "id": 6, "tasks": ["5.7"] },
    { "id": 7, "tasks": ["7.1", "7.2", "7.3", "7.4"] }
  ]
}
```
