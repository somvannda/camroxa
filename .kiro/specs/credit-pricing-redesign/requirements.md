# Requirements Document

## Introduction

The Credit Pricing & Plan Redesign feature overhauls CAMXORA's subscription plan structure and credit pricing configuration to support granular per-service limits, transparent margin calculation, and enforcement of usage quotas across all AI operations (music, image, and text generation). The current system only tracks monthly song quotas and a single pricing entry. This redesign introduces per-service monthly and daily limits on plans, a global credit value setting, auto-calculated profit margins, service availability derived from the Key Pool, and credit-based onboarding costs.

## Glossary

- **Platform_API**: The FastAPI backend service that manages authentication, credits, licenses, and proxies AI generation requests
- **Admin_Portal**: The React-based admin web UI for managing users, plans, credits, and system configuration
- **Plan**: A subscription tier that defines per-service usage limits, profile allowances, and billing parameters
- **Credit_Pricing_Entry**: A configuration record mapping an AI service and operation type to a credit charge, external cost, and calculated margin
- **Global_Credit_Value**: A system-wide setting that defines the monetary value of a single credit (derived from credit pack pricing, e.g., $10 / 3000 credits = $0.00333 per credit)
- **Key_Pool**: The encrypted pool of API keys per AI provider, used to determine service availability
- **AI_Service**: An external AI provider integrated with the platform (Suno, FAL, OpenAI, DeepSeek, SLAI)
- **Operation_Type**: The category of AI operation performed (Music_Generation, Image_Generation, Text_Generation, Channel_Setup)
- **Sell_Price**: The calculated dollar amount a user pays per operation, derived from credits_per_operation multiplied by Global_Credit_Value
- **Profit_Margin**: The difference between Sell_Price and the external cost charged by the AI provider
- **Service_Availability**: The operational status of an AI_Service determined by whether active keys exist in the Key_Pool
- **Credit_Wallet**: A per-user credit balance used to pay for AI operations
- **Onboarding_Generation**: AI generation operations performed during channel profile setup (name, logo, cover, description)
- **Daily_Limit**: The maximum number of operations of a specific type a user can perform per day per channel
- **Monthly_Limit**: The maximum number of operations of a specific type a user can perform per billing period

## Requirements

### Requirement 1: Plan Structure Redesign

**User Story:** As an Admin, I want to configure plans with per-service monthly and daily limits for songs, images, and profiles, so that I can control usage granularly across all AI operation types.

#### Acceptance Criteria

1. THE Platform_API SHALL store Plan records with the following fields: name, price_cents, billing_cycle_days, profile_allowance, monthly_song_limit, monthly_image_limit, daily_song_limit_per_channel, daily_image_limit_per_channel, and is_active
2. WHEN an Admin creates or updates a Plan, THE Platform_API SHALL validate that monthly_song_limit is an integer between 0 and 100,000 inclusive, monthly_image_limit is an integer between 0 and 100,000 inclusive, daily_song_limit_per_channel is an integer between 1 and 1,000 inclusive, and daily_image_limit_per_channel is an integer between 1 and 1,000 inclusive
3. WHEN an Admin updates a Plan's limits, THE Platform_API SHALL apply changes to new subscriptions immediately and preserve existing active subscription limits until renewal
4. THE Admin_Portal SHALL display Plan configuration with distinct fields for monthly_song_limit, monthly_image_limit, daily_song_limit_per_channel, daily_image_limit_per_channel, and profile_allowance
5. IF an Admin sets monthly_song_limit or monthly_image_limit to 0, THEN THE Platform_API SHALL treat that operation type as unavailable for users on that Plan (generation requests for that type are rejected with a plan-limit-zero error)

### Requirement 2: Credit Pricing Configuration Redesign

**User Story:** As an Admin, I want to configure credit pricing per AI service and operation type with auto-calculated margins, so that I can visualize profitability for each operation and adjust pricing to meet revenue targets.

#### Acceptance Criteria

1. WHEN an Admin creates a Credit_Pricing_Entry, THE Platform_API SHALL store the ai_service identifier, operation_type, credits_per_operation (integer between 1 and 10,000), and external_cost_cents (integer, the provider's charge per operation in cents)
2. THE Platform_API SHALL populate the ai_service dropdown from the list of providers that have at least one key entry in the Key_Pool (regardless of key status), returning providers: Suno, FAL, OpenAI, DeepSeek, SLAI
3. THE Platform_API SHALL support the following operation_type values: Music_Generation, Image_Generation, Text_Generation, Channel_Setup
4. WHEN an Admin queries Credit_Pricing_Entry records, THE Platform_API SHALL return each entry with auto-calculated fields: sell_price_cents (credits_per_operation multiplied by Global_Credit_Value), profit_margin_cents (sell_price_cents minus external_cost_cents), and profit_margin_percent ((profit_margin_cents divided by sell_price_cents) multiplied by 100, rounded to two decimal places)
5. THE Admin_Portal SHALL display the credit pricing table with columns: AI Service, Operation Type, Credits per Operation, External Cost ($), Sell Price ($), Profit Margin ($), Profit Margin (%)
6. WHEN the Global_Credit_Value changes, THE Admin_Portal SHALL recalculate and display updated Sell_Price and Profit_Margin values for all Credit_Pricing_Entry records without requiring manual edits to each entry
7. THE Platform_API SHALL enforce a unique constraint on the combination of ai_service and operation_type; IF an Admin attempts to create a duplicate entry, THEN THE Platform_API SHALL reject the request with a conflict error

### Requirement 3: Global Credit Value Configuration

**User Story:** As an Admin, I want to set a global credit value that defines how much one credit is worth in dollars, so that all margin calculations derive from a single configurable setting.

#### Acceptance Criteria

1. THE Platform_API SHALL store a Global_Credit_Value as a system setting representing the dollar value of one credit (stored as a decimal with up to 6 decimal places, e.g., 0.003333)
2. WHEN an Admin updates the Global_Credit_Value, THE Platform_API SHALL validate that the value is a positive number greater than 0 and less than or equal to 1.0
3. WHEN an Admin sets a credit pack price and credit quantity (e.g., $10 for 3,000 credits), THE Admin_Portal SHALL display the derived Global_Credit_Value as price divided by quantity for reference
4. THE Platform_API SHALL use the Global_Credit_Value exclusively for margin display calculations in the Admin_Portal; credit deductions from user wallets SHALL use the integer credits_per_operation value from Credit_Pricing_Entry records
5. IF no Global_Credit_Value is configured, THEN THE Platform_API SHALL return margin calculations as null and THE Admin_Portal SHALL display "Not configured" in place of Sell_Price and Profit_Margin columns

### Requirement 4: Service Availability Based on Key Pool

**User Story:** As an Admin, I want to see which AI services are available based on Key Pool status, so that I can quickly identify services that need attention.

#### Acceptance Criteria

1. WHEN the Admin_Portal loads the credit pricing page, THE Platform_API SHALL return a service_availability list indicating each AI_Service's status: "available" when at least one key in the Key_Pool for that provider has status "active", "degraded" when keys exist but none have status "active" (all are rate_limited, exhausted, or disabled), and "unavailable" when no key entries exist for that provider
2. THE Admin_Portal SHALL display a status indicator next to each AI_Service in the pricing table showing the service availability state with color coding (green for available, yellow for degraded, red for unavailable)
3. WHEN a User submits a generation request for an AI_Service with status "unavailable", THE Platform_API SHALL reject the request with a 503 Service Unavailable error indicating the AI service has no configured keys
4. WHEN a User submits a generation request for an AI_Service with status "degraded", THE Platform_API SHALL attempt the request using the Key Pool failover mechanism and return a 503 error only if all failover attempts are exhausted

### Requirement 5: Onboarding Credit Costs

**User Story:** As a platform operator, I want onboarding generation steps to deduct credits from the user's wallet, so that trial credit usage is tracked and users understand the cost of channel setup.

#### Acceptance Criteria

1. WHEN a User triggers channel name generation during onboarding, THE Platform_API SHALL deduct credits equal to the configured Credit_Pricing_Entry for the Text_Generation operation type from the User's Credit_Wallet
2. WHEN a User triggers logo generation during onboarding, THE Platform_API SHALL deduct credits equal to the configured Credit_Pricing_Entry for the Image_Generation operation type from the User's Credit_Wallet
3. WHEN a User triggers cover image generation during onboarding, THE Platform_API SHALL deduct credits equal to the configured Credit_Pricing_Entry for the Image_Generation operation type per cover generated from the User's Credit_Wallet
4. WHEN a User triggers description generation during onboarding, THE Platform_API SHALL deduct credits equal to the configured Credit_Pricing_Entry for the Text_Generation operation type from the User's Credit_Wallet
5. THE Platform_API SHALL use the Channel_Setup operation type pricing when a dedicated onboarding rate is configured; IF no Channel_Setup pricing exists for the provider, THEN THE Platform_API SHALL fall back to the standard Text_Generation or Image_Generation pricing for that operation
6. IF a User's Credit_Wallet balance is insufficient to cover an onboarding generation step, THEN THE Platform_API SHALL reject the request with a 402 Insufficient Credits error indicating the required credits and current balance

### Requirement 6: Plan Limit Enforcement

**User Story:** As a platform operator, I want the system to enforce daily and monthly limits per operation type before processing generation requests, so that users cannot exceed their plan allowances.

#### Acceptance Criteria

1. WHEN a User submits a generation request, THE Platform_API SHALL check the following conditions in order: (a) credit balance is sufficient, (b) daily limit for the operation type per channel has not been reached, (c) monthly limit for the operation type has not been reached
2. IF the User's Credit_Wallet balance is less than the credits_per_operation for the requested operation, THEN THE Platform_API SHALL return HTTP 402 with error code "INSUFFICIENT_CREDITS" including fields: required_credits, current_balance, and suggested_pack
3. IF the User has reached the daily_song_limit_per_channel or daily_image_limit_per_channel for the current channel on the current day, THEN THE Platform_API SHALL return HTTP 429 with error code "DAILY_QUOTA_EXCEEDED" including fields: limit, current_usage, reset_time (next midnight UTC), and operation_type
4. IF the User has reached the monthly_song_limit or monthly_image_limit for the current billing period, THEN THE Platform_API SHALL return HTTP 429 with error code "MONTHLY_QUOTA_EXCEEDED" including fields: limit, current_usage, period_end_date, and operation_type
5. THE Platform_API SHALL track daily usage counts per user per channel per operation type, resetting counts at midnight UTC each day
6. THE Platform_API SHALL track monthly usage counts per user per operation type, resetting counts at the start of each billing period (based on subscription activation date)
7. WHILE a User is on a Lifetime plan with no monthly limits configured (monthly_song_limit and monthly_image_limit set to null), THE Platform_API SHALL skip monthly limit checks and enforce only credit balance and daily limits

### Requirement 7: Database Schema Migration

**User Story:** As a developer, I want the database schema updated to support per-service limits and enhanced pricing fields, so that the new plan and pricing structures are persisted correctly.

#### Acceptance Criteria

1. THE Platform_API SHALL add columns monthly_image_limit (INTEGER, nullable) and daily_image_limit_per_channel (INTEGER, NOT NULL, DEFAULT 7) to the plans table via an Alembic migration
2. THE Platform_API SHALL rename the column monthly_song_quota to monthly_song_limit in the plans table for naming consistency
3. THE Platform_API SHALL rename the column model_identifier to ai_service in the credit_pricing table for clarity
4. THE Platform_API SHALL add a system_settings table (if not exists) with columns: key (VARCHAR, PRIMARY KEY), value (TEXT, NOT NULL), updated_at (TIMESTAMPTZ) to store the Global_Credit_Value
5. THE Platform_API SHALL create a usage_tracking table with columns: id (UUID, PRIMARY KEY), user_id (UUID, FK to users), channel_profile_id (UUID, FK to channel_profiles, nullable), operation_type (VARCHAR), usage_date (DATE), daily_count (INTEGER, DEFAULT 0), monthly_count (INTEGER, DEFAULT 0), period_start_date (DATE), created_at (TIMESTAMPTZ), updated_at (TIMESTAMPTZ), with a unique constraint on (user_id, channel_profile_id, operation_type, usage_date)
6. THE Platform_API migration SHALL be backwards-compatible: existing data in plans and credit_pricing tables SHALL be preserved with sensible defaults for new columns (monthly_image_limit defaults to null meaning unlimited, daily_image_limit_per_channel defaults to 7)

### Requirement 8: Admin Portal UI Updates

**User Story:** As an Admin, I want the admin portal Plans and Credits pages updated to reflect the new structure, so that I can manage per-service limits and view margin calculations visually.

#### Acceptance Criteria

1. THE Admin_Portal Plans page SHALL display editable fields for: name, price, billing_cycle_days, profile_allowance, monthly_song_limit, monthly_image_limit, daily_song_limit_per_channel, and daily_image_limit_per_channel
2. THE Admin_Portal Credits pricing page SHALL display a form with dropdowns for AI Service (populated from Key Pool providers) and Operation Type (Music_Generation, Image_Generation, Text_Generation, Channel_Setup), numeric inputs for Credits per Operation and External Cost, and read-only calculated fields for Sell Price and Profit Margin
3. THE Admin_Portal Credits page SHALL include a Global Credit Value settings section displaying the current value, a form to update it, and a reference calculation showing "If credit pack is $X for Y credits, then 1 credit = $Z"
4. THE Admin_Portal Credits pricing page SHALL display a service availability badge next to each AI Service row indicating available (green), degraded (yellow), or unavailable (red) status
5. WHEN an Admin edits the Global Credit Value, THE Admin_Portal SHALL immediately recalculate all displayed Sell Price and Profit Margin values without requiring a page refresh
