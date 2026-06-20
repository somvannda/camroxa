# Requirements Document

## Introduction

The Platform API is a Python-based centralized backend service that replaces the desktop application's direct connections to external AI services (Suno, Fal AI, SLAI/DeepSeek). Currently the desktop app connects directly to these services using locally-stored API keys and a local ngrok tunnel for Suno callbacks. The Platform API centralizes this by acting as the authenticated middleware layer: the desktop app authenticates with the Platform API, which then proxies generation requests to external AI services while managing credits, licenses, and user data.

The API also serves as the data layer for a future web admin portal (user/license/credit management) and a marketing website (plan purchasing). It hosts the PostgreSQL database that currently lives alongside the desktop app, making it accessible to all ecosystem projects.

## Glossary

- **Platform_API**: The Python REST API backend service that acts as middleware between ecosystem clients and external AI model services
- **Desktop_App**: The existing PyQt6 desktop application for music generation, video creation, and YouTube uploads
- **Web_Portal**: The future web-based administration interface for managing users, licenses, credits, and content
- **Marketing_Website**: The future public-facing website where users purchase plans and the desktop application
- **User**: A registered individual who authenticates with the Platform_API to access generation services
- **Admin**: A User with elevated privileges who manages other users, licenses, credits, and system configuration
- **License**: A software entitlement that grants a User access to the Desktop_App, associated with a specific Plan type
- **Plan**: A subscription tier determining a User's profile allowance, song quota, and credit allocation (Monthly at $79/month, Yearly at $699/year, or Lifetime at $1,499 one-time); all pricing parameters are Admin-configurable
- **Credit_Wallet**: A unified per-User credit balance that can be spent on any AI model operation through the Platform_API; Lifetime users and users who exhaust their plan quota purchase credit packs into this wallet
- **Credit_Pack**: An Admin-configurable bundle of song credits available for purchase (Starter $49/500 songs, Creator $149/2,000 songs, Agency $699/10,000 songs); pricing and quantities are adjustable by Admin at any time
- **Credit_Pricing**: An Admin-configurable setting per AI model that defines how many wallet credits are charged to the user per operation (set higher than the actual external API cost to generate profit margin)
- **User_Profile**: The account-level profile of a User containing display name, email, avatar, plan info, and wallet balance
- **Channel_Profile**: A music generation configuration managed in the Desktop_App containing folder paths, image prompts, video template references, YouTube upload settings, and output resolution; synced to the Platform_API for reporting and allowance enforcement
- **Music_Prompt**: An Admin-managed combination of song description (genre/mood/energy) and song structure (section headers like [Verse], [Chorus], [Bridge]) used internally by the Platform_API to drive LLM-based lyric generation; hidden from end users who only see the generated title, album, and lyrics
- **Song_Draft**: A generated song containing title, album name, and structured lyrics produced by an LLM provider before submission to Suno
- **Suno_Task**: A record tracking a music generation request submitted to the Suno API, including task ID, status, audio URLs, and download state
- **Image_Job**: A record tracking a background or thumbnail image generation request submitted to Fal AI or SLAI
- **Batch**: A group of songs generated together in a single run, tied to a profile pair (OK channel + Alt channel) and a run date
- **Auth_Service**: The authentication and authorization subsystem of the Platform_API responsible for token issuance, validation, and role enforcement
- **Callback_Endpoint**: A public URL endpoint on the Platform_API that receives completion notifications from external AI services (replacing the desktop app's local ngrok tunnel)

## Requirements

### Requirement 1: User Authentication

**User Story:** As a Desktop_App user, I want to authenticate with the Platform API using my credentials, so that I can access generation services through a centralized secure gateway.

#### Acceptance Criteria

1. WHEN a User submits valid credentials (email and password), THE Auth_Service SHALL return an access token (valid for 30 minutes) and a refresh token (valid for 7 days) within 2 seconds
2. WHEN a User submits invalid credentials, THE Auth_Service SHALL return an authentication error message indicating the cause of failure without revealing whether the email or password was incorrect, within 2 seconds
3. WHEN an access token expires, THE Auth_Service SHALL allow the User to obtain a new access token using a valid refresh token without re-entering credentials
4. IF a refresh token is expired or revoked, THEN THE Auth_Service SHALL require the User to re-authenticate with credentials and SHALL invalidate all access tokens previously issued with that refresh token
5. THE Auth_Service SHALL hash all stored passwords using bcrypt with a minimum work factor of 12
6. WHEN the Desktop_App starts, THE Platform_API SHALL accept token-based authentication for all subsequent API requests without requiring credentials on each call
7. IF a User fails authentication 5 consecutive times for the same email, THEN THE Auth_Service SHALL lock the account for 15 minutes and reject further authentication attempts for that email with an account-locked error

### Requirement 2: User Registration and Account Management

**User Story:** As a new user, I want to create an account on the platform, so that I can purchase a license and use the music generation ecosystem.

#### Acceptance Criteria

1. WHEN a new user submits a registration request with a valid email address, a password meeting security requirements, and a display name between 2 and 50 characters, THE Platform_API SHALL create a User account and return a confirmation containing the assigned user identifier, email, and display name
2. WHEN a registration request contains an email already associated with an existing account, THE Platform_API SHALL reject the request with a duplicate email error
3. THE Platform_API SHALL validate that passwords meet minimum security requirements (minimum 8 characters, maximum 128 characters, at least one uppercase letter, one lowercase letter, and one digit)
4. IF a registration request contains an invalid email format or a password that does not meet security requirements or a display name outside the 2–50 character range, THEN THE Platform_API SHALL reject the request with a validation error indicating which fields failed
5. WHEN a User account is created, THE Platform_API SHALL assign the default User role with no active license and a Credit_Wallet balance of zero
6. WHEN a User updates their display name or password, THE Platform_API SHALL validate the new value against the same rules as registration, persist the change, and return the updated account record

### Requirement 3: User Management (Admin)

**User Story:** As an Admin, I want to view, edit, suspend, and delete user accounts through the Web Portal, so that I can manage the platform's user base.

#### Acceptance Criteria

1. WHEN an Admin requests the user list, THE Platform_API SHALL return a paginated list of User accounts (default page size 25, maximum 100) with filtering by status (active, suspended, deleted), plan type, and registration date range
2. WHEN an Admin updates a User's account details (display name, role, plan), THE Platform_API SHALL persist the changes and return the updated User record
3. WHEN an Admin suspends a User account, THE Platform_API SHALL revoke all active tokens for that User, prevent new authentication, and record the suspension reason; WHEN an Admin reactivates a suspended account, THE Platform_API SHALL restore authentication access
4. WHEN an Admin deletes a User account, THE Platform_API SHALL soft-delete the record (set deleted_at timestamp), preserve audit history, and revoke all associated licenses
5. IF a non-Admin User attempts an admin-only operation, THEN THE Platform_API SHALL return a 403 Forbidden response
6. IF an Admin attempts to update or delete a User account that does not exist, THEN THE Platform_API SHALL return a 404 Not Found response

### Requirement 4: License and Plan Management

**User Story:** As an Admin, I want to manage subscription plans and licenses with configurable pricing and quotas, so that I can control access tiers and retain flexibility to adjust pricing at any time.

#### Acceptance Criteria

1. THE Platform_API SHALL support Admin-configurable Plan types with the following default configurations stored in a plans table that Admins can update at any time without code changes:
   - **Monthly Plan**: $79/month, 2 Channel_Profiles, 420 songs/month quota (7 songs/day/channel), 30-day billing cycle, AI generation included within quota
   - **Yearly Plan**: $699/year, 4 Channel_Profiles, 840 songs/month quota (7 songs/day/channel), 365-day billing cycle, AI generation included within quota
   - **Lifetime Plan**: $1,499 one-time, unlimited Channel_Profiles, lifetime software access, all future updates; does NOT include unlimited AI generation — user must purchase credit packs for all generation
2. WHEN an Admin updates a Plan's configuration (price, profile allowance, song quota, or billing cycle), THE Platform_API SHALL store the change with an effective date and apply it to all new subscriptions from that date forward; existing active subscriptions SHALL retain their original terms until renewal
3. WHEN an Admin creates a new License, THE Platform_API SHALL generate a unique license key and store it with the specified Plan type, pricing tier, and activation parameters; for Monthly and Yearly plans, THE Platform_API SHALL set the expiration period based on the plan's billing cycle from activation date
4. WHEN a License is assigned to a User who has no active License of the same Plan type, THE Platform_API SHALL associate the license key with the User account and activate the corresponding Plan with the profile allowance and song quota defined by the Plan configuration
5. WHEN the Desktop_App starts and the User authenticates, THE Platform_API SHALL validate the User's license status and return the active Plan details including: plan type, total profile allowance, monthly song quota, songs remaining in current period, credit wallet balance, and subscription expiration date (if applicable)
6. THE Platform_API SHALL enforce daily song generation limits per channel (configurable, default 7 songs/day/channel) and monthly song generation limits per plan; IF a User exceeds the daily or monthly quota, THEN THE Platform_API SHALL reject generation requests with a quota-exceeded error indicating the limit, current usage, and reset time
7. WHEN an Admin revokes a License, THE Platform_API SHALL mark the license as revoked, deactivate the associated Plan for that User, and recalculate the User's total profile allowance (existing Channel_Profiles exceeding the new limit SHALL be preserved but no new profiles may be created until under the limit)
8. WHILE a License is expired (Monthly or Yearly plan past its billing cycle expiration date), THE Platform_API SHALL reject generation requests from that User and return a license-expired error indicating the expiration date and renewal options
9. IF an Admin attempts to assign a License to a User who already has an active License of that same Plan type, THEN THE Platform_API SHALL reject the assignment with a duplicate-license error indicating the existing active license
10. THE Platform_API SHALL support a launch offer configuration: Admins can set a promotional price and a maximum redemption count (e.g., first 50 customers get Lifetime at $999 instead of $1,499); WHEN the redemption count is reached, THE Platform_API SHALL automatically revert to the standard price for new purchases
11. THE Platform_API SHALL store all plan pricing, quotas, and profile allowances as Admin-editable configuration records (not hardcoded), enabling changes to any pricing parameter through Admin API endpoints without requiring code deployment
12. WHEN an Admin deactivates a Plan (sets is_active to false), THE Platform_API SHALL prevent new license creation and assignment for that Plan type; existing active licenses on the deactivated Plan SHALL continue operating normally until expiration or revocation; WHEN an Admin reactivates a Plan (sets is_active to true), THE Platform_API SHALL resume allowing new license creation and assignment for that Plan type

### Requirement 5: Credit Pricing Configuration

**User Story:** As an Admin, I want to configure the credit cost charged to users for each AI model operation, so that I can set prices above the actual external API cost and generate profit margins.

#### Acceptance Criteria

1. WHEN an Admin configures credit pricing for an AI model, THE Platform_API SHALL store the model identifier, operation type, credits-per-operation charge (integer value between 1 and 10,000 inclusive), and the actual external API cost per operation (Admin-provided decimal value)
2. WHEN an Admin updates the credit price for an AI model operation, THE Platform_API SHALL apply the new price to all subsequent generation requests without affecting previously charged transactions
3. THE Platform_API SHALL support pricing configuration for each AI model operation type: Suno music generation, Fal AI image generation, SLAI image generation, and LLM lyric generation (DeepSeek/SLAI)
4. WHEN an Admin queries the pricing table, THE Platform_API SHALL return all configured model operations with their current credit charge, the actual external API cost, and the calculated margin (credit charge minus external cost) for each operation
5. THE Platform_API SHALL enforce that credit prices are integers greater than or equal to 1; IF an Admin submits a credit price of 0, negative, or non-integer, THEN THE Platform_API SHALL reject the request with a validation error indicating the acceptable range
6. IF a User submits a generation request for an AI model operation that has no pricing configured, THEN THE Platform_API SHALL reject the request with an error indicating that the operation is not yet available
7. THE Platform_API SHALL enforce a unique constraint on the combination of model identifier and operation type; IF an Admin attempts to create a duplicate pricing entry, THEN THE Platform_API SHALL reject the request with a conflict error

### Requirement 6: Credit Wallet and Credit Pack Purchasing

**User Story:** As a User, I want to purchase credit packs into my unified wallet, so that I can continue using AI generation services after my plan's included quota is consumed or as a Lifetime user.

#### Acceptance Criteria

1. THE Platform_API SHALL support Admin-configurable credit packs stored in a credit_packs table that Admins can update at any time without code changes; default packs:
   - **Starter Pack**: $49, 500 songs (250 AI requests), available to all users
   - **Creator Pack**: $149, 2,000 songs (1,000 AI requests), available to all users
   - **Agency Pack**: $699, 10,000 songs (5,000 AI requests), available to all users
2. WHEN an Admin creates or updates a credit pack configuration (name, price, song credits, request count, availability), THE Platform_API SHALL store the change and apply it to all subsequent purchases; existing purchased packs already credited to wallets SHALL NOT be affected
3. WHEN a User initiates a credit pack purchase with a valid payment confirmation, THE Platform_API SHALL add the pack's song credits to the User's Credit_Wallet balance, where the credited quantity matches the purchased pack's configured song credit amount
4. THE Platform_API SHALL maintain a single unified Credit_Wallet per User; credits in the wallet are usable for any AI model operation (Suno, image generation, LLM) and the balance SHALL be stored as a non-negative integer
5. WHEN a credit pack purchase is completed, THE Platform_API SHALL record the transaction with timestamp, pack identifier, pack name, amount paid, credit quantity added, and payment reference
6. IF a credit pack purchase fails due to payment processing error, THEN THE Platform_API SHALL not modify the User's wallet balance and return an error indicating the payment failure reason
7. WHEN an Admin manually adjusts a User's wallet balance (add bonus credits or subtract for dispute resolution), THE Platform_API SHALL apply the adjustment and record the transaction with reason, provided the resulting balance does not go below zero or exceed 10,000,000 credits
8. WHEN a User requests their wallet balance, THE Platform_API SHALL return the current credit balance, active plan song quota remaining (if on Monthly/Yearly), and the most recent 50 transactions (credits purchased, credits consumed per operation, refunds), with support for paginated retrieval of older transactions
9. THE Desktop_App SHALL display the User's Credit_Wallet balance in a persistent header or toolbar area visible on all primary screens without requiring navigation or scrolling
10. IF a credit pack purchase would cause the User's Credit_Wallet balance to exceed 10,000,000 credits, THEN THE Platform_API SHALL reject the purchase and return an error indicating the maximum wallet balance would be exceeded
11. WHEN a Lifetime plan is activated for a User, THE Platform_API SHALL credit 1,000 bonus song credits to the User's Credit_Wallet as a one-time grant and record it as a "lifetime_bonus" transaction
12. FOR Monthly and Yearly plan users, THE Platform_API SHALL first consume the plan's included monthly song quota before deducting from the Credit_Wallet; WHEN the monthly quota is exhausted, subsequent generation requests SHALL deduct from the Credit_Wallet
13. FOR Lifetime plan users, THE Platform_API SHALL deduct from the Credit_Wallet for all generation requests; IF the wallet balance is zero, THEN THE Platform_API SHALL reject generation requests with an error indicating available credit packs for purchase

### Requirement 7: Credit Deduction on Generation

**User Story:** As a platform operator, I want credits deducted from the user's wallet at the configured pricing rate when they invoke AI operations, so that usage is monetized with profit margin.

#### Acceptance Criteria

1. WHEN a User submits a Suno music generation request, THE Platform_API SHALL atomically deduct the Admin-configured Suno credit price (e.g., 14 credits per song pair) from the User's Credit_Wallet before forwarding the request to the Suno API, such that concurrent requests from the same User cannot overdraw the balance below zero
2. WHEN a User submits an image generation request (background or thumbnail), THE Platform_API SHALL atomically deduct the Admin-configured image credit price from the User's Credit_Wallet before forwarding the request
3. WHEN a User submits a song draft generation request (LLM lyrics/title/album), THE Platform_API SHALL atomically deduct the Admin-configured LLM credit price from the User's Credit_Wallet before forwarding the request
4. IF the User's Credit_Wallet balance is insufficient for the configured price of the requested operation, THEN THE Platform_API SHALL reject the request with an insufficient-credits error indicating the required amount and current balance
5. WHEN a credit deduction is performed, THE Platform_API SHALL record the transaction with User identifier, AI model, operation type, credits charged, batch ID (if applicable), and timestamp
6. IF the Platform_API fails to deliver the request to the external AI service (network error, connection timeout, or the external service returns a non-retryable error), THEN THE Platform_API SHALL refund the charged credits to the User's Credit_Wallet and record the refund transaction with the failure reason
7. IF a generation request has been forwarded to an external AI service and no response or callback is received within a configurable timeout period (default 300 seconds), THEN THE Platform_API SHALL treat the request as failed, refund the charged credits to the User's Credit_Wallet, and record the refund transaction

### Requirement 8: Channel Profile Management

**User Story:** As a User, I want to manage my Channel Profiles through the Platform API, so that my generation configurations are synchronized between the Desktop App and the Web Portal for reporting and allowance tracking.

#### Acceptance Criteria

1. THE Platform_API SHALL enforce Channel_Profile count limits based on the User's active Plan: Lifetime plan allows 5 Channel_Profiles, Monthly plan allows 3 Channel_Profiles, Additional plan adds purchased slots to the base allowance up to a maximum of 20 total Channel_Profiles per User
2. WHEN a User creates a Channel_Profile via the Desktop_App, THE Platform_API SHALL validate that the profile name is unique per User and does not exceed 100 characters, then store the profile with name, folder name, run prefix, logo path, video template ID, reel template ID, output resolution, image configuration (mode, background prompt, thumbnail prompt, sample settings), and YouTube upload settings (visibility, category, playlist, tags, title template, description template, publish schedule, OAuth app ID)
3. WHEN a User updates a Channel_Profile, THE Platform_API SHALL persist all changed fields and return the updated Channel_Profile record within 2 seconds
4. IF a User attempts to create a Channel_Profile beyond the allowed limit, THEN THE Platform_API SHALL reject the request with a profile-limit-exceeded error indicating the current count, maximum allowed count, and the Additional plan as the upgrade path
5. IF a User attempts to update or delete a Channel_Profile that does not exist or belongs to another User, THEN THE Platform_API SHALL return a not-found error
6. WHEN a User deletes a Channel_Profile, THE Platform_API SHALL remove the profile record and dissociate it from any active channel assignments (channelOkProfileIds, channelAltProfileIds); in-progress Batches referencing the deleted profile SHALL continue using the configuration captured at batch creation
7. WHEN the Desktop_App requests the Channel_Profile list, THE Platform_API SHALL return all Channel_Profiles for the authenticated User ordered by name in ascending alphabetical order
8. WHEN an Admin views a User's Channel_Profiles through the Web_Portal, THE Platform_API SHALL return the profiles with all-time usage statistics (batches generated, songs produced, credits consumed) aggregated from the User's Batch and credit transaction records

### Requirement 9: Music Prompt Management (Admin-Only, Hidden from Users)

**User Story:** As an Admin, I want to manage song descriptions and song structures that drive music generation, so that users receive high-quality generated music without needing to understand prompt engineering.

#### Acceptance Criteria

1. WHEN an Admin creates a song description (Music_Prompt), THE Platform_API SHALL store it with a name (1–100 characters, unique across descriptions), content text (1–5000 characters, genre/mood/energy description), and optional match key for structure pairing
2. WHEN an Admin creates a song structure, THE Platform_API SHALL store it with a name (1–100 characters, unique across structures), content text (1–5000 characters, section headers like [Verse], [Chorus], [Bridge]), and optional match key for description pairing
3. WHEN an Admin updates a song description or structure, THE Platform_API SHALL persist the changed fields and return the updated record; WHEN an Admin deletes a description or structure, THE Platform_API SHALL remove it and dissociate it from any match key pairings
4. THE Platform_API SHALL use Admin-managed descriptions and structures internally during song draft generation; the Desktop_App SHALL NOT display descriptions or structures to end users
5. WHEN a User views their generated songs, THE Platform_API SHALL expose only the title, album name, and lyrics; the description and structure used for generation SHALL be stored for admin reporting but hidden from the User
6. THE Platform_API SHALL support the matchDescriptionStructure pairing mode: WHEN enabled, THE Platform_API SHALL pair descriptions with structures by matching matchKey values during batch generation; IF a description or structure has a matchKey with no corresponding counterpart, THEN THE Platform_API SHALL skip that item and log a warning
7. THE Platform_API SHALL support cycling through structures (cycleStructures setting): structures are assigned sequentially to songs in batch order, wrapping to the first structure after the last is used; shuffling mode randomizes the assignment order using a seeded random generator per Batch

### Requirement 10: Song Draft Generation (LLM Proxy)

**User Story:** As a User, I want the Platform API to generate song drafts (title, album, lyrics) using LLM services, so that I no longer need to store LLM API keys locally in the Desktop App.

#### Acceptance Criteria

1. WHEN a User submits a song draft generation request with language, creativity level (0-100), description, structure, avoid lists (recent titles, albums, and lyric openings each capped at 200 entries), and optional forced values, THE Platform_API SHALL forward the request to the configured LLM provider (DeepSeek or SLAI) and return the generated title, album, and lyrics within 30 seconds per LLM attempt
2. THE Platform_API SHALL support configurable LLM providers per operation type: songDraftProvider, titleAlbumProvider, and lyricsProvider, each mapped to a registered AI model endpoint
3. WHEN generating a song draft, THE Platform_API SHALL enforce the song structure by validating that returned lyrics contain the exact section headers in the exact order specified, contain no content lines before the first header, and have at least max(16, number_of_section_headers × 4) non-empty content lines (or 32 if no headers are provided), retrying up to the configured maximum attempts (default 8)
4. WHEN generating a title and album, THE Platform_API SHALL enforce uniqueness by checking the generated title and album against the User-provided avoid lists (normalized text comparison), reject drafts where the title or album matches an entry in the avoid list, and retry up to the configured maximum attempts (default 6)
5. IF all generation attempts are exhausted without producing a valid result, THEN THE Platform_API SHALL return an error response indicating the failure reason and the last rejection causes, and refund the credits deducted for that operation to the User's Credit_Wallet
6. THE Platform_API SHALL accept optional forced values (forced_title, forced_album, forced_opening) and pass them through to the LLM as constraints; WHEN forced_title or forced_album is provided, THE Platform_API SHALL use the forced value in the output regardless of the LLM response, and WHEN forced_opening is provided, THE Platform_API SHALL inject it as the first lines of the generated lyrics
7. IF the LLM provider returns an unparseable response (invalid JSON or missing required keys: title, album, lyrics), THEN THE Platform_API SHALL count it as a failed attempt and retry within the configured maximum attempts

### Requirement 11: Suno Music Generation Proxy

**User Story:** As a User, I want the Platform API to submit music generation requests to Suno and handle callbacks, so that the Desktop App no longer needs a local ngrok tunnel for Suno callbacks.

#### Acceptance Criteria

1. WHEN a User submits a Suno generation request with model version (V5 or V5_5), title, lyrics, style, and instrumental flag, THE Platform_API SHALL forward the request to the Suno API within 30 seconds and return the Suno-assigned task ID to the caller
2. THE Platform_API SHALL provide a public Callback_Endpoint URL that replaces the Desktop_App's local ngrok callback, receiving Suno completion notifications
3. WHEN the Callback_Endpoint receives a Suno completion notification containing a recognized task ID, THE Platform_API SHALL update the corresponding Suno_Task record with status (SUCCESS or FAILED), audio URLs (OK track and Alt track), and push a WebSocket notification to the User's connected clients
4. WHEN a User requests the status of a Suno_Task, THE Platform_API SHALL return the current status (PENDING, SUCCESS, or FAILED), audio URLs if status is SUCCESS, and download state (downloaded_ok, downloaded_alt flags)
5. THE Platform_API SHALL detect duplicate requests by computing a SHA-256 hash of the normalized request fields (model + title + lyrics + style + instrumental); IF a Suno_Task with the same hash already exists for the same User, THEN THE Platform_API SHALL return the existing task ID and current status without resubmitting to Suno
6. WHEN Suno audio URLs become available in a Suno_Task record, THE Platform_API SHALL store the OK track URL and Alt track URL in the Suno_Task record and mark the task status as SUCCESS
7. IF the Suno API returns an error or does not respond within 30 seconds when the Platform_API forwards a generation request, THEN THE Platform_API SHALL return an error response indicating whether the failure is retryable (timeout, rate limit, 5xx) or permanent (4xx validation error), and SHALL NOT create a Suno_Task record
8. IF the Callback_Endpoint receives a notification with an unrecognized task ID or malformed payload, THEN THE Platform_API SHALL discard the notification and log the event without affecting existing Suno_Task records

### Requirement 12: Image Generation Proxy

**User Story:** As a User, I want the Platform API to proxy image generation requests to Fal AI or SLAI, so that image API keys are centrally managed and credit usage is tracked.

#### Acceptance Criteria

1. WHEN a User submits a background image generation request with prompt (1 to 2000 characters), reference image (PNG bytes as base64, maximum 10 MB decoded), resolution (width and height each between 512 and 2048 pixels), and style strength (decimal value from 0.0 to 1.0 inclusive), THE Platform_API SHALL forward the request to the configured image provider (Fal AI or SLAI) and return the generated image as PNG bytes within 60 seconds
2. WHEN a User submits a thumbnail image generation request with prompt (1 to 2000 characters), overlay input image (PNG bytes as base64, maximum 10 MB decoded), and resolution (width and height each between 512 and 2048 pixels), THE Platform_API SHALL forward the request to the configured provider and return the generated overlay image as PNG bytes within 60 seconds
3. THE Platform_API SHALL support provider selection per image type: imageBackgroundProvider and imageThumbnailProvider, each configurable as "fal" or "slai"
4. THE Platform_API SHALL support multiple Fal AI models (flux-dev-i2i, flux2-klein) and multiple SLAI models, selectable through Admin configuration per provider setting
5. IF the external image provider returns an error, THEN THE Platform_API SHALL return a standardized error response indicating whether the error is retryable (timeout exceeding 60 seconds, rate limit, 5xx) or permanent (4xx client error, invalid model), and include a retry-after duration in seconds for retryable errors
6. IF a User submits an image generation request with missing required fields, an invalid base64 payload, or parameter values outside the allowed ranges, THEN THE Platform_API SHALL reject the request with a validation error response identifying each invalid field and the constraint that was violated

### Requirement 13: Batch Generation Orchestration

**User Story:** As a User, I want to generate batches of songs with associated image generation through the Platform API, so that the full pipeline (lyrics → Suno → images) is coordinated centrally.

#### Acceptance Criteria

1. WHEN a User initiates a batch generation run with profile pair (OK profile + Alt profile), song count (1 to 50), date range, and generation settings (language, creativity level, description/structure pairing mode), THE Platform_API SHALL create a Batch record and generate the specified number of Song_Drafts using the configured LLM provider
2. WHEN Song_Drafts in a Batch are ready, THE Platform_API SHALL store them in the songs table with batch_id, batch_index, profile assignments, and status "pending"
3. WHEN the Desktop_App submits songs from a Batch to Suno, THE Platform_API SHALL create Suno_Task records with output directory paths resolved from the profile's folder configuration and the batch's run directories
4. WHEN a Suno_Task in a Batch completes with audio URLs available, THE Platform_API SHALL create Image_Job records for that song's background and thumbnail generation based on the profile's image configuration (mode: bg_thumb, thumb_only, or bg_only), independently of other incomplete Suno_Tasks in the same Batch
5. THE Platform_API SHALL track batch progress and expose a batch status endpoint returning: total songs, songs with completed drafts, songs with failed drafts, songs submitted to Suno, songs with completed Suno tasks, songs with failed Suno tasks, songs with downloaded audio, and songs with completed images
6. IF the User's Credit_Wallet balance is insufficient to cover the total estimated credit cost for the requested batch (LLM credits × song count plus Suno credits × song count), THEN THE Platform_API SHALL reject the batch request with an insufficient-credits error indicating the required total and current balance
7. IF one or more Song_Drafts in a Batch fail LLM generation after exhausting retries, THEN THE Platform_API SHALL mark those drafts as "failed", continue processing the remaining successful drafts through the pipeline, and include the failure count in the batch status
8. IF a Suno_Task in a Batch fails permanently, THEN THE Platform_API SHALL mark that song's status as "suno_failed", refund the charged Suno credits for that song to the User's Credit_Wallet, and continue processing Image_Jobs for other songs in the Batch that completed successfully

### Requirement 14: Application Settings Management

**User Story:** As a User, I want my application settings stored and served by the Platform API, so that settings are synchronized across clients and backed by the central database.

#### Acceptance Criteria

1. WHEN the Desktop_App requests application settings, THE Platform_API SHALL return the merged settings for the authenticated User within 2 seconds, where merging applies User-stored values over system defaults (User-stored values take precedence for any key that exists in both)
2. WHEN the Desktop_App submits a settings patch (partial update) containing between 1 and 50 key-value pairs, THE Platform_API SHALL persist the changed keys and return the full merged settings
3. THE Platform_API SHALL store settings as key-value pairs supporting string (maximum 10,000 characters), integer, float, boolean, and JSON object (maximum 64 KB serialized) value types, with setting keys limited to 255 characters
4. THE Platform_API SHALL exclude sensitive settings (database connection credentials, external API keys) from API responses; database connectivity is managed by the Platform_API server configuration
5. WHEN Admin-level settings are updated (global credit costs, default plan limits), THE Platform_API SHALL apply the new defaults to all Users who have not explicitly overridden those keys; Users with stored overrides SHALL retain their values
6. IF the Desktop_App submits a settings patch containing a value that does not match a supported type (string, integer, float, boolean, or JSON object), THEN THE Platform_API SHALL reject the entire patch with a validation error indicating the invalid key and expected types, and SHALL NOT persist any changes from that patch

### Requirement 15: External AI Service Credit Monitoring (Admin)

**User Story:** As an Admin, I want to monitor the platform's remaining credits on external AI services (Suno API account balance), so that I can ensure the platform has sufficient balance to fulfill user requests.

#### Acceptance Criteria

1. WHEN an Admin requests the external Suno credit balance, THE Platform_API SHALL query the Suno API credit endpoint and return the platform's remaining Suno credits within 5 seconds
2. THE Platform_API SHALL cache the external Suno credit balance for a configurable duration (default 30 seconds) to avoid excessive external API calls
3. IF the platform's external Suno credit balance falls below a configurable reserve threshold (default 100 credits), THEN THE Platform_API SHALL reject new Suno generation requests with an insufficient-platform-balance error indicating the service is temporarily unavailable, and push a low-balance alert via WebSocket to all connected Admin clients
4. THE Platform_API SHALL store the platform's external API balances separately from user wallet balances and expose external balances exclusively through Admin-only endpoints; user wallets are the internal credit system, external balances represent the platform's operational budget
5. IF the Suno API credit endpoint is unreachable or returns an error, THEN THE Platform_API SHALL serve the last cached balance value to Admin queries and, if no cached value exists, report the balance as unknown without blocking generation requests

### Requirement 16: Authorization and Role Enforcement

**User Story:** As a platform operator, I want role-based access control, so that users can only access their own resources and admins can manage the entire platform.

#### Acceptance Criteria

1. THE Platform_API SHALL enforce two roles: User (access to own resources and generation endpoints) and Admin (full management access to all users, system configuration, and music prompt management)
2. WHEN a request is received from a User-role account, THE Auth_Service SHALL validate the access token, extract the User's identity and role, and scope all data queries to the authenticated User's records; WHEN a request is received from an Admin-role account, THE Auth_Service SHALL validate the access token and grant access to all User records without user-scoping restrictions
3. IF a request lacks a valid access token, THEN THE Platform_API SHALL return a 401 Unauthorized response
4. WHILE a User's account is suspended, THE Platform_API SHALL reject all requests from that User (regardless of role) with a 403 Forbidden response and an error message indicating the account is suspended; THE Platform_API SHALL evaluate account suspension before license status or credit balance checks
5. WHILE a User's license is expired or revoked, THE Platform_API SHALL reject generation requests (Suno, image, LLM) with a 403 Forbidden response and an error message indicating the license status, but allow read-only access to existing data (Channel_Profiles, songs, history)
6. WHILE a User's Credit_Wallet balance is zero or below the required operation cost, THE Platform_API SHALL reject generation requests with a 402 Payment Required response and an error message indicating insufficient credits, but allow all other operations (profile management, settings, read access)
7. THE Platform_API SHALL enforce authorization checks in the following order: token validity (401), account suspension (403), license status (403), credit balance (402); the first failing check determines the response

### Requirement 17: Webhook and Real-Time Notifications

**User Story:** As a Desktop App user, I want to receive real-time notifications when generation tasks complete, so that the app can auto-trigger the next pipeline step (images after Suno, video after images).

#### Acceptance Criteria

1. THE Platform_API SHALL support WebSocket connections from authenticated clients for real-time event delivery, requiring a valid access token during the connection handshake and allowing a maximum of 3 concurrent WebSocket connections per User
2. WHEN a Suno_Task status changes (PENDING → SUCCESS or FAILED), THE Platform_API SHALL push a notification to the User's connected WebSocket clients within 5 seconds of the status change, including the task ID, new status, and audio URLs (empty list if FAILED)
3. WHEN an Image_Job completes or fails, THE Platform_API SHALL push a notification to the User's connected WebSocket clients within 5 seconds of the status change, including the job ID, status, and output image path (empty string if failed)
4. IF a User has no active WebSocket connections when a notification is generated, THEN THE Platform_API SHALL queue the notification and deliver all queued notifications in chronological order when the client next establishes a WebSocket connection, retaining queued notifications for a maximum of 24 hours before discarding them
5. IF a WebSocket connection receives no messages or pings for 60 seconds, THEN THE Platform_API SHALL send a ping frame; IF the client does not respond with a pong within 10 seconds, THEN THE Platform_API SHALL close the connection

### Requirement 18: Health and Status Monitoring

**User Story:** As a platform operator, I want health check endpoints, so that monitoring systems can verify the API's operational status and detect degraded external services.

#### Acceptance Criteria

1. THE Platform_API SHALL expose a public health check endpoint that returns the service status (healthy, degraded, or unhealthy), database connectivity status, uptime duration in seconds, and timestamp (UTC ISO 8601) without requiring authentication
2. WHEN any dependent service (database, Suno API, Fal AI, SLAI) fails to respond within 3 seconds, THE Platform_API SHALL report degraded status on the health endpoint identifying which service is affected; IF all dependent services are unreachable, THEN THE Platform_API SHALL report unhealthy status
3. THE Platform_API SHALL respond to health check requests within 500 milliseconds

### Requirement 19: Rate Limiting

**User Story:** As a platform operator, I want to rate-limit API requests, so that the platform remains available under load and no single user can exhaust shared resources.

#### Acceptance Criteria

1. THE Platform_API SHALL enforce per-User rate limits on each generation endpoint type (Suno, image, LLM) independently, configurable by the Admin, with a default limit of 60 requests per minute per endpoint type if no Admin configuration exists
2. WHEN a User exceeds the configured rate limit, THE Platform_API SHALL return a 429 Too Many Requests response with a Retry-After header indicating the number of seconds until the User can retry, and SHALL NOT deduct credits from the User's Credit_Wallet for the rejected request
3. THE Platform_API SHALL enforce a Suno submission rate limit matching the external API constraint (maximum 20 requests per 10-second sliding window per User)
4. WHEN an Admin updates rate limit configuration for an endpoint type, THE Platform_API SHALL apply the new limit to subsequent requests within 5 seconds without requiring a service restart

### Requirement 20: Audit Logging

**User Story:** As an Admin, I want all significant platform actions logged, so that I can review activity for security, billing disputes, and usage analysis.

#### Acceptance Criteria

1. WHEN a User or Admin performs a state-changing operation (generation request, credit purchase, profile change, license assignment) or a security-relevant operation is rejected (failed authentication, authorization failure, insufficient credits), THE Platform_API SHALL record an audit log entry with actor ID, action type, target resource, timestamp (UTC ISO 8601), credit impact (zero if not applicable), outcome (success or failure), source IP address, client identifier, and API endpoint path
2. WHEN an Admin queries the audit log with optional filters (actor, action type, resource type, date range), THE Platform_API SHALL return paginated results with a default page size of 50 entries and a maximum page size of 200 entries, and SHALL return the first page of results within 2 seconds
3. THE Platform_API SHALL retain audit log entries for a minimum of 90 days
4. THE Platform_API SHALL treat audit log entries as append-only; no API endpoint or Admin operation SHALL modify or delete an existing audit log entry within the retention period
