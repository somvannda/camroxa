# Implementation Plan: Admin User Data Reset

## Overview

This implementation plan covers the admin-facing user data reset feature spanning the Platform API (FastAPI backend) and Admin Portal (React SPA). The plan follows a backend-first approach: domain models and error hierarchy, then repository layer, then service layer, then API endpoints, and finally the frontend components and hooks wired together.

## Tasks

- [x] 1. Set up domain models and error hierarchy
  - [x] 1.1 Create Pydantic request/response schemas and domain dataclasses
    - Create `platform_api/models/reset_models.py` with `ResetRequest`, `RestoreRequest`, `ResetResponse`, `RestoreResponse`, `BackupMetadataResponse`, `BackupListResponse` Pydantic models
    - Create `BackupMetadata`, `ResetResult`, `RestoreResult` frozen dataclasses
    - Define `DELETION_ORDER` constant list and `REDIS_FLUSH_PATTERNS` constant list
    - _Requirements: 2.2, 2.3, 2.4, 3.1, 3.7_

  - [x] 1.2 Create error hierarchy for reset operations
    - Add `ResetError`, `BackupCreationError`, `ResetExecutionError`, `RestoreExecutionError`, `RateLimitExceededError` to `platform_api/exceptions.py` (or a new `platform_api/models/reset_errors.py`)
    - Register exception handlers in the FastAPI app for the new error types mapping to correct HTTP status codes (500, 429, etc.)
    - _Requirements: 2.5, 3.8, 3.9, 5.5, 1.6_

- [x] 2. Implement password verification and rate limiting
  - [x] 2.1 Implement PasswordAttemptLimiter class
    - Create `platform_api/services/password_limiter.py` with `PasswordAttemptLimiter` class
    - Use Redis key prefix `reset_pwd_attempts:`, max 5 attempts, 15-minute lockout
    - Implement `check_and_increment(admin_id)` and `reset(admin_id)` methods
    - _Requirements: 1.6_

  - [x] 2.2 Implement verify_admin_password helper
    - Create `platform_api/services/admin_password.py` (or add to existing auth utils)
    - Implement `verify_admin_password(admin_id, password, pool, redis)` that checks bcrypt hash and integrates with `PasswordAttemptLimiter`
    - Raise `AuthenticationError` on wrong password (401), `RateLimitExceededError` on lockout (429)
    - _Requirements: 1.1, 1.2, 1.3, 1.6_

  - [ ]* 2.3 Write property test for rate limiting behavior
    - **Property 9: Authorization enforcement**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    - Test that after 5 failed attempts, subsequent calls raise `RateLimitExceededError`
    - Test that successful verification resets the counter

  - [ ]* 2.4 Write unit tests for password verification
    - Test correct password proceeds without error
    - Test wrong password raises AuthenticationError (401)
    - Test 5 failures then 6th attempt raises RateLimitExceededError (429)
    - Test counter reset on success
    - _Requirements: 1.1, 1.2, 1.6_

- [x] 3. Implement ResetRepository
  - [x] 3.1 Create ResetRepository with fetch and delete methods
    - Create `platform_api/repositories/reset_repo.py`
    - Implement `fetch_all_user_data(exclude_admin_email)` returning dict of table_name → list[dict]
    - Implement `delete_user_data_in_transaction(conn, exclude_admin_email)` deleting in FK order from `DELETION_ORDER`
    - Implement `reset_counters_in_transaction(conn)` setting `redeem_codes.current_redemptions` and `invitation_codes.current_uses` to 0
    - Implement `restore_data_in_transaction(conn, data)` inserting records with ON CONFLICT DO NOTHING
    - _Requirements: 2.2, 3.1, 3.2, 3.3, 3.4, 3.5, 5.3_

  - [ ]* 3.2 Write property tests for ResetRepository
    - **Property 3: Admin account preservation** — after delete, admin row remains unchanged
    - **Property 4: System configuration preservation** — system config rows remain unchanged
    - **Property 5: Counter reset to zero** — all counters become 0 after reset
    - **Validates: Requirements 3.2, 3.3, 3.4, 3.5**

- [x] 4. Implement ResetService
  - [x] 4.1 Create ResetService with backup and reset orchestration
    - Create `platform_api/services/reset_service.py`
    - Implement `create_backup(admin_id)` — fetch all user data, write JSON to backup_dir with timestamped filename
    - Implement `execute_reset(admin_id)` — create backup first, then open transaction (120s timeout), delete in FK order, reset counters, commit, flush Redis, write audit log
    - Handle partial success: if Redis flush fails after DB commit, return result with `redis_flushed=False`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.6, 3.7, 3.8, 3.9, 3.10_

  - [x] 4.2 Implement restore and list_backups in ResetService
    - Implement `execute_restore(backup_filename, admin_id)` — read backup JSON, open transaction (120s timeout), insert with ON CONFLICT DO NOTHING, commit, write audit log
    - Implement `list_backups()` — scan backup_dir, parse metadata from each file, sort newest-first, cap at 100
    - Raise `FileNotFoundError` if backup doesn't exist, `RestoreExecutionError` on insert failure
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ]* 4.3 Write property tests for ResetService
    - **Property 1: Backup completeness** — generate random user data → backup → verify all records present
    - **Property 2: Backup metadata and filename correctness** — verify filename pattern and metadata accuracy
    - **Property 6: Audit log per-table accuracy** — verify per-table counts match actual deletions
    - **Property 7: Backup listing sorted and bounded** — verify sorted descending, max 100
    - **Property 8: Restore inserts non-conflicting records** — verify union semantics
    - **Validates: Requirements 2.2, 2.3, 2.4, 3.10, 4.1, 4.2, 5.3**

- [x] 5. Checkpoint - Backend core logic
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement admin router endpoints
  - [x] 6.1 Add user-data reset, backup-list, and restore endpoints to admin router
    - Extend `platform_api/routers/admin.py` with three new endpoints:
      - `POST /admin/user-data/reset` — verify password, call `execute_reset`
      - `GET /admin/user-data/backups` — call `list_backups`
      - `POST /admin/user-data/restore` — verify password, call `execute_restore`
    - Apply `require_admin` dependency for JWT + role check on all three
    - Wire `ResetService` as a FastAPI dependency
    - _Requirements: 1.1, 1.2, 1.3, 4.1, 5.1, 5.3, 7.1, 7.2, 7.3, 7.4_

  - [x] 6.2 Register ResetService dependency in FastAPI DI
    - Add `ResetService` instantiation in `platform_api/dependencies.py`
    - Inject pool, redis, audit_service, and backup_dir (from config/env)
    - _Requirements: 2.1_

  - [ ]* 6.3 Write integration tests for admin router endpoints
    - Test full reset flow: seed DB → POST reset → verify user tables empty, admin preserved, config intact
    - Test backup listing: multiple backups → GET → verify sorted response
    - Test restore flow: POST restore → verify records inserted
    - Test auth: missing JWT → 401, non-admin role → 403
    - Test rate limiting: 5 wrong passwords → 429
    - Test partial success: mock Redis failure → 207 response
    - _Requirements: 1.1, 1.2, 1.6, 3.2, 3.3, 3.8, 3.9, 4.1, 5.3, 5.6, 7.1, 7.2, 7.3, 7.4_

- [x] 7. Checkpoint - Backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement frontend hook and types
  - [x] 8.1 Create TypeScript types for user data reset
    - Create `admin_portal/src/types/user-data-reset.ts` with `BackupEntry`, `ResetResult`, `RestoreResult`, `ResetRequest`, `RestoreRequest` interfaces
    - _Requirements: 6.4_

  - [x] 8.2 Create useUserDataReset hook
    - Create `admin_portal/src/hooks/use-user-data-reset.ts`
    - Implement `useBackupList()` — TanStack Query wrapping `GET /admin/user-data/backups`
    - Implement `useResetUserData()` — TanStack Mutation wrapping `POST /admin/user-data/reset`
    - Implement `useRestoreUserData()` — TanStack Mutation wrapping `POST /admin/user-data/restore`
    - Invalidate backup list query on successful reset or restore
    - _Requirements: 6.4, 6.5, 6.6_

- [x] 9. Implement frontend components
  - [x] 9.1 Create PasswordConfirmDialog component
    - Create `admin_portal/src/components/shared/password-confirm-dialog.tsx`
    - Accept props: `open`, `onOpenChange`, `title`, `description`, `onConfirm`, `isLoading`, `error`
    - Disable confirm button when password field is empty
    - Clear password field on close
    - Close on Escape or cancel button click without sending request
    - _Requirements: 1.4, 1.5, 1.7, 1.8, 5.1, 5.2_

  - [x] 9.2 Create UserDataManagementSection component
    - Create `admin_portal/src/pages/settings/user-data-section.tsx`
    - Render destructive reset button (red styling) with warning text
    - Render backup list sorted newest-first with timestamp, file size, and Restore button per entry
    - Show empty-state message when no backups available
    - Show loading indicator and disable buttons during operations
    - Show success toast (auto-dismiss 5s) on completion, error toast (persistent) on failure
    - Show error state with retry button if backup list fails to load
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

  - [x] 9.3 Integrate UserDataManagementSection into Settings page
    - Import and render `UserDataManagementSection` in `admin_portal/src/pages/settings/index.tsx`
    - Wire the password confirmation dialog for both reset and restore flows
    - _Requirements: 6.1, 6.3_

- [x] 10. Checkpoint - Frontend complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Frontend tests
  - [ ]* 11.1 Write unit tests for PasswordConfirmDialog
    - Test button disabled when password empty, enabled when typed
    - Test onConfirm called with password value
    - Test dialog closes on cancel/Escape without calling onConfirm
    - Test loading state disables inputs
    - Test error message displays
    - _Requirements: 1.4, 1.5, 1.8_

  - [ ]* 11.2 Write unit tests for UserDataManagementSection
    - Test renders reset button with destructive styling
    - Test backup list renders entries sorted by date
    - Test empty state message when no backups
    - Test loading state disables buttons
    - Test success/error toasts appear correctly
    - Test error state with retry button on backup list failure
    - _Requirements: 6.1, 6.2, 6.4, 6.5, 6.6, 6.7, 6.8_

  - [ ]* 11.3 Write property tests for frontend data handling (fast-check)
    - Test backup list sorting: for any array of BackupEntry objects, displayed order is always descending by created_at
    - Test file size formatting: for any non-negative integer, formatted size is human-readable and consistent
    - _Requirements: 6.4_

- [x] 12. Final checkpoint - All tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend is implemented first to allow frontend integration testing against real endpoints
- The `DELETION_ORDER` constant ensures FK-safe deletion without disabling constraints

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "3.1", "8.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.2"] },
    { "id": 3, "tasks": ["2.4", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3"] },
    { "id": 5, "tasks": ["6.1", "6.2"] },
    { "id": 6, "tasks": ["6.3", "8.2"] },
    { "id": 7, "tasks": ["9.1", "9.2"] },
    { "id": 8, "tasks": ["9.3"] },
    { "id": 9, "tasks": ["11.1", "11.2", "11.3"] }
  ]
}
```
