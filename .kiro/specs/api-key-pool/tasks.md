# Implementation Plan: API Key Pool

## Overview

This plan implements a multi-key management layer for external AI providers with automatic failover, configurable selection strategies, usage tracking, cooldown recovery, and an admin dashboard. The implementation progresses from data layer → core service logic → API endpoints → client integration → admin portal UI.

## Tasks

- [x] 1. Database schema and domain models
  - [x] 1.1 Create Alembic migration for key pool tables
    - Create migration file adding `key_pool_configs`, `api_key_entries`, and `key_status_events` tables
    - Include all columns, constraints, indexes as specified in the design (CHECK constraints on priority 1–100, cooldown 10–3600, UNIQUE on provider+label)
    - Add indexes: `idx_key_entries_provider_status`, `idx_key_entries_provider_priority`, `idx_key_events_provider_created`, `idx_key_events_key_id`
    - _Requirements: 1.1, 1.6_

  - [x] 1.2 Add domain models and enumerations
    - Add `KeyStatus` and `SelectionStrategy` enums to `platform_api/models/enums.py`
    - Add `ApiKeyEntry`, `KeyPoolConfig`, and `KeyStatusEvent` dataclasses to `platform_api/models/domain.py`
    - _Requirements: 1.1, 2.1_

  - [x] 1.3 Add Pydantic request/response schemas
    - Add `AddKeyRequest`, `UpdateKeyRequest`, `KeyEntryResponse`, `ProviderConfigRequest`, `ProviderConfigResponse`, `ProviderHealthResponse`, `AllProvidersHealthResponse`, `KeyStatusEventResponse` to `platform_api/models/schemas.py`
    - Include all field validators (min_length, max_length, ge, le, pattern)
    - _Requirements: 1.2, 1.5, 6.1, 6.2, 7.1_

- [x] 2. Encryption and key pool repository
  - [x] 2.1 Implement KeyEncryption utility
    - Create `platform_api/services/key_encryption.py` with `KeyEncryption` class
    - Use `cryptography` library with Fernet + PBKDF2 key derivation from master key
    - Read master key from application settings (`Settings` class)
    - _Requirements: 1.6_

  - [ ]* 2.2 Write property test for encryption round-trip
    - **Property 1: Encryption round-trip preserves key value**
    - Test that for any valid key string (1–500 chars), encrypt→decrypt produces identical string and ciphertext does not contain plaintext as substring
    - **Validates: Requirements 1.6**

  - [x] 2.3 Implement KeyPoolRepository
    - Create `platform_api/repositories/key_pool_repo.py` implementing `KeyPoolRepositoryPort`
    - Implement: `list_by_provider`, `get_active_by_provider`, `get_by_id`, `create`, `update`, `delete`
    - Implement: `get_provider_config`, `upsert_provider_config`, `increment_counters`, `reset_daily_counters`, `get_usage_stats`, `get_recent_events`
    - Use raw asyncpg queries following existing repository patterns
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.1, 5.2, 5.3, 5.5_

  - [ ]* 2.4 Write property test for input validation
    - **Property 2: Input validation accepts valid entries and rejects invalid ones**
    - Test that valid key/label/priority are accepted with status=active, and invalid inputs are rejected
    - **Validates: Requirements 1.2, 1.5**

- [x] 3. Checkpoint - Ensure data layer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Key selection strategies
  - [x] 4.1 Implement key selection logic
    - Create `platform_api/services/key_pool_service.py` with `KeyPoolService` class implementing `KeyPoolServicePort`
    - Implement `get_key` method with round-robin and priority selection strategies
    - Round-robin: use Redis `key_pool:{provider}:rr_position` counter to track position, cycle through active keys
    - Priority: select lowest priority number, round-robin among tied priorities
    - Filter out non-active keys (rate_limited, exhausted, disabled) from selection
    - Raise `NoAvailableKeysError` when no active keys exist
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 3.3, 3.4_

  - [ ]* 4.2 Write property test for round-robin selection
    - **Property 5: Round-robin cycles deterministically through all active keys**
    - Test that N consecutive selections return each active key exactly once, and 2N repeats the sequence
    - **Validates: Requirements 2.2**

  - [ ]* 4.3 Write property test for priority selection
    - **Property 6: Priority selection returns lowest-priority-number key**
    - Test that selection always returns the active key with lowest priority number, with round-robin among ties
    - **Validates: Requirements 2.3**

  - [ ]* 4.4 Write property test for selection only returning active keys
    - **Property 9: Selection only returns active keys**
    - Test that selection never returns a key with status rate_limited, exhausted, or disabled
    - **Validates: Requirements 3.3**

  - [ ]* 4.5 Write property test for no-available-keys error
    - **Property 10: All non-active keys produces NoAvailableKeysError**
    - Test that when all keys are non-active, NoAvailableKeysError is raised with correct status counts
    - **Validates: Requirements 3.4**

  - [ ]* 4.6 Write property test for strategy change
    - **Property 7: Strategy change takes immediate effect**
    - Test that after changing strategy, next selection follows new strategy behavior
    - **Validates: Requirements 2.4**

- [x] 5. Failover and cooldown logic
  - [x] 5.1 Implement failover handler in KeyPoolService
    - Implement `execute_with_failover` method with max 3 retry attempts
    - On HTTP 429: mark key as `rate_limited`, record timestamp, retry with next key
    - On HTTP 402/403 (billing): mark key as `exhausted`, retry with next key
    - Exclude non-active keys from retry selection
    - Log failover events with failed key ID, failure reason, and replacement key ID
    - Implement `report_key_success` and `report_key_failure` methods
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 3.6_

  - [x] 5.2 Implement cooldown manager
    - Use Redis TTL keys (`key_pool:{provider}:cooldown:{key_id}`) for cooldown tracking
    - On rate_limited transition: set cooldown TTL using Retry-After header (capped at 3600) or provider's configured cooldown_seconds
    - On next selection: check if cooldown expired (key gone from Redis) → transition back to active
    - Exhausted keys never auto-recover
    - Configuration changes don't affect existing cooldowns
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 5.3 Write property test for failover status transitions
    - **Property 8: HTTP failure triggers correct status transition and failover**
    - Test that 429 → rate_limited, 402/403 → exhausted, and retry uses a different key
    - **Validates: Requirements 3.1, 3.2**

  - [ ]* 5.4 Write property test for failover retry bound
    - **Property 11: Failover retries are bounded at 3**
    - Test that total request attempts never exceed 3 regardless of pool size
    - **Validates: Requirements 3.5**

  - [ ]* 5.5 Write property test for cooldown duration
    - **Property 12: Cooldown duration uses Retry-After when present, capped at 3600**
    - Test that Retry-After value is used (capped at 3600), or configured default is used when absent
    - **Validates: Requirements 4.1, 4.5**

  - [ ]* 5.6 Write property test for cooldown recovery
    - **Property 13: Cooldown recovery restores active status**
    - Test that after cooldown elapses, key transitions back to active and becomes eligible for selection
    - **Validates: Requirements 4.2**

  - [ ]* 5.7 Write property test for config change not affecting existing cooldowns
    - **Property 14: Configuration change does not affect existing cooldowns**
    - Test that changing cooldown config doesn't alter remaining time for already-cooling keys
    - **Validates: Requirements 4.3**

  - [ ]* 5.8 Write property test for exhausted keys never auto-recovering
    - **Property 15: Exhausted keys never auto-recover**
    - Test that exhausted keys remain exhausted regardless of time elapsed
    - **Validates: Requirements 4.4**

- [x] 6. Checkpoint - Ensure core service tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Usage tracking and health indicators
  - [x] 7.1 Implement usage counter logic in KeyPoolService
    - Increment total_requests, daily_requests on each key use, update last_used_at
    - Categorize: success_count, failure_count (4xx/5xx), rate_limit_hits (429)
    - Store counters in both Redis (fast path) and PostgreSQL (durability)
    - Implement `reset_daily_counters` (midnight UTC reset via daily_requests = 0, preserve totals)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 7.2 Implement health indicator logic
    - Implement `get_pool_status` method returning health per provider
    - Health indicator: "healthy" when active ≥ T/2, "degraded" when 0 < active < T/2, "critical" when active = 0
    - _Requirements: 7.1_

  - [ ]* 7.3 Write property test for usage counter categorization
    - **Property 16: Usage counters are correctly categorized**
    - Test that for N requests with S successes, F failures, R rate-limits: counters match expected values
    - **Validates: Requirements 5.1, 5.2**

  - [ ]* 7.4 Write property test for daily counter reset
    - **Property 17: Daily counter reset preserves total counters**
    - Test that after reset, daily counters are zero but totals are unchanged
    - **Validates: Requirements 5.3**

  - [ ]* 7.5 Write property test for health indicator
    - **Property 18: Health indicator correctly reflects pool state**
    - Test healthy/degraded/critical thresholds based on active key ratio
    - **Validates: Requirements 7.1**

- [x] 8. Redis caching layer
  - [x] 8.1 Implement Redis cache for key pool
    - On startup/modification: populate `key_pool:{provider}:active` sorted set with active key IDs scored by priority
    - Maintain `key_pool:{provider}:rate_limited` set for quick filtering
    - Implement cache invalidation on key add/remove/status change (increment `key_pool:{provider}:version`)
    - Implement fallback to direct PostgreSQL queries when Redis is unavailable (log warning)
    - _Requirements: 8.4, 8.5_

- [x] 9. Admin API endpoints
  - [x] 9.1 Create key pool router
    - Create `platform_api/routers/key_pool.py` with all admin endpoints
    - `GET /api/v1/admin/key-pool/{provider}/keys` — list keys for provider
    - `POST /api/v1/admin/key-pool/{provider}/keys` — add key (validate, encrypt, store)
    - `PATCH /api/v1/admin/key-pool/keys/{key_id}` — update label/priority/value
    - `DELETE /api/v1/admin/key-pool/keys/{key_id}` — remove key
    - `POST /api/v1/admin/key-pool/keys/{key_id}/enable` — set status to active
    - `POST /api/v1/admin/key-pool/keys/{key_id}/disable` — set status to disabled
    - `GET /api/v1/admin/key-pool/{provider}/config` — get provider config
    - `PUT /api/v1/admin/key-pool/{provider}/config` — update strategy/cooldown
    - `GET /api/v1/admin/key-pool/{provider}/health` — provider health summary
    - `GET /api/v1/admin/key-pool/{provider}/events` — recent status events
    - `GET /api/v1/admin/key-pool/health` — all providers health
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 2.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 7.1, 7.3_

  - [x] 9.2 Register key pool router in app factory
    - Import and include `key_pool.router` in `platform_api/main.py` under the admin prefix
    - Wire dependencies for `KeyPoolService` and `KeyPoolRepository` in `wire_dependencies.py`
    - _Requirements: 8.2_

  - [x] 9.3 Add custom error classes
    - Add `NoAvailableKeysError` and `DuplicateKeyLabelError` to `platform_api/exceptions.py`
    - Ensure they integrate with the existing `PlatformAPIError` handler
    - _Requirements: 3.4, 1.5_

- [x] 10. Checkpoint - Ensure API endpoint tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Client wrapper and generation service integration
  - [x] 11.1 Implement KeyPoolClientWrapper
    - Create `platform_api/clients/key_pool_client_wrapper.py`
    - Wraps existing client protocol methods to inject key from pool and handle failover
    - Each provider client (Suno, Fal, LLM, Slai) gets a wrapper instance
    - _Requirements: 8.1, 8.2_

  - [x] 11.2 Integrate key pool with GenerationService
    - Modify `GenerationService.__init__` to accept optional `KeyPoolService` dependency
    - Wrap client calls through `KeyPoolClientWrapper.execute()` when pool is available
    - Implement backward compatibility: fall back to system_settings key when pool has zero entries for a provider
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ]* 11.3 Write property test for empty pool fallback
    - **Property 19: Empty pool falls back to system_settings key**
    - Test that zero-entry pools use system_settings, and pools with entries use the pool
    - **Validates: Requirements 8.3**

  - [ ]* 11.4 Write property test for key removal excluding from selection
    - **Property 3: Key removal excludes key from selection pool**
    - Test that removing a key results in N−1 keys and the removed key is never selected
    - **Validates: Requirements 1.3**

  - [ ]* 11.5 Write property test for priority update affecting selection
    - **Property 4: Priority update affects subsequent selection order**
    - Test that updating a key to lowest priority number causes it to be selected next
    - **Validates: Requirements 1.4**

- [x] 12. Checkpoint - Ensure integration tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Admin portal - Types and API hooks
  - [x] 13.1 Create TypeScript type definitions
    - Create `admin_portal/src/types/key-pool.ts`
    - Define interfaces: `ApiKeyEntry`, `ProviderConfig`, `ProviderHealth`, `KeyStatusEvent`, `AddKeyRequest`, `UpdateKeyRequest`
    - _Requirements: 6.1, 7.1_

  - [x] 13.2 Create React Query hooks
    - Create `admin_portal/src/hooks/use-key-pool.ts`
    - Hooks: `useProviderKeys`, `useProviderConfig`, `useProviderHealth`, `useAllProvidersHealth`, `useProviderEvents`
    - Mutations: `useAddKey`, `useUpdateKey`, `useDeleteKey`, `useEnableKey`, `useDisableKey`, `useUpdateProviderConfig`
    - Configure automatic refetch intervals (5 seconds for health data per Req 7.2)
    - _Requirements: 6.1, 7.2_

- [x] 14. Admin portal - Key pool management page
  - [x] 14.1 Create key pool page with provider tabs
    - Create `admin_portal/src/pages/key-pool/index.tsx`
    - Tabbed layout organized by provider (Suno, FAL, OpenAI, Slai, YouTube, Facebook)
    - Display all keys per provider with: label, masked key value (first 4 + last 4 chars), status badge, priority, daily requests, last used timestamp
    - _Requirements: 6.1_

  - [x] 14.2 Create provider tab component
    - Create `admin_portal/src/components/key-pool/provider-tab.tsx`
    - Render key list with `key-entry-row` components
    - Include "Add Key" button and provider settings panel
    - _Requirements: 6.1, 6.7_

  - [x] 14.3 Create key entry row component
    - Create `admin_portal/src/components/key-pool/key-entry-row.tsx`
    - Display key info with action buttons: enable/disable toggle, edit, delete
    - Inline status badge with color coding (active=green, rate_limited=yellow, exhausted=red, disabled=gray)
    - _Requirements: 6.1, 6.3, 6.4, 6.5, 6.6_

  - [x] 14.4 Create add/edit key dialogs
    - Create `admin_portal/src/components/key-pool/add-key-dialog.tsx` — form with key_value, label, priority fields + validation
    - Create `admin_portal/src/components/key-pool/edit-key-dialog.tsx` — inline edit form for label/priority
    - Confirmation dialog before deletion with key label and provider name
    - _Requirements: 6.2, 6.5, 6.6_

  - [x] 14.5 Create provider settings panel
    - Create `admin_portal/src/components/key-pool/provider-settings.tsx`
    - Configure selection strategy (round_robin/priority dropdown) and cooldown period (number input 10–3600)
    - Submit changes to API and reflect updates without full page reload
    - _Requirements: 6.7_

- [x] 15. Admin portal - Health dashboard
  - [x] 15.1 Create health summary component
    - Create `admin_portal/src/components/key-pool/health-summary.tsx`
    - Per-provider summary: total/active/rate_limited/exhausted/disabled counts + health indicator badge
    - Critical state alert banner when no active keys for any provider
    - Auto-refresh every 5 seconds via React Query refetch interval
    - _Requirements: 7.1, 7.2, 7.5_

  - [x] 15.2 Create event log component
    - Create `admin_portal/src/components/key-pool/event-log.tsx`
    - Display last 50 status transitions per provider: timestamp, key label, previous→new status, trigger reason
    - Timeline/table layout with color-coded status badges
    - _Requirements: 7.3_

  - [x] 15.3 Create key detail hover/expand view
    - Add expandable detail section to `key-entry-row.tsx`
    - Show: total requests, daily requests, success rate %, time since last used, cooldown remaining (if rate_limited)
    - _Requirements: 7.4_

- [x] 16. Checkpoint - Ensure frontend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Final integration and wiring
  - [x] 17.1 Wire KeyPoolService into application lifespan
    - Initialize `KeyPoolService` during app startup in `_lifespan`
    - Load active keys into Redis cache on startup
    - Configure `KeyEncryption` with master key from settings
    - _Requirements: 8.4_

  - [x] 17.2 Add ENCRYPTION_MASTER_KEY to Settings
    - Add `encryption_master_key: str` field to `platform_api/config.py` Settings class
    - Document as required environment variable
    - _Requirements: 1.6_

  - [ ]* 17.3 Write frontend component tests
    - Test page rendering with mocked provider data (MSW handlers)
    - Test add/edit/delete form interactions
    - Test confirmation dialog behavior
    - Test health indicator badge rendering
    - Test critical state alert banner
    - _Requirements: 6.1, 6.2, 6.5, 7.1, 7.5_

- [x] 18. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation uses Python (Hypothesis) for backend property tests and TypeScript (fast-check) for frontend property tests
- All API keys are encrypted at rest — the `ENCRYPTION_MASTER_KEY` environment variable must be set before first use
- Redis is used for low-latency key selection but the system gracefully degrades to direct DB queries if Redis is unavailable

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "2.3", "9.3"] },
    { "id": 2, "tasks": ["2.2", "2.4", "4.1"] },
    { "id": 3, "tasks": ["4.2", "4.3", "4.4", "4.5", "4.6", "5.1", "5.2"] },
    { "id": 4, "tasks": ["5.3", "5.4", "5.5", "5.6", "5.7", "5.8", "7.1", "7.2"] },
    { "id": 5, "tasks": ["7.3", "7.4", "7.5", "8.1"] },
    { "id": 6, "tasks": ["9.1", "9.2", "13.1"] },
    { "id": 7, "tasks": ["11.1", "13.2"] },
    { "id": 8, "tasks": ["11.2", "14.1", "14.2"] },
    { "id": 9, "tasks": ["11.3", "11.4", "11.5", "14.3", "14.4", "14.5"] },
    { "id": 10, "tasks": ["15.1", "15.2", "15.3"] },
    { "id": 11, "tasks": ["17.1", "17.2", "17.3"] }
  ]
}
```
