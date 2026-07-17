# Requirements Document

## Introduction

This feature provides admin-facing functionality for resetting all user-related data from the platform database while preserving system configuration. It includes password-confirmed destructive reset, automatic backup creation before any wipe, and the ability to restore user data from previous backups. The feature spans the Admin Portal (React SPA) and the Platform API (FastAPI backend).

## Glossary

- **Admin_Portal**: The React-based single-page application used by administrators to manage the platform.
- **Platform_API**: The FastAPI backend service that handles business logic, authentication, and database operations.
- **Reset_Service**: The backend service responsible for orchestrating user data deletion, backup creation, and restore operations.
- **Backup**: A JSON-serialized snapshot of all user-related data taken before a reset, stored on the server filesystem.
- **User_Data**: All database records associated with end-users including accounts, tokens, settings, wallets, transactions, channel profiles, batches, songs, tasks, jobs, and usage tracking. Excludes the admin account (admin@mgfaceless.com).
- **System_Config**: Platform-wide configuration tables that persist across resets including plans, pricing, prompts, API keys, OAuth apps, and content pools.
- **Admin_Account**: The administrative user identified by the email admin@mgfaceless.com that is preserved during all reset operations.
- **Redis_Cache**: The Redis instance used for token blocklists, rate limit counters, and session data.

## Requirements

### Requirement 1: Password Confirmation Before Reset

**User Story:** As an admin, I want to re-enter my password before executing a data reset, so that accidental or unauthorized resets are prevented.

#### Acceptance Criteria

1. WHEN the admin submits a reset request, THE Platform_API SHALL verify the provided password against the stored bcrypt hash of the authenticated admin within 5 seconds before initiating the backup and reset operation.
2. IF the provided password does not match the admin's stored password hash, THEN THE Platform_API SHALL reject the reset request with HTTP 401 and return an error message indicating invalid credentials without revealing whether the account exists.
3. IF the provided password matches, THEN THE Platform_API SHALL initiate the backup and reset operation and return HTTP 200 to the Admin_Portal.
4. WHEN the admin clicks the reset action button, THE Admin_Portal SHALL display a password confirmation dialog requiring the admin to type their current password before the reset request is sent to the Platform_API.
5. WHILE the password confirmation dialog is open, THE Admin_Portal SHALL disable the confirm button until the password field contains at least 1 character.
6. IF the admin has failed password verification 5 consecutive times for reset confirmation, THEN THE Platform_API SHALL reject further reset attempts for that admin for 15 minutes and return HTTP 429 with an error message indicating too many failed attempts.
7. IF the password verification request fails due to network error or exceeds a 10-second timeout, THEN THE Admin_Portal SHALL display an error message indicating the verification could not be completed and SHALL NOT send the reset request to the Platform_API.
8. WHEN the admin clicks the cancel button or presses Escape while the password confirmation dialog is open, THE Admin_Portal SHALL close the dialog without sending any request to the Platform_API.

### Requirement 2: Automatic Backup Before Reset

**User Story:** As an admin, I want the system to automatically create a backup of all user data before wiping it, so that I can restore data if needed.

#### Acceptance Criteria

1. WHEN a reset request is confirmed (password verified), THE Reset_Service SHALL create a complete backup of all user data before any deletion occurs.
2. THE Backup SHALL include all rows from: users (except Admin_Account), refresh_tokens, user_settings, notification_queue, credit_wallets, credit_transactions, channel_profiles, batches, songs, suno_tasks, image_jobs, youtube_connected_accounts, youtube_connect_sessions, batch_channel_assets, profile_video_templates, usage_tracking, plan_usage, onboarding_ai_usage, onboarding_drafts, billing_payments, redeem_code_redemptions, invitation_code_redemptions, licenses, client_log_batches, audit_logs, and user-owned music_descriptions and music_structures (WHERE user_id IS NOT NULL).
3. THE Backup SHALL be stored as a JSON file on the server filesystem with a filename containing a UTC timestamp in ISO 8601 format (e.g., backup_2026-07-13T10-30-00Z.json).
4. THE Backup SHALL record metadata including: creation timestamp, total record count, list of tables included, and the admin actor ID who triggered the reset.
5. IF the backup creation fails (disk write error, serialization error), THEN THE Reset_Service SHALL abort the reset operation and return HTTP 500 with error message "Backup creation failed, reset aborted".

### Requirement 3: User Data Reset Execution

**User Story:** As an admin, I want to wipe all user-related data while keeping system configuration intact, so that I can start fresh without reconfiguring the platform.

#### Acceptance Criteria

1. WHEN the backup completes successfully, THE Reset_Service SHALL delete all rows from the user data tables in the correct foreign-key dependency order to avoid constraint violations.
2. THE Reset_Service SHALL preserve the Admin_Account row (email = admin@mgfaceless.com) in the users table during the reset.
3. THE Reset_Service SHALL preserve all rows in System_Config tables: plans, plan_offers, credit_packs, credit_pricing, ai_model_costs, system_settings, rate_limit_config, channel_prompts, music_languages, key_pool_configs, api_key_entries, key_status_events, youtube_oauth_apps, image_sample_packs, image_random_history, title_pool, album_pool, opening_pairs, content_pool_preset_packs, blog_posts, and global music_descriptions and music_structures (WHERE user_id IS NULL).
4. THE Reset_Service SHALL reset the current_redemptions column to 0 on all rows in the redeem_codes table.
5. THE Reset_Service SHALL reset the current_uses column to 0 on all rows in the invitation_codes table.
6. THE Reset_Service SHALL execute all database deletions and counter resets within a single database transaction with a statement timeout of 120 seconds, so that a failure at any step rolls back all changes.
7. WHEN the database transaction commits successfully, THE Reset_Service SHALL flush Redis keys matching patterns: token_blocklist:*, rate_limit:*, and session:*.
8. IF any database deletion or counter reset step fails, THEN THE Reset_Service SHALL roll back the transaction and return HTTP 500 with an error message indicating which table or step failed.
9. IF the Redis flush fails after a successful database commit, THEN THE Reset_Service SHALL log the failure, return HTTP 207 with a response indicating the database reset succeeded but Redis flush failed, and include the uncleared Redis key patterns in the response.
10. WHEN the reset completes successfully, THE Reset_Service SHALL create an audit_logs entry recording the reset action with the admin actor ID, timestamp, and a per-table breakdown of record counts deleted.

### Requirement 4: Backup Listing

**User Story:** As an admin, I want to see a list of all available backups, so that I can choose which one to restore from.

#### Acceptance Criteria

1. WHEN the admin requests the backup list, THE Platform_API SHALL return a list of all available backup files sorted by creation date (newest first) within 3 seconds, returning at most 100 entries.
2. THE Platform_API SHALL return for each backup: filename, creation timestamp (UTC ISO 8601), file size in bytes, total record count, and the list of table names included.
3. IF no backups exist, THEN THE Platform_API SHALL return an empty list with HTTP 200.
4. IF the backup storage directory is inaccessible or a backup file's metadata cannot be read, THEN THE Platform_API SHALL return HTTP 500 with an error message indicating the storage access failure, and SHALL NOT return a partial list.

### Requirement 5: Restore From Backup

**User Story:** As an admin, I want to restore user data from a previous backup, so that I can recover data after a reset.

#### Acceptance Criteria

1. WHEN the admin selects a backup to restore, THE Admin_Portal SHALL display a password confirmation dialog before sending the restore request.
2. IF the admin enters an incorrect password in the restore confirmation dialog, THEN THE Admin_Portal SHALL display an error message indicating invalid credentials and SHALL NOT send the restore request.
3. WHEN a restore request is confirmed (password verified), THE Reset_Service SHALL read the selected backup file and insert all records back into the database, skipping any record that already exists with the same primary key.
4. THE Reset_Service SHALL execute the restore within a single database transaction and SHALL abort the transaction if it has not completed within 120 seconds.
5. IF any insert fails due to constraint violations or data corruption, THEN THE Reset_Service SHALL roll back the restore transaction and return HTTP 500 with an error message describing the failure.
6. IF the requested backup file does not exist on the filesystem, THEN THE Platform_API SHALL return HTTP 404 with error message "Backup not found".
7. WHEN the restore completes successfully, THE Reset_Service SHALL create an audit_logs entry recording the restore action with the backup filename and record count restored.
8. WHEN the restore completes successfully, THE Admin_Portal SHALL display a success notification indicating the number of records restored.

### Requirement 6: Admin Portal Settings UI

**User Story:** As an admin, I want a clear UI in the Settings page to access reset and restore functionality, so that I can manage user data without direct database access.

#### Acceptance Criteria

1. THE Admin_Portal SHALL display a "User Data Management" section on the Settings page containing the reset button and backup/restore controls.
2. THE Admin_Portal SHALL display the reset button with a destructive visual style (red color) and warning text explaining that the action deletes all user data.
3. WHEN the admin clicks the reset button, THE Admin_Portal SHALL show the password confirmation dialog before proceeding.
4. THE Admin_Portal SHALL display a list of available backups sorted by creation date descending (newest first), showing timestamp, human-readable file size, and a "Restore" button for each entry, and SHALL display an empty-state message indicating no backups are available when the list is empty.
5. WHILE a reset or restore operation is in progress, THE Admin_Portal SHALL display a loading indicator and disable the reset and restore buttons to prevent concurrent operations.
6. WHEN a reset or restore operation completes successfully, THE Admin_Portal SHALL display a success toast notification that auto-dismisses after 5 seconds and refresh the backup list.
7. IF a reset or restore operation fails, THEN THE Admin_Portal SHALL display an error toast notification with the error message returned by the Platform_API that persists until manually dismissed by the admin.
8. IF the backup list fails to load from the Platform_API, THEN THE Admin_Portal SHALL display an error state with the error message and a retry button to re-fetch the list.

### Requirement 7: Authorization and Access Control

**User Story:** As a platform operator, I want reset and restore endpoints to be restricted to admin users only, so that unauthorized users cannot destroy or manipulate data.

#### Acceptance Criteria

1. THE Platform_API SHALL require a valid admin JWT token (role claim equals "admin") for all data-reset, backup-listing, and data-restore endpoints; requests missing the admin role claim SHALL be rejected before any endpoint logic executes.
2. IF an authenticated user with a non-admin role attempts to access any data-reset, backup-listing, or data-restore endpoint, THEN THE Platform_API SHALL return HTTP 403 with an error message indicating that admin privileges are required, without executing the requested operation.
3. IF a request to any data-reset, backup-listing, or data-restore endpoint does not include a valid JWT token (missing, expired, or malformed), THEN THE Platform_API SHALL return HTTP 401 with an error message indicating that authentication is required.
4. THE Platform_API SHALL enforce authorization checks on protected endpoints in the following order: token presence and validity (401), then role verification (403); the first failing check determines the response.
