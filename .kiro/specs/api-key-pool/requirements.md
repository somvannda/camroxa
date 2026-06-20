# Requirements Document

## Introduction

The API Key Pool feature enables the MusicGenerator platform to manage multiple API keys per external AI provider (Suno, FAL.ai, OpenAI, Slai, YouTube, Facebook). Currently, the platform stores a single API key per provider in the `system_settings` table, creating a single point of failure when a key becomes rate-limited, exhausted, or disabled. This feature introduces a key pool system with automatic failover, load balancing, usage tracking, and an admin management interface — providing redundancy and high availability for all external AI service integrations.

## Glossary

- **Key_Pool_Service**: The backend subsystem of the Platform_API responsible for managing, selecting, and monitoring API keys across all configured providers
- **API_Key_Entry**: A single API key record within a provider's pool, containing the key value, status, priority, usage counters, and metadata
- **Provider**: An external AI service integrated with the platform (Suno, FAL.ai, OpenAI, Slai, YouTube, Facebook)
- **Key_Status**: The current operational state of an API_Key_Entry: active, rate_limited, exhausted, or disabled
- **Selection_Strategy**: The algorithm used to choose which API_Key_Entry to use for a given request: round_robin or priority
- **Cooldown_Period**: A configurable duration (in seconds) after which a rate_limited key automatically transitions back to active status
- **Key_Pool_Dashboard**: The admin portal UI section displaying real-time health, usage, and status information for all API keys across providers
- **Admin_Portal**: The React/TypeScript web application used by administrators to manage platform configuration including the key pool

## Requirements

### Requirement 1: API Key Storage and Pool Configuration

**User Story:** As an Admin, I want to store multiple API keys per provider in a dedicated pool, so that the platform has redundancy when a single key becomes unavailable.

#### Acceptance Criteria

1. THE Key_Pool_Service SHALL support storage of multiple API_Key_Entry records per Provider, with each entry containing: encrypted key value, provider identifier, label (1–100 characters), priority (integer 1–100 where 1 is highest), status (active, rate_limited, exhausted, disabled), creation timestamp, and last-used timestamp
2. WHEN an Admin adds a new API_Key_Entry to a Provider pool, THE Key_Pool_Service SHALL validate that the key value is non-empty (1–500 characters), the label is unique within that Provider, and the priority is within the range 1–100; THE Key_Pool_Service SHALL store the entry with an initial status of active
3. WHEN an Admin removes an API_Key_Entry from a Provider pool, THE Key_Pool_Service SHALL delete the entry and redistribute pending requests to remaining active keys in that pool
4. WHEN an Admin updates an API_Key_Entry (label, priority, or key value), THE Key_Pool_Service SHALL persist the changes and apply the new priority to subsequent key selection without disrupting in-flight requests
5. IF an Admin attempts to add an API_Key_Entry with a label that already exists for the same Provider, THEN THE Key_Pool_Service SHALL reject the request with a duplicate-label error
6. THE Key_Pool_Service SHALL store all API key values encrypted at rest using AES-256 encryption with a server-managed encryption key

### Requirement 2: Key Selection Strategy

**User Story:** As an Admin, I want to configure how keys are selected from the pool (round-robin or priority-based), so that I can control load distribution based on my operational needs.

#### Acceptance Criteria

1. THE Key_Pool_Service SHALL support two Selection_Strategy modes per Provider: round_robin (distributes requests evenly across active keys in sequence) and priority (selects the active key with the lowest priority number first, falling back to the next lowest on failure)
2. WHEN a Provider pool is configured with the round_robin strategy, THE Key_Pool_Service SHALL cycle through active API_Key_Entry records in a deterministic sequence, advancing the position pointer after each successful selection
3. WHEN a Provider pool is configured with the priority strategy, THE Key_Pool_Service SHALL select the active API_Key_Entry with the lowest priority number; WHEN multiple keys share the same priority, THE Key_Pool_Service SHALL select among them using round-robin
4. WHEN an Admin changes the Selection_Strategy for a Provider, THE Key_Pool_Service SHALL apply the new strategy to all subsequent key selections for that Provider without restarting the service
5. THE Key_Pool_Service SHALL default to the priority selection strategy for newly created Provider pools

### Requirement 3: Automatic Failover on Key Failure

**User Story:** As a platform operator, I want the system to automatically switch to the next available key when a request fails due to rate limiting or credit exhaustion, so that generation requests succeed without manual intervention.

#### Acceptance Criteria

1. WHEN an external API returns HTTP 429 (rate limited) for a request made with a specific API_Key_Entry, THE Key_Pool_Service SHALL mark that key's status as rate_limited, record the timestamp, and immediately retry the request using the next available active key from the same Provider pool
2. WHEN an external API returns HTTP 402 (payment required) or HTTP 403 with a billing-related error for a request made with a specific API_Key_Entry, THE Key_Pool_Service SHALL mark that key's status as exhausted and immediately retry the request using the next available active key from the same Provider pool
3. WHEN a failover retry is attempted, THE Key_Pool_Service SHALL exclude all keys with status rate_limited, exhausted, or disabled from the selection pool
4. IF all API_Key_Entry records for a Provider have a non-active status (rate_limited, exhausted, or disabled), THEN THE Key_Pool_Service SHALL return an error to the caller indicating that no available keys exist for the requested Provider, including the count of keys in each status
5. THE Key_Pool_Service SHALL limit failover retries to a maximum of 3 attempts per original request to prevent infinite retry loops; IF all retry attempts fail, THEN THE Key_Pool_Service SHALL return the last error received from the external API
6. WHEN a failover occurs, THE Key_Pool_Service SHALL log the event with the failed key identifier, failure reason (HTTP status code and response body summary), and the replacement key identifier

### Requirement 4: Automatic Key Recovery After Cooldown

**User Story:** As a platform operator, I want rate-limited keys to automatically return to active status after a cooldown period, so that temporarily blocked keys rejoin the pool without manual intervention.

#### Acceptance Criteria

1. WHEN an API_Key_Entry transitions to rate_limited status, THE Key_Pool_Service SHALL schedule an automatic recovery check after the configured Cooldown_Period (default 60 seconds, configurable per Provider between 10 and 3600 seconds)
2. WHEN the Cooldown_Period elapses for a rate_limited API_Key_Entry, THE Key_Pool_Service SHALL transition the key status back to active, making it eligible for selection
3. WHEN an Admin configures the Cooldown_Period for a Provider, THE Key_Pool_Service SHALL apply the new duration to all future rate_limited events for that Provider; keys already in cooldown SHALL complete their original cooldown duration
4. THE Key_Pool_Service SHALL NOT automatically recover keys with exhausted status; exhausted keys SHALL remain in exhausted status until an Admin manually changes the status to active
5. IF an external API response includes a Retry-After header with a numeric value, THE Key_Pool_Service SHALL use that value (in seconds, capped at 3600) as the cooldown duration for that specific rate_limited event instead of the configured default

### Requirement 5: Usage Tracking Per Key

**User Story:** As an Admin, I want to track how many requests each key has processed, so that I can monitor load distribution and identify keys approaching their limits.

#### Acceptance Criteria

1. WHEN the Key_Pool_Service uses an API_Key_Entry to make a request to an external Provider, THE Key_Pool_Service SHALL increment the total request counter and the daily request counter for that key, and update the last-used timestamp
2. THE Key_Pool_Service SHALL maintain per-key counters for: total requests (all time), daily requests (reset at midnight UTC), successful requests, failed requests (4xx and 5xx responses), and rate-limit hits (429 responses)
3. WHEN a new UTC day begins, THE Key_Pool_Service SHALL reset all daily request counters to zero for all API_Key_Entry records
4. WHEN an Admin queries usage statistics for an API_Key_Entry, THE Key_Pool_Service SHALL return total requests, daily requests, success count, failure count, rate-limit hit count, last-used timestamp, and last-failure timestamp
5. THE Key_Pool_Service SHALL persist usage counters in the database, ensuring counters survive service restarts without data loss

### Requirement 6: Admin Key Pool Management UI

**User Story:** As an Admin, I want a dedicated interface in the Admin Portal to manage the API key pool per provider, so that I can add, remove, enable, disable, and monitor keys.

#### Acceptance Criteria

1. WHEN an Admin navigates to the Key Pool management page, THE Admin_Portal SHALL display a tabbed or grouped view organized by Provider, showing all API_Key_Entry records for each Provider with their label, masked key value (first 4 and last 4 characters visible), status badge, priority, daily request count, and last-used timestamp
2. WHEN an Admin adds a new API_Key_Entry through the management page, THE Admin_Portal SHALL present a form requiring: key value, label, and priority; THE Admin_Portal SHALL submit the entry to the Key_Pool_Service and display the result (success or validation error)
3. WHEN an Admin clicks the disable action on an active API_Key_Entry, THE Admin_Portal SHALL call the Key_Pool_Service to set the status to disabled and update the displayed status badge immediately
4. WHEN an Admin clicks the enable action on a disabled API_Key_Entry, THE Admin_Portal SHALL call the Key_Pool_Service to set the status to active and update the displayed status badge immediately
5. WHEN an Admin removes an API_Key_Entry, THE Admin_Portal SHALL display a confirmation dialog stating the key label and Provider before executing the deletion
6. WHEN an Admin edits the label or priority of an API_Key_Entry, THE Admin_Portal SHALL display an inline edit form, submit the change to the Key_Pool_Service, and reflect the update without a full page reload
7. THE Admin_Portal SHALL allow an Admin to configure the Selection_Strategy (round_robin or priority) and Cooldown_Period per Provider through a provider-level settings panel

### Requirement 7: Key Pool Health Dashboard

**User Story:** As an Admin, I want a health dashboard showing the real-time status of all API keys, so that I can quickly identify issues and take corrective action.

#### Acceptance Criteria

1. WHEN an Admin views the Key Pool Health Dashboard, THE Admin_Portal SHALL display a summary per Provider showing: total keys count, active keys count, rate_limited keys count, exhausted keys count, disabled keys count, and overall pool health indicator (healthy when at least one key is active, degraded when less than half are active, critical when no keys are active)
2. WHEN an API_Key_Entry status changes (active to rate_limited, rate_limited to active, or any other transition), THE Admin_Portal SHALL update the dashboard display within 5 seconds without requiring a manual page refresh
3. THE Admin_Portal SHALL display a timeline or event log of the last 50 key status transitions per Provider, showing: timestamp, key label, previous status, new status, and trigger reason (rate-limit response, manual disable, cooldown recovery, admin action)
4. WHEN an Admin hovers over or expands an API_Key_Entry in the dashboard, THE Admin_Portal SHALL display detailed metrics: total requests, daily requests, success rate percentage, average response time for the current day, time since last used, and time remaining in cooldown (if rate_limited)
5. IF a Provider pool enters the critical state (no active keys), THE Admin_Portal SHALL display a prominent alert banner on the dashboard indicating which Provider has no available keys

### Requirement 8: Integration with Existing Generation Service

**User Story:** As a platform operator, I want the key pool to integrate transparently with the existing generation service, so that all AI requests automatically use the pool without changes to the generation workflow.

#### Acceptance Criteria

1. WHEN the Generation_Service submits a request to an external AI provider (Suno, FAL.ai, OpenAI, Slai), THE Key_Pool_Service SHALL provide the appropriate API key by selecting from the Provider's pool using the configured Selection_Strategy, replacing the current single-key lookup from system_settings
2. THE Key_Pool_Service SHALL expose an asynchronous interface compatible with the existing client protocol pattern (SunoClientProtocol, FalClientProtocol, SlaiClientProtocol, LlmClientProtocol) so that the Generation_Service requires minimal code changes
3. WHILE the Key_Pool_Service contains zero API_Key_Entry records for a given Provider, THE Key_Pool_Service SHALL fall back to reading the single key value from the existing system_settings table for backward compatibility
4. WHEN the platform starts, THE Key_Pool_Service SHALL load all active API_Key_Entry records into an in-memory cache (backed by Redis) for low-latency key selection, refreshing the cache on any key pool modification
5. IF the Redis cache is unavailable, THEN THE Key_Pool_Service SHALL fall back to direct database queries for key selection and log a warning indicating degraded performance
