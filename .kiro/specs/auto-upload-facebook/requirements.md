# Requirements Document

## Introduction

This feature adds automated Facebook page video/reel uploads to the Music page's Automation Card via browser automation. Unlike YouTube (which uses OAuth API), Facebook upload uses Playwright with persistent browser contexts to drive a pre-logged-in Chrome session, navigating Facebook's Creator Studio or Reels upload UI to post videos. The feature supports multiple Facebook pages per account, configurable post metadata (captions, hashtags), upload queuing with retry logic, rate limiting to avoid anti-automation detection, and full fault isolation from the rest of the pipeline.

## Glossary

- **Automation_Card**: The horizontal card in the Music page containing automation toggle buttons (Auto-Gen Image, Auto-GSuno, Auto-Video, Auto Merge, Auto Reel, Auto-Upload)
- **Facebook_Upload_Coordinator**: The feature coordinator managing Facebook upload lifecycle, queue processing, session health, and retry logic
- **Facebook_Upload_Queue**: The ordered list of pending Facebook upload jobs stored in the database, processed sequentially with rate limiting
- **Facebook_Upload_Job**: A single database record representing one video file to be uploaded to a specific Facebook page with associated metadata
- **Browser_Session**: A Playwright persistent browser context storing cookies, localStorage, and session tokens for a logged-in Facebook account
- **Facebook_Account**: A stored configuration representing one Facebook user login with an associated browser profile directory
- **Facebook_Page**: A Facebook page managed by a Facebook_Account, identified by page name and URL, selected as the upload target
- **Upload_Worker**: A background thread that processes one Facebook_Upload_Job at a time using browser automation
- **Rate_Limiter**: The component that enforces minimum delays between consecutive uploads to avoid Facebook's anti-automation detection
- **Session_Validator**: The component that checks whether a Browser_Session is still authenticated before attempting uploads
- **Music_Settings**: The persisted key-value settings store for the Music page
- **Auto_Video_Pipeline**: The automated workflow that exports MP4 videos from MP3 tracks after a Suno batch completes
- **Post_Metadata**: The caption text, hashtags, and optional scheduling information associated with a Facebook upload
- **Reel_Video**: A video rendered in 9:16 portrait format (1080×1920) intended for short-form platforms like Facebook Reels
- **Progress_Table**: The QTableWidget on the Progress page displaying batch rows with metadata (batchId, profileId, role, outDir) stored in Qt.ItemDataRole.UserRole
- **Row_Context_Menu**: The right-click context menu on a Progress_Table row providing actions such as Restart Converter, Restart Merge, Start YouTube Upload
- **Reel_Prerequisites**: The set of files required to generate reel MP4s: MP3 audio files, a background image, and the profile's reel video template
- **Merge_Choice_Dialog**: A modal dialog presented during manual upload that lets the user choose between merging multiple reels into one video or posting each reel individually

## Requirements

### Requirement 1: Auto Upload Facebook Toggle in Automation Card

**User Story:** As a music producer, I want an "Auto Upload Facebook" toggle in the Automation Card, so that I can enable or disable automatic Facebook posting as part of my pipeline without affecting other automation stages.

#### Acceptance Criteria

1. THE Automation_Card SHALL display an "Auto Upload Facebook" toggle button positioned after the existing "Auto-Upload" (YouTube) toggle
2. WHEN the Auto Upload Facebook toggle is clicked, THE Music_Settings SHALL persist the `autoUploadFacebook` boolean value immediately
3. WHEN the Music page loads, THE Automation_Card SHALL restore the Auto Upload Facebook toggle state from the persisted `autoUploadFacebook` setting, defaulting to false when no persisted value exists
4. IF the `autoUploadFacebook` setting cannot be read from persistence, THEN THE Automation_Card SHALL display the Auto Upload Facebook toggle in the off (false) state
5. WHEN the application starts, THE Facebook_Upload_Coordinator SHALL reset the persisted `autoUploadFacebook` setting to false to prevent unintended automatic uploads from a previous session

### Requirement 2: Facebook Account Management

**User Story:** As a music producer, I want to register and manage Facebook accounts for uploading, so that the system can authenticate using my existing browser sessions.

#### Acceptance Criteria

1. THE Settings page SHALL provide a "Facebook Accounts" section for managing registered Facebook accounts
2. WHEN a user adds a new Facebook account, THE system SHALL store the account name, browser profile directory path, and a user-defined label
3. THE system SHALL support storing multiple Facebook accounts simultaneously
4. WHEN a user removes a Facebook account, THE system SHALL delete the account record and all associated page mappings from the database
5. THE system SHALL store Facebook account records in the `facebook_accounts` database table with fields: uid, label, browser_profile_path, created_at, updated_at
6. IF the browser profile directory path does not exist on disk, THEN THE system SHALL display a warning indicator next to the account entry

### Requirement 3: Facebook Page Discovery and Selection

**User Story:** As a music producer, I want to discover and select which Facebook pages to upload to, so that I can target specific pages for my video content.

#### Acceptance Criteria

1. WHEN a user triggers page discovery for a Facebook account, THE Facebook_Upload_Coordinator SHALL launch a Browser_Session using the account's browser profile and navigate to the Facebook page-switching UI to retrieve the list of available pages
2. THE system SHALL store discovered pages in the `facebook_pages` database table with fields: uid, account_uid, page_name, page_url, is_active, last_verified_at
3. WHEN page discovery completes, THE Settings page SHALL display all discovered pages with checkboxes to mark pages as active upload targets
4. THE system SHALL support multiple active pages per account for simultaneous upload targeting
5. IF page discovery fails due to session expiry or network error, THEN THE Facebook_Upload_Coordinator SHALL report the failure reason to the user and mark the account session as requiring re-authentication

### Requirement 4: Browser Session Management and Persistence

**User Story:** As a music producer, I want the system to maintain persistent browser sessions so that I do not need to re-login to Facebook for every upload.

#### Acceptance Criteria

1. THE Facebook_Upload_Coordinator SHALL use Playwright persistent browser contexts with the configured browser profile directory to maintain login state between application sessions
2. WHEN an upload is about to start, THE Session_Validator SHALL verify the Browser_Session is authenticated by checking for known authenticated-state indicators on the Facebook page
3. IF the Session_Validator detects an expired or invalid session, THEN THE Facebook_Upload_Coordinator SHALL mark the associated Facebook_Account as "session_expired", skip all pending jobs for that account, and emit a status notification requesting the user to re-authenticate
4. THE system SHALL provide a "Verify Session" button in the Settings page that launches the browser visibly so the user can manually log in or resolve authentication challenges
5. WHILE a Browser_Session is active for upload processing, THE Facebook_Upload_Coordinator SHALL use headless mode by default for automated uploads
6. THE system SHALL store session health status (valid, expired, unknown) per Facebook_Account in the database

### Requirement 5: Upload Job Creation from Pipeline Events

**User Story:** As a music producer, I want Facebook upload jobs to be created automatically when the auto-video pipeline completes with reel outputs, so that my content flows to Facebook without manual intervention.

#### Acceptance Criteria

1. WHEN the `auto_video_done` event is emitted with a non-empty `reelOutput` field AND `autoUploadFacebook` is true, THE Facebook_Upload_Coordinator SHALL create one Facebook_Upload_Job for each active Facebook_Page targeting the reel merged file
2. WHEN the `auto_video_done` event is emitted AND `autoUploadFacebook` is true AND individual reel MP4 files exist in the output directory AND the user's `facebookUploadMode` setting is "individual_reels", THE Facebook_Upload_Coordinator SHALL create one Facebook_Upload_Job per individual reel file per active Facebook_Page
3. THE Facebook_Upload_Job record SHALL include fields: uid, account_uid, page_uid, file_path, caption, hashtags, status, attempt_count, created_at, updated_at, completed_at, error_message, batch_id, profile_id, role
4. WHEN a Facebook_Upload_Job is created, THE system SHALL set the initial status to "pending"
5. IF no active Facebook pages are configured when `autoUploadFacebook` is true, THEN THE Facebook_Upload_Coordinator SHALL emit a warning status message and skip job creation without affecting the rest of the pipeline

### Requirement 6: Upload Queue Processing

**User Story:** As a music producer, I want Facebook uploads to be processed sequentially from a queue with proper rate limiting, so that uploads are reliable and do not trigger Facebook's anti-automation systems.

#### Acceptance Criteria

1. THE Upload_Worker SHALL process Facebook_Upload_Jobs one at a time in FIFO order (oldest pending job first)
2. THE Rate_Limiter SHALL enforce a configurable minimum delay between consecutive upload completions, defaulting to 120 seconds
3. WHILE the Upload_Worker is processing a job, THE Facebook_Upload_Coordinator SHALL update the job status to "uploading"
4. WHEN an upload completes successfully, THE Facebook_Upload_Coordinator SHALL update the job status to "completed" and record the completion timestamp
5. THE Upload_Worker SHALL only process jobs when `autoUploadFacebook` is true; WHEN the toggle is set to false, THE Upload_Worker SHALL pause processing without cancelling pending jobs
6. THE Facebook_Upload_Coordinator SHALL use a single Upload_Worker thread to prevent concurrent browser sessions that could trigger detection

### Requirement 7: Upload Execution via Browser Automation

**User Story:** As a music producer, I want the system to navigate Facebook's upload interface using browser automation to post my videos as reels, so that uploads work without requiring official API access.

#### Acceptance Criteria

1. WHEN processing a Facebook_Upload_Job, THE Upload_Worker SHALL launch a Playwright browser context using the associated account's browser profile directory
2. THE Upload_Worker SHALL navigate to the target Facebook_Page's reel creation URL and interact with the upload form to submit the video file
3. WHEN the video file is submitted, THE Upload_Worker SHALL fill in the caption and hashtags from the job's Post_Metadata before confirming the post
4. THE Upload_Worker SHALL wait for confirmation that the post was published successfully by detecting the success indicator on the page
5. IF the upload form navigation fails due to unexpected page structure changes, THEN THE Upload_Worker SHALL capture a screenshot for debugging, mark the job as "failed", and record the failure details
6. THE Upload_Worker SHALL implement configurable timeouts: 60 seconds for page navigation, 300 seconds for video upload completion, and 30 seconds for post confirmation

### Requirement 8: Upload Retry and Error Recovery

**User Story:** As a music producer, I want failed uploads to retry automatically with exponential backoff, so that transient failures (network issues, temporary Facebook UI changes) resolve without my intervention.

#### Acceptance Criteria

1. IF a Facebook_Upload_Job fails during upload, THEN THE Facebook_Upload_Coordinator SHALL increment the attempt count and reschedule the job with exponential backoff delay (attempt 1: 2 minutes, attempt 2: 5 minutes, attempt 3: 15 minutes, attempt 4: 60 minutes)
2. IF a Facebook_Upload_Job reaches the maximum retry count of 4 attempts, THEN THE Facebook_Upload_Coordinator SHALL mark the job as "failed_permanent" and stop retrying
3. IF the failure reason is classified as "session_expired", THEN THE Facebook_Upload_Coordinator SHALL skip retry and mark all pending jobs for that account as "blocked_session" until the session is restored
4. THE system SHALL classify failures into categories: transient (network timeout, temporary UI glitch), session (login required, CAPTCHA), and permanent (file not found, video rejected by Facebook)
5. WHEN a previously "blocked_session" account has its session restored, THE Facebook_Upload_Coordinator SHALL transition all "blocked_session" jobs back to "pending" status

### Requirement 9: Post Metadata Configuration

**User Story:** As a music producer, I want to configure default captions and hashtags for Facebook uploads, so that my posts have consistent branding without manual editing each time.

#### Acceptance Criteria

1. THE Settings page SHALL provide a "Facebook Post Defaults" section with fields for default caption template and default hashtags
2. THE caption template SHALL support placeholder variables: `{track_name}`, `{batch_date}`, `{profile_name}`, `{role}`
3. WHEN a Facebook_Upload_Job is created, THE Facebook_Upload_Coordinator SHALL resolve the caption template using actual values from the batch context and store the resolved text in the job record
4. THE system SHALL persist the default caption template and hashtags in Music_Settings under keys `facebookDefaultCaption` and `facebookDefaultHashtags`
5. THE system SHALL enforce a maximum caption length of 2200 characters (Facebook's limit) and truncate with an ellipsis if the resolved caption exceeds the limit

### Requirement 10: Upload Mode Selection

**User Story:** As a music producer, I want to choose whether to upload the merged reel file or individual reel files to Facebook, so that I can control the content format per my creative preference.

#### Acceptance Criteria

1. THE Settings page SHALL provide an "Upload Mode" selector with options: "merged_reel" (upload the single merged reel file) and "individual_reels" (upload each individual reel MP4 separately)
2. WHEN `facebookUploadMode` is "merged_reel", THE Facebook_Upload_Coordinator SHALL create one upload job per active page using the merged reel file path from the `reelOutput` field
3. WHEN `facebookUploadMode` is "individual_reels", THE Facebook_Upload_Coordinator SHALL create one upload job per individual reel MP4 file per active page
4. THE system SHALL persist the upload mode selection in Music_Settings under the key `facebookUploadMode`, defaulting to "merged_reel"
5. IF the selected upload mode is "merged_reel" AND the `reelOutput` field is empty (merge was skipped or failed), THEN THE Facebook_Upload_Coordinator SHALL fall back to uploading individual reel files and emit an informational status message

### Requirement 11: Fault Isolation from Pipeline

**User Story:** As a music producer, I want Facebook upload failures to never affect other pipeline stages (video generation, merge, YouTube upload), so that a Facebook outage or automation detection does not break my workflow.

#### Acceptance Criteria

1. THE Facebook_Upload_Coordinator SHALL catch all exceptions within its processing boundary and SHALL NOT propagate exceptions to the calling auto-video pipeline or event bus handlers
2. IF the Facebook_Upload_Coordinator encounters an unrecoverable error during initialization, THEN THE system SHALL log the error, disable the feature gracefully, and allow the rest of the application to function normally
3. THE Facebook_Upload_Coordinator SHALL operate in its own background thread, isolated from the auto-video pipeline thread, the YouTube upload thread, and the UI thread
4. THE Facebook_Upload_Coordinator SHALL not hold any locks, database connections, or file handles that are shared with other pipeline stages
5. IF the Playwright browser process crashes, THEN THE Facebook_Upload_Coordinator SHALL terminate the crashed process, mark the current job as failed (transient), and continue processing the queue after the retry delay

### Requirement 12: Status Tracking and UI Feedback

**User Story:** As a music producer, I want to see the status of Facebook uploads in the application, so that I can monitor progress and identify issues.

#### Acceptance Criteria

1. THE Music page SHALL display a Facebook upload status label showing the current state (idle, uploading, waiting for rate limit, error)
2. WHEN an upload job status changes, THE Facebook_Upload_Coordinator SHALL emit a `facebook_upload_status` event on the UI bus with the current message
3. THE system SHALL provide a Facebook Jobs view (accessible from the Music page) displaying all upload jobs with columns: status, page name, file name, attempts, created time, error message
4. WHEN a job completes or fails permanently, THE Facebook_Upload_Coordinator SHALL emit a `facebook_upload_done` event with fields: jobUid, ok (boolean), error (string), pageId
5. THE Facebook Jobs view SHALL support manual retry of failed jobs via a "Retry" button that resets the job status to "pending" and clears the attempt count

### Requirement 13: Settings Page Configuration

**User Story:** As a music producer, I want all Facebook upload settings centralized on the Settings page, so that I can configure the feature in one place.

#### Acceptance Criteria

1. THE Settings page SHALL provide a "Facebook Upload" section containing: account management, page selection, upload mode, rate limit delay, caption template, hashtags, and timeout settings
2. WHEN the rate limit delay setting is changed, THE Music_Settings SHALL persist the value under the key `facebookRateLimitSeconds` with a minimum of 60 seconds and a default of 120 seconds
3. WHEN timeout settings are changed, THE Music_Settings SHALL persist values under keys `facebookNavTimeoutSeconds` (default 60), `facebookUploadTimeoutSeconds` (default 300), and `facebookConfirmTimeoutSeconds` (default 30)
4. THE Settings page SHALL display the session health status for each registered Facebook account (valid, expired, unknown)
5. THE Settings page SHALL provide a "Test Upload" button that performs a dry-run navigation to the upload page (without posting) to verify the browser session and page access

### Requirement 14: Database Schema for Facebook Upload Feature

**User Story:** As a developer, I want a clean database schema for Facebook upload state, so that job tracking and account configuration persist across application restarts.

#### Acceptance Criteria

1. THE system SHALL create a `facebook_accounts` table with columns: uid (text, primary key), label (text), browser_profile_path (text), session_status (text, default "unknown"), created_at (text), updated_at (text)
2. THE system SHALL create a `facebook_pages` table with columns: uid (text, primary key), account_uid (text, foreign key), page_name (text), page_url (text), is_active (boolean, default false), last_verified_at (text)
3. THE system SHALL create a `facebook_upload_jobs` table with columns: uid (text, primary key), account_uid (text), page_uid (text), file_path (text), caption (text), hashtags (text), status (text, default "pending"), attempt_count (integer, default 0), next_retry_at (text), created_at (text), updated_at (text), completed_at (text), error_message (text), error_category (text), batch_id (text), profile_id (text), role (text)
4. THE database migration SHALL be idempotent (using CREATE TABLE IF NOT EXISTS) and SHALL NOT affect any existing tables
5. IF the database migration fails, THEN THE system SHALL log the error and allow the application to start without the Facebook upload feature (graceful degradation)

### Requirement 15: Feature Module Structure

**User Story:** As a developer, I want the Facebook upload feature to live in its own module following the existing feature architecture, so that the codebase remains organized and maintainable.

#### Acceptance Criteria

1. THE Facebook upload feature SHALL reside in the `python_app/features/facebook_upload/` directory
2. THE module SHALL contain at minimum: `__init__.py`, `coordinator.py`, `db.py`, `browser_automation.py`, `session_manager.py`
3. THE Facebook_Upload_Coordinator SHALL follow the same dependency injection pattern as the existing AutoVideoCoordinator (injected accessors, no direct MainWindow references)
4. THE module SHALL declare all public interfaces through the `__init__.py` file
5. THE Facebook_Upload_Coordinator SHALL accept a LoggerPort for logging, matching the pattern used by other feature coordinators

### Requirement 16: Anti-Detection Measures

**User Story:** As a music producer, I want the browser automation to minimize the risk of Facebook detecting automated behavior, so that my accounts are not restricted or banned.

#### Acceptance Criteria

1. THE Upload_Worker SHALL add randomized delays (between 1 and 3 seconds) between UI interactions (clicks, typing) to simulate human behavior
2. THE Upload_Worker SHALL type caption text character-by-character with randomized inter-keystroke delays (between 30 and 120 milliseconds) rather than pasting the entire string
3. THE Browser_Session SHALL use the actual user's browser fingerprint from the persistent profile (no modified user-agent strings or injected scripts)
4. THE Rate_Limiter SHALL add a randomized jitter of 0 to 30 seconds to the configured minimum delay between uploads to avoid predictable timing patterns
5. THE system SHALL limit uploads to a maximum of 10 videos per Facebook page per 24-hour rolling window, configurable via the `facebookDailyUploadLimit` setting (default 10)
6. IF the daily upload limit is reached for a page, THEN THE Facebook_Upload_Coordinator SHALL pause processing for that page and emit a status message indicating the limit was reached

### Requirement 17: Manual Facebook Upload from Progress Page (Single Row)

**User Story:** As a music producer, I want to right-click a row in the Progress table and select "Upload Reel to Facebook", so that I can manually trigger a Facebook reel upload for a specific batch without enabling the full auto-upload pipeline.

#### Acceptance Criteria

1. THE Row_Context_Menu SHALL include an "Upload Reel to Facebook" action positioned after the YouTube upload actions section
2. WHEN the user selects "Upload Reel to Facebook", THE system SHALL read the row's output directory from the row metadata stored in Qt.ItemDataRole.UserRole
3. WHEN the "Upload Reel to Facebook" action is triggered, THE system SHALL verify that Reel_Prerequisites exist in the output directory: at least one MP3 file, a background image file, and a valid reel video template associated with the row's profile
4. IF Reel_Prerequisites are missing from the output directory, THEN THE system SHALL display a warning message identifying which prerequisites are absent and abort the action
5. WHEN Reel_Prerequisites are present AND reel MP4 files (files ending with `_REEL.mp4`) do not already exist in the output directory, THE system SHALL generate reel MP4s using the existing reel export pipeline (`_export_reel_videos`)
6. WHEN Reel_Prerequisites are present AND reel MP4 files already exist in the output directory, THE system SHALL skip reel generation and proceed directly to upload job creation
7. WHEN reel MP4 generation completes (or is skipped) AND more than one reel MP4 exists, THE system SHALL present a Merge_Choice_Dialog asking the user to choose between "Merge into one reel video" or "Post individual reels separately"
8. WHEN the user selects "Merge into one reel video", THE system SHALL merge the reel MP4s into a single merged reel file using the existing merge pipeline and create one Facebook_Upload_Job per active Facebook_Page for the merged file
9. WHEN the user selects "Post individual reels separately", THE Facebook_Upload_Coordinator SHALL create one Facebook_Upload_Job per individual reel MP4 per active Facebook_Page
10. WHEN only one reel MP4 exists, THE system SHALL skip the Merge_Choice_Dialog and create one Facebook_Upload_Job per active Facebook_Page for that single file
11. WHEN Facebook_Upload_Jobs are created, THE system SHALL display a confirmation message showing the number of jobs queued and the target page names
12. THE "Upload Reel to Facebook" action SHALL be disabled when no output directory is set on the row, no active Facebook pages are configured, or the row's role is not "OK" or "ALT"
13. IF no active Facebook pages are configured, THEN THE system SHALL display an informational message directing the user to configure Facebook pages in the Settings page
14. THE system SHALL execute reel generation and merge operations on a background thread to prevent blocking the UI thread


