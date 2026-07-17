# Requirements Document

## Introduction

The Cost Breakdown Estimator is a read-only analytics page in the Admin Portal that provides visibility into AI provider costs per batch generation cycle, plan quota economics, and profit margin analysis. It enables administrators to understand the cost structure of each plan tier by comparing what AI services charge per generation unit against what users pay through their subscription pricing.

## Glossary

- **Cost_Estimator_Page**: The admin portal page that displays cost breakdown analytics and profit margin calculations
- **Platform_API**: The FastAPI backend that serves cost estimation data from the database
- **Batch_Cycle**: A single generation run that produces songs, images, and optionally video exports for a user
- **AI_Provider**: An external service used for content generation (Suno, Fal AI/SLAI, DeepSeek/SLAI)
- **AI_Model_Cost**: A record in the `ai_model_costs` table representing the USD cost per operation for a specific AI service and sub-model
- **Plan**: A subscription tier (Monthly, Yearly, Lifetime) with defined quotas and pricing
- **Song_Quota**: The maximum number of **song packages** (lyric + title + album + Suno Primary + Secondary channel, retries included) allowed per billing cycle for a plan; only Suno music consumes a unit
- **Image_Quota**: The maximum number of image jobs (background/thumbnail each count) allowed per billing cycle; album-level batches typically consume 1 BG + 1 TH per channel per batch when both are requested
- **Cost_Per_Unit**: The calculated AI provider cost for producing one unit (one song package or one image job)
- **Profit_Margin**: The difference between plan subscription revenue and estimated total AI costs for the plan's full quota
- **Operation_Type**: The category of AI operation (music_generation, image_generation, text_generation / lyric|title|album, channel_setup)
- **Usage_Ledger**: credit_transactions rows for every billable op, including plan_allowance amount=0 rows with list_credit_units for finance reporting

## Requirements

### Requirement 1: Display AI Model Cost Summary

**User Story:** As an admin, I want to see all configured AI model costs grouped by provider, so that I can understand the per-operation cost structure of each AI service.

#### Acceptance Criteria

1. WHEN the Cost_Estimator_Page loads, THE Platform_API SHALL return all records from the ai_model_costs table ordered by ai_service, sub_model, and operation_type within 3 seconds
2. WHEN the Cost_Estimator_Page loads, THE Cost_Estimator_Page SHALL display each AI_Model_Cost record showing the ai_service name, sub_model, operation_type, and cost_usd formatted to a maximum of 8 decimal places with trailing zeros removed
3. THE Cost_Estimator_Page SHALL group AI_Model_Cost entries by ai_service and display a subtotal row per group showing the sum of cost_usd values for all operations under that ai_service
4. IF no AI_Model_Cost records exist, THEN THE Cost_Estimator_Page SHALL display an empty state message indicating that no model costs are configured and directing the admin to the settings page to add cost entries

### Requirement 2: Estimate Cost Per Batch Cycle

**User Story:** As an admin, I want to see the estimated total AI cost for a single batch generation cycle, so that I can understand the variable cost of serving one batch request.

#### Acceptance Criteria

1. THE Platform_API SHALL calculate the estimated cost per batch cycle by summing: one text_generation cost (LLM draft package slots: lyric + title + album as applicable) + one music_generation cost (Suno) + image generation costs for the batch. **Album-level images** (when enabled) SHALL be modeled as 1 background + 1 thumbnail **per channel per batch**, not per song; the estimator's `images_per_song` parameter remains a planning lever for legacy/per-song image assumptions and SHALL document album-level as the product default where both BG and TH are requested for Primary/Secondary channels
2. WHEN songs_per_batch is provided as a query parameter, THE Platform_API SHALL multiply the per-song generation costs (text + music) by that count; image costs SHALL follow the album-level or images_per_song assumption documented above
3. WHEN the Cost_Estimator_Page loads, THE Cost_Estimator_Page SHALL display the estimated cost per batch cycle broken down by operation type (LLM, music, image), showing each cost value in USD to 2 decimal places
4. THE Cost_Estimator_Page SHALL allow the admin to adjust the assumed songs-per-batch count (integer between 1 and 100) and images_per_song (integer between 1 and 100) to recalculate the batch cost estimate without a full page reload, and SHALL debounce recalculation requests by 300ms
5. THE Platform_API SHALL use the cost_usd values from the ai_model_costs table as the source for all cost calculations
6. IF a cost record for any required operation type (text_generation, music_generation, or image_generation) is missing from the ai_model_costs table, THEN THE Cost_Estimator_Page SHALL display that operation's cost as $0.00 and show a warning indicator next to the missing operation
7. THE Cost_Estimator_Page and requirements SHALL clarify that plan **song quotas** are sold as complete song packages (lyric + title + album + Suno Primary + Secondary channel, retries included), not as separate lyric/title/album allowances on the plan form

### Requirement 3: Display Plan Quota Cost Analysis

**User Story:** As an admin, I want to see what each plan's full quota costs us in AI provider fees, so that I can evaluate whether the subscription pricing covers our expenses.

#### Acceptance Criteria

1. WHEN the Cost_Estimator_Page loads, THE Platform_API SHALL return all plans where is_active is true, including each plan's name, price_cents, monthly_song_limit, and monthly_image_limit values
2. THE Platform_API SHALL calculate the per-song AI cost as the sum of one music_generation cost plus one text_generation cost from the ai_model_costs table, and the per-image AI cost as one image_generation cost from the ai_model_costs table, using the currently active cost entries for the default model of each operation type
3. THE Platform_API SHALL calculate the total estimated AI cost for each plan by summing: (monthly_song_limit multiplied by the per-song AI cost) plus (monthly_image_limit multiplied by the per-image AI cost)
4. THE Cost_Estimator_Page SHALL display for each plan: plan name, subscription price in USD, song quota, image quota, estimated total AI cost for full quota consumption in USD, per-song cost in USD, and per-image cost in USD
5. WHEN a plan has an unlimited quota (monthly_song_limit is null or monthly_image_limit is null), THE Cost_Estimator_Page SHALL display "Unlimited" for that quota field and omit the total cost calculation for the unlimited quota type while still calculating costs for any quota that has a numeric limit
6. IF the ai_model_costs table contains no entries for a required operation type (music_generation, text_generation, or image_generation), THEN THE Platform_API SHALL return zero for that operation's per-unit cost and include a warning field identifying the missing operation type

### Requirement 4: Calculate Profit Margin Per Plan

**User Story:** As an admin, I want to see the profit margin for each plan tier, so that I can determine if our pricing is sustainable and profitable.

#### Acceptance Criteria

1. THE Platform_API SHALL calculate profit margin per plan as: plan price_cents minus total estimated AI cost for the plan's full quota
2. THE Cost_Estimator_Page SHALL display the profit margin in both absolute USD value and as a percentage of the plan price, with the percentage rounded to 2 decimal places
3. WHEN the profit margin is negative (AI costs exceed plan price), THE Cost_Estimator_Page SHALL highlight the plan row with a visually distinct warning indicator
4. THE Cost_Estimator_Page SHALL display a summary row showing the unweighted arithmetic mean of profit margin percentages across all active plans that have a calculable margin
5. IF a plan has unlimited quota (monthly_song_limit is null) or a plan price_cents of zero, THEN THE Cost_Estimator_Page SHALL omit the profit margin calculation for that plan and display a label indicating the margin is not applicable

### Requirement 5: API Endpoint for Cost Estimation Data

**User Story:** As an admin portal developer, I want a dedicated API endpoint that returns pre-calculated cost estimation data, so that the frontend can render the page without complex client-side calculations.

#### Acceptance Criteria

1. THE Platform_API SHALL expose a GET endpoint at /api/v1/admin/cost-estimates that accepts optional query parameters songs_per_batch (integer, default 1, range 1–100) and images_per_song (integer, default 1, range 1–100), and SHALL return the cost estimation response within 3 seconds
2. THE Platform_API SHALL require admin authentication for the /api/v1/admin/cost-estimates endpoint; IF a non-admin User or unauthenticated request calls the endpoint, THEN THE Platform_API SHALL return a 403 Forbidden or 401 Unauthorized response respectively
3. WHEN the endpoint is called, THE Platform_API SHALL return a response containing: ai_model_costs records grouped by ai_service (each entry including ai_service, sub_model, operation_type, and cost_usd), a per-batch cost breakdown (total batch cost, cost per operation type: text_generation, music_generation, image_generation, using the provided songs_per_batch and images_per_song values), and a per-plan cost analysis for each active plan (plan name, price_cents, monthly_song_limit, monthly_image_limit, estimated total AI cost in cents for full quota consumption, profit margin in cents, and profit margin percentage); WHEN a plan has unlimited quota (monthly_song_limit is null), THE Platform_API SHALL omit the total AI cost and margin calculations for that quota field and indicate unlimited status
4. IF the ai_model_costs table is empty, THEN THE Platform_API SHALL return a response with zero values for all cost fields and include a warning field indicating missing cost configuration
5. IF the songs_per_batch or images_per_song query parameter is outside the range 1–100 or is not a positive integer, THEN THE Platform_API SHALL return a validation error indicating the acceptable range

### Requirement 6: Configurable Batch Assumptions

**User Story:** As an admin, I want to adjust the assumptions used for cost estimation (songs per batch, images per song), so that I can model different usage scenarios.

#### Acceptance Criteria

1. THE Cost_Estimator_Page SHALL provide input controls for: songs per batch (default 1), and images per song (default 1), where each input accepts only whole numbers between 1 and 100 inclusive and rejects empty values, decimal numbers, and non-numeric characters
2. WHEN the admin changes an assumption input to a valid value and the input loses focus or the admin stops typing for 300ms, THE Cost_Estimator_Page SHALL recalculate all derived values (batch cost, plan totals, margins) within 500ms without a full page reload
3. THE Cost_Estimator_Page SHALL treat assumption values as ephemeral, resetting both inputs to their defaults (songs per batch: 1, images per song: 1) each time the page loads
4. IF the admin enters an invalid assumption value (empty, non-integer, less than 1, or greater than 100), THEN THE Cost_Estimator_Page SHALL display an inline validation error adjacent to the input, preserve the invalid text in the input field, and continue using the previous valid value for all calculations until a valid value is entered
5. WHEN the Cost_Estimator_Page loads with default assumption values, THE Cost_Estimator_Page SHALL use those defaults to calculate and display the initial batch cost, plan totals, and margins

### Requirement 7: Cost Breakdown Visualization

**User Story:** As an admin, I want a clear visual representation of where costs go, so that I can quickly identify the most expensive AI services.

#### Acceptance Criteria

1. THE Cost_Estimator_Page SHALL display a cost distribution breakdown showing the percentage contribution of each AI_Provider to the total batch cost, with percentages displayed to one decimal place and rounded such that the displayed values sum to 100%
2. THE Cost_Estimator_Page SHALL sort AI_Provider entries by cost descending so the most expensive provider appears first
3. WHEN the admin hovers over a cost distribution entry, THE Cost_Estimator_Page SHALL display a tooltip within 200ms showing the USD amount formatted to two decimal places and the percentage contribution to one decimal place
4. IF the total batch cost is zero (no AI_Model_Cost records configured or all costs are $0.00), THEN THE Cost_Estimator_Page SHALL display an empty state indicating that cost distribution is unavailable until provider costs are configured
