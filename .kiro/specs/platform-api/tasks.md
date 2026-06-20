# Implementation Plan: Platform API

## Overview

This plan implements a Python FastAPI backend service that centralizes authentication, AI service proxying, credit management, license management, and real-time notifications. The implementation follows a layered architecture (transport → application → domain → infrastructure) with Protocol-based dependency injection. Tasks are ordered to establish foundations first (project structure, models, database), then build core services (auth, credits, licenses), followed by generation proxying and real-time features, ending with integration wiring.

## Tasks

- [x] 1. Project structure, configuration, and core models
  - [x] 1.1 Create project scaffolding and FastAPI app factory
    - Create `platform_api/` directory structure matching the design (main.py, config.py, dependencies.py, middleware/, routers/, services/, repositories/, models/, clients/, ports/, migrations/)
    - Implement `main.py` with FastAPI app factory, CORS middleware, global exception handler, and router registration
    - Implement `config.py` with Pydantic Settings loading from environment variables (database URL, Redis URL, JWT secret, token expiration times, external API keys)
    - Add `pyproject.toml` or `requirements.txt` with dependencies: fastapi, uvicorn, asyncpg, sqlalchemy, alembic, pyjwt, passlib[bcrypt], redis, httpx, pydantic[email], hypothesis (dev)
    - _Requirements: 18.1_

  - [x] 1.2 Define domain models, enumerations, and Pydantic schemas
    - Create `models/enums.py` with UserRole, UserStatus, LicenseStatus, PlanType, TaskStatus, ImageKind, ChannelRole, TransactionDirection enumerations
    - Create `models/domain.py` with dataclasses for User, License, Plan, CreditWallet, CreditTransaction, ChannelProfile, Song, SunoTask, ImageJob, Batch, AuditLog, MusicDescription, MusicStructure
    - Create `models/schemas.py` with Pydantic request/response models: LoginRequest, TokenResponse, RegisterRequest, SunoGenerationRequest, ImageGenerationRequest, DraftGenerationRequest, BatchCreateRequest, WalletBalanceResponse, BatchStatusResponse, ErrorResponse
    - _Requirements: 1.1, 2.1, 2.3, 4.1, 6.1, 8.2, 11.1, 12.1, 13.1_

  - [x] 1.3 Create database migrations with Alembic
    - Initialize Alembic configuration pointing to the PostgreSQL connection
    - Create initial migration with all tables from the design: users, refresh_tokens, plans, plan_offers, licenses, credit_wallets, credit_packs, credit_pricing, credit_transactions, channel_profiles, music_descriptions, music_structures, batches, songs, suno_tasks, image_jobs, user_settings, system_settings, audit_logs, rate_limit_config, notification_queue, plan_usage
    - Include all indexes, constraints, and CHECK constraints from the schema design
    - _Requirements: 4.1, 6.1, 6.4, 8.2, 20.3_

  - [x] 1.4 Implement Protocol interfaces (ports)
    - Create `ports/auth_port.py` with AuthServicePort Protocol (authenticate, refresh_token, validate_token, revoke_tokens)
    - Create `ports/credit_port.py` with CreditServicePort Protocol (get_balance, deduct, refund, purchase_pack)
    - Create `ports/generation_port.py` with GenerationServicePort Protocol (submit_suno, submit_image, submit_draft)
    - Create `ports/notification_port.py` with NotificationServicePort Protocol (push, queue)
    - _Requirements: 1.1, 7.1, 11.1, 17.1_

  - [x] 1.5 Implement exception hierarchy and global error handler
    - Create `platform_api/exceptions.py` with PlatformAPIError base class and subclasses: AuthenticationError, AccountLockedError, InsufficientCreditsError, QuotaExceededError, ExternalServiceError, ValidationError, DuplicateError, NotFoundError
    - Register global exception handler in main.py that formats errors per the design's JSON error structure
    - Include audit logging hook for 401/403 security failures
    - _Requirements: 1.2, 1.7, 7.4, 11.7, 12.5, 16.3, 16.4, 16.5, 16.6_

- [x] 2. Authentication and authorization
  - [x] 2.1 Implement auth service with JWT token management
    - Create `services/auth_service.py` implementing AuthServicePort
    - Implement login: validate credentials, issue access token (30 min) and refresh token (7 days) using PyJWT
    - Implement refresh: validate refresh token, issue new token pair, rotate refresh token
    - Implement logout: revoke refresh token by adding to Redis blocklist
    - Implement password hashing with bcrypt work factor 12 (passlib)
    - _Requirements: 1.1, 1.3, 1.4, 1.5_

  - [x] 2.2 Implement account lockout mechanism
    - Add lockout logic in auth_service using Redis: track failed attempts per email, lock after 5 consecutive failures for 15 minutes
    - Implement `check_lockout` and `record_failed_attempt` functions per the design algorithm
    - Reset failure counter on successful login
    - _Requirements: 1.7_

  - [x]* 2.3 Write property tests for auth (Properties 1-4)
    - **Property 1: Password hashing round-trip with bcrypt work factor**
    - **Property 2: Account lockout threshold**
    - **Property 3: Password validation rules**
    - **Property 4: Registration validation completeness**
    - **Validates: Requirements 1.5, 1.7, 2.3, 2.4**

  - [x] 2.4 Implement auth middleware and authorization chain
    - Create `middleware/auth.py` with JWT validation dependency (FastAPI Depends)
    - Implement the authorization chain per design: token validity (401) → account suspension (403) → license status (403) → credit balance (402)
    - Create role-based access decorators for User and Admin enforcement
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7_

  - [x] 2.5 Implement auth router endpoints
    - Create `routers/auth.py` with POST /login, POST /register, POST /refresh, POST /logout
    - Wire to auth_service via FastAPI dependency injection
    - Implement registration with password validation (8-128 chars, uppercase, lowercase, digit), email uniqueness check, display name validation (2-50 chars)
    - Return all validation errors (not just first) per Property 4
    - _Requirements: 1.1, 1.2, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x]* 2.6 Write property test for authorization check ordering (Property 30)
    - **Property 30: Authorization check ordering**
    - **Validates: Requirements 16.7**

- [x] 3. Checkpoint - Verify auth layer
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. User management (Admin)
  - [x] 4.1 Implement user repository and service
    - Create `repositories/user_repo.py` with CRUD operations, paginated listing with filters (status, plan type, date range), soft-delete
    - Create `services/user_service.py` with get_users (paginated, max page size 100, default 25), update_user, suspend_user (revoke tokens, record reason), reactivate_user, delete_user (soft-delete, revoke licenses)
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 4.2 Implement users router
    - Create `routers/users.py` with GET /users/me, PATCH /users/me, GET /users (Admin), PATCH /users/{id} (Admin), POST /users/{id}/suspend (Admin), POST /users/{id}/reactivate (Admin), DELETE /users/{id} (Admin)
    - Enforce Admin role via dependency; return 403 for non-Admin on admin endpoints, 404 for non-existent users
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x]* 4.3 Write property test for paginated list invariants (Property 5)
    - **Property 5: Paginated list invariants**
    - **Validates: Requirements 3.1, 20.2**

- [x] 5. License and plan management
  - [x] 5.1 Implement license and plan repositories
    - Create `repositories/license_repo.py` with CRUD for licenses, license key generation, assignment, revocation, status queries, active license lookup, plan usage tracking
    - Create plan seeding logic for default plans (Monthly $79/30-day, Yearly $699/365-day, Lifetime $1499 one-time) as configurable database records
    - _Requirements: 4.1, 4.3, 4.4_

  - [x] 5.2 Implement license service
    - Create `services/license_service.py` with create_license, assign_license (check no duplicate plan type), revoke_license (recalculate profile allowance), validate_license
    - Implement daily song limit per channel (default 7/day) and monthly quota enforcement
    - Implement plan offer logic: promotional pricing with max redemption count, auto-revert to standard price
    - Implement plan deactivation: prevent new license creation when is_active=false, existing licenses unaffected
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12_

  - [x] 5.3 Implement licenses and plans routers
    - Create `routers/licenses.py` with POST /licenses (Admin), POST /licenses/{id}/assign (Admin), POST /licenses/{id}/revoke (Admin), GET /licenses/validate (User)
    - Create `routers/plans.py` with GET /plans (Admin), PATCH /plans/{id} (Admin), GET/POST /plans/offers (Admin)
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.10, 4.12_

  - [x]* 5.4 Write property test for daily quota enforcement (Property 33)
    - **Property 33: Daily quota enforcement per channel**
    - **Validates: Requirements 4.6**

- [x] 6. Credit system
  - [x] 6.1 Implement credit repository and wallet logic
    - Create `repositories/credit_repo.py` with atomic deduction using `UPDATE ... WHERE balance >= amount RETURNING balance` pattern, refund, get_balance, transaction recording
    - Implement wallet balance bounds enforcement: non-negative, max 10,000,000
    - Implement transaction history with pagination (default 50 recent, paginated older)
    - _Requirements: 6.3, 6.4, 6.5, 6.7, 6.8, 6.10_

  - [x] 6.2 Implement credit service with quota consumption order
    - Create `services/credit_service.py` implementing CreditServicePort
    - Implement quota consumption order: Monthly/Yearly users consume plan quota first, then wallet; Lifetime users always use wallet
    - Implement purchase_pack: validate payment, add credits, record transaction, check overflow
    - Implement manual admin adjustment with bounds checking
    - Implement lifetime bonus: credit 1,000 songs on lifetime activation
    - _Requirements: 6.1, 6.2, 6.3, 6.6, 6.7, 6.10, 6.11, 6.12, 6.13_

  - [x] 6.3 Implement credit pricing service and router
    - Create credit pricing CRUD: configure per-model pricing (model_identifier + operation_type unique), validate credits_per_operation in [1, 10000], store external cost, compute margin
    - Create `routers/credits.py` with GET /credits/balance, GET /credits/packs, POST /credits/purchase, GET /credits/pricing (Admin), POST/PUT /credits/pricing (Admin), POST /credits/adjust (Admin)
    - Reject generation requests for unconfigured model operations
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x]* 6.4 Write property tests for credits (Properties 6-10)
    - **Property 6: Credit pricing validation and margin calculation**
    - **Property 7: Atomic credit deduction never overdraws**
    - **Property 8: Credit refund restores exact amount**
    - **Property 9: Plan quota consumed before wallet**
    - **Property 10: Wallet balance invariant (non-negative, bounded)**
    - **Validates: Requirements 5.1, 5.4, 5.5, 7.1-7.4, 7.6, 6.4, 6.7, 6.10, 6.12**

  - [x]* 6.5 Write property test for batch cost pre-check (Property 24)
    - **Property 24: Batch cost pre-check**
    - **Validates: Requirements 13.6**

- [x] 7. Checkpoint - Verify core services
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Channel profile management
  - [x] 8.1 Implement profile repository and service
    - Create `repositories/profile_repo.py` with CRUD, count by user, uniqueness enforcement (user_id + name)
    - Create `services/profile_service.py` with create (enforce plan limit), update, delete (dissociate from active assignments), list (ordered by name ascending)
    - Implement profile limit enforcement based on plan type: Lifetime=5, Monthly=3, expandable to max 20
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 8.2 Implement profiles router
    - Create `routers/profiles.py` with GET /profiles, POST /profiles, PUT /profiles/{id}, DELETE /profiles/{id} (User), GET /profiles/{id}/stats (Admin)
    - Include admin stats endpoint aggregating batches, songs, and credits consumed
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_

  - [x]* 8.3 Write property tests for profiles (Properties 11-13)
    - **Property 11: Channel profile count enforcement**
    - **Property 12: Channel profile name uniqueness per user**
    - **Property 13: Profile list ordering**
    - **Validates: Requirements 8.1, 8.2, 8.4, 8.7**

- [x] 9. Music prompt management (Admin)
  - [x] 9.1 Implement prompt repository and service
    - Create `repositories/prompt_repo.py` with CRUD for music_descriptions and music_structures, matchKey-based pairing lookup
    - Create `services/prompt_service.py` with create/update/delete for descriptions and structures, matchKey pairing logic, cycle/shuffle structure assignment
    - Implement seeded random shuffle per Batch for structure ordering
    - _Requirements: 9.1, 9.2, 9.3, 9.6, 9.7_

  - [x] 9.2 Implement prompts router
    - Create `routers/prompts.py` with GET/POST /prompts/descriptions, PUT/DELETE /prompts/descriptions/{id}, GET/POST /prompts/structures, PUT/DELETE /prompts/structures/{id} (all Admin-only)
    - _Requirements: 9.1, 9.2, 9.3_

  - [x]* 9.3 Write property tests for prompts (Properties 14-17)
    - **Property 14: Music prompt validation (descriptions and structures)**
    - **Property 15: Song data visibility scoping**
    - **Property 16: matchKey pairing correctness**
    - **Property 17: Cyclic structure assignment**
    - **Validates: Requirements 9.1, 9.2, 9.5, 9.6, 9.7**

- [x] 10. Generation services (LLM, Suno, Image proxying)
  - [x] 10.1 Implement external HTTP clients
    - Create `clients/suno_client.py` with async httpx client for Suno API (submit task, check status, get credit balance)
    - Create `clients/fal_client.py` with async httpx client for Fal AI image generation
    - Create `clients/slai_client.py` with async httpx client for SLAI image generation
    - Create `clients/llm_client.py` with async httpx client for DeepSeek/SLAI LLM (song draft generation)
    - Implement timeout handling (30s for Suno/LLM, 60s for image) and error classification (retryable vs permanent)
    - _Requirements: 10.1, 11.1, 11.7, 12.1, 12.5_

  - [x] 10.2 Implement generation service (draft, Suno, image orchestration)
    - Create `services/generation_service.py` implementing GenerationServicePort
    - Implement submit_draft: call LLM, validate lyrics structure (headers order, content lines ≥ max(16, headers×4)), retry up to 8 attempts, enforce avoid list uniqueness (retry up to 6 attempts for title/album), handle forced values
    - Implement submit_suno: compute SHA-256 request hash for dedup, check for existing task, atomic credit deduction, forward to Suno, create Suno_Task record, refund on delivery failure
    - Implement submit_image: validate request (resolution 512-2048, style_strength 0-1, prompt 1-2000 chars, base64 ≤10MB), atomic credit deduction, forward to provider, return PNG bytes, refund on failure
    - _Requirements: 10.1, 10.3, 10.4, 10.5, 10.6, 10.7, 11.1, 11.5, 11.7, 12.1, 12.2, 12.5, 12.6, 7.1, 7.2, 7.3, 7.6_

  - [x] 10.3 Implement generation and callbacks routers
    - Create `routers/generation.py` with POST /generation/draft, POST /generation/suno, GET /generation/suno/{taskId}, POST /generation/image (all User auth)
    - Create `routers/callbacks.py` with POST /callbacks/suno (HMAC/IP validation, no JWT)
    - Implement callback processing: update Suno_Task status, store audio URLs, trigger WebSocket notification
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.6, 11.8, 12.1, 12.2, 12.3_

  - [x]* 10.4 Write property tests for generation (Properties 18-23)
    - **Property 18: Song structure validation**
    - **Property 19: Title/album avoid list enforcement**
    - **Property 20: Forced values override**
    - **Property 21: Suno request hash determinism and collision resistance**
    - **Property 22: Error classification (retryable vs permanent)**
    - **Property 23: Image request validation ranges**
    - **Validates: Requirements 10.3, 10.4, 10.6, 11.5, 11.7, 12.5, 12.6**

- [x] 11. Batch generation orchestration
  - [x] 11.1 Implement batch service
    - Create `repositories/batch_repo.py` with batch CRUD, song record management, status aggregation queries
    - Create `services/batch_service.py` with create_batch (pre-check total cost: LLM + Suno credits × song_count), orchestrate draft generation, track per-song status, handle partial failures (mark failed drafts, continue with successful ones)
    - Implement image job creation when Suno_Task completes based on profile image config (bg_thumb, thumb_only, bg_only)
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8_

  - [x] 11.2 Implement batch router
    - Create `routers/batch.py` or extend generation router with POST /batches, GET /batches/{id}
    - Return batch status with all counters: total_songs, drafts_completed, drafts_failed, suno_submitted, suno_completed, suno_failed, audio_downloaded, images_completed
    - _Requirements: 13.1, 13.5_

- [x] 12. Checkpoint - Verify generation pipeline
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Application settings
  - [x] 13.1 Implement settings repository and service
    - Create `repositories/settings_repo.py` with key-value CRUD supporting types: string (≤10000 chars), integer, float, boolean, JSON (≤64KB)
    - Create `services/settings_service.py` with get_merged_settings (user values override system defaults), patch_settings (1-50 key-value pairs, atomic: reject entire patch if any value invalid), sensitive key filtering
    - Implement settings key limit (255 chars) and value type validation
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

  - [x] 13.2 Implement settings router
    - Create `routers/settings_router.py` with GET /settings (User), PATCH /settings (User)
    - Return merged settings within 2 seconds, exclude sensitive keys
    - _Requirements: 14.1, 14.2, 14.4_

  - [x]* 13.3 Write property tests for settings (Properties 25-28)
    - **Property 25: Settings merge precedence**
    - **Property 26: Settings patch idempotence**
    - **Property 27: Settings value round-trip**
    - **Property 28: Sensitive settings exclusion**
    - **Validates: Requirements 14.1, 14.2, 14.3, 14.4**

- [x] 14. WebSocket notifications
  - [x] 14.1 Implement notification service and WebSocket manager
    - Create `services/notification_service.py` implementing NotificationServicePort with push (to connected clients) and queue (for offline users)
    - Create `routers/ws.py` with WebSocket endpoint /ws requiring valid access token in handshake, max 3 concurrent connections per user
    - Implement connection lifecycle: authenticate on connect, manage per-user connection registry, ping/pong (60s idle → ping, 10s timeout → close)
    - Implement notification queue: store undelivered notifications in notification_queue table, deliver on reconnect (chronological order), expire after 24 hours
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

  - [x]* 14.2 Write unit tests for WebSocket notification delivery
    - Test connection authentication, notification push on Suno/Image completion, queue drain on reconnect, ping/pong timeout handling
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

- [x] 15. Rate limiting and external balance monitoring
  - [x] 15.1 Implement rate limiting middleware
    - Create `middleware/rate_limit.py` with sliding window rate limiting using Redis sorted sets per the design algorithm
    - Enforce per-user, per-endpoint-type limits (configurable, default 60/min); Suno-specific 20 requests per 10s window
    - Return 429 with Retry-After header; do NOT deduct credits for rejected requests
    - Support Admin live-update of rate limit config (apply within 5 seconds)
    - _Requirements: 19.1, 19.2, 19.3, 19.4_

  - [x] 15.2 Implement external Suno balance monitoring
    - Add to `services/generation_service.py` or new admin service: query Suno API credit endpoint, cache in Redis (30s TTL)
    - Implement reserve threshold check (default 100 credits): reject new Suno requests if below threshold, push low-balance alert to Admin WebSocket clients
    - Handle unreachable Suno endpoint: serve cached value or report "unknown" without blocking requests
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

  - [x]* 15.3 Write property test for rate limit enforcement (Property 31)
    - **Property 31: Rate limit enforcement**
    - **Validates: Requirements 19.1, 19.2, 19.3**

- [x] 16. Audit logging
  - [x] 16.1 Implement audit service and repository
    - Create `repositories/audit_repo.py` with append-only insert, paginated filtered queries (actor, action_type, resource_type, date range; default 50, max 200 per page)
    - Create `services/audit_service.py` with log_event (actor_id, action_type, target_resource, timestamp UTC ISO 8601, credit_impact, outcome, source_ip, client_id, endpoint_path, metadata)
    - Create `middleware/audit.py` to intercept state-changing requests and auto-log
    - No update/delete operations on audit log entries
    - _Requirements: 20.1, 20.2, 20.3, 20.4_

  - [x] 16.2 Implement admin router for audit and rate limits
    - Create `routers/admin.py` with GET /admin/suno-balance (Admin), GET /admin/audit-log (Admin with filters), GET/PUT /admin/rate-limits (Admin)
    - Return first page of audit results within 2 seconds
    - _Requirements: 15.1, 19.4, 20.2_

  - [x]* 16.3 Write property test for audit log (Property 32)
    - **Property 32: Audit log completeness and immutability**
    - **Validates: Requirements 20.1, 20.4**

- [x] 17. Health check endpoint
  - [x] 17.1 Implement health check router
    - Create `routers/health.py` with GET /health (no auth required)
    - Check database connectivity, Suno API reachability, Fal AI reachability, SLAI reachability (3s timeout per service)
    - Return status (healthy/degraded/unhealthy), database connectivity status, uptime seconds, UTC ISO 8601 timestamp
    - Respond within 500ms
    - _Requirements: 18.1, 18.2, 18.3_

- [x] 18. Data isolation and scoping
  - [x] 18.1 Implement user-scoped data isolation
    - Add user-scoping to all repository queries for User-role requests: profiles, songs, batches, tasks, settings only return records belonging to the authenticated user
    - Admin-role requests bypass scoping
    - _Requirements: 16.1, 16.2_

  - [x]* 18.2 Write property test for user-scoped data isolation (Property 29)
    - **Property 29: User-scoped data isolation**
    - **Validates: Requirements 16.2**

- [x] 19. Integration wiring and dependency injection
  - [x] 19.1 Wire all dependencies and complete FastAPI app
    - Create `dependencies.py` with FastAPI dependency injection setup: database pool (asyncpg), Redis connection, all repositories, all services, all clients
    - Register all routers in main.py with /api/v1 prefix
    - Wire middleware stack: rate limiting → auth → audit
    - Ensure all Protocol implementations are properly injected
    - _Requirements: All_

  - [x]* 19.2 Write integration tests for full generation pipeline
    - Test complete flow: register → login → create profile → submit batch → draft generation → Suno submission → callback → image generation → WebSocket notification
    - Mock external services (Suno, Fal AI, SLAI, DeepSeek) with httpx mock
    - Test concurrent credit operations
    - Test rate limiting under load
    - _Requirements: All_

- [x] 20. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at major integration boundaries
- Property tests validate universal correctness properties defined in the design (33 properties total across 8 domains)
- Unit tests validate specific examples and edge cases
- External services (Suno, Fal AI, SLAI, DeepSeek) are mocked in tests using httpx mock clients
- The project uses Python 3.11+ with FastAPI, asyncpg, Redis, and Hypothesis for property testing
- All database operations use async/await with connection pooling
- Protocol-based dependency injection matches the existing project's `features/ports.py` pattern

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "1.5"] },
    { "id": 2, "tasks": ["2.1", "2.2"] },
    { "id": 3, "tasks": ["2.3", "2.4", "2.5"] },
    { "id": 4, "tasks": ["2.6", "4.1"] },
    { "id": 5, "tasks": ["4.2", "4.3", "5.1"] },
    { "id": 6, "tasks": ["5.2", "5.3"] },
    { "id": 7, "tasks": ["5.4", "6.1"] },
    { "id": 8, "tasks": ["6.2", "6.3"] },
    { "id": 9, "tasks": ["6.4", "6.5", "8.1"] },
    { "id": 10, "tasks": ["8.2", "8.3", "9.1"] },
    { "id": 11, "tasks": ["9.2", "9.3", "10.1"] },
    { "id": 12, "tasks": ["10.2"] },
    { "id": 13, "tasks": ["10.3", "10.4", "11.1"] },
    { "id": 14, "tasks": ["11.2", "13.1"] },
    { "id": 15, "tasks": ["13.2", "13.3", "14.1"] },
    { "id": 16, "tasks": ["14.2", "15.1", "15.2"] },
    { "id": 17, "tasks": ["15.3", "16.1"] },
    { "id": 18, "tasks": ["16.2", "16.3", "17.1"] },
    { "id": 19, "tasks": ["18.1"] },
    { "id": 20, "tasks": ["18.2", "19.1"] },
    { "id": 21, "tasks": ["19.2"] }
  ]
}
```
