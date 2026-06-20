# Requirements Document

## Introduction

This feature integrates the PyQt6 desktop application with the existing Platform API so that all AI generation services (music, image, song drafts) are accessed through the authenticated API rather than called directly. The desktop app gains a login/signup flow, license enforcement, and removes local API keys for AI services. All other app behavior (video export, YouTube upload, UI) remains unchanged.

## Glossary

- **Desktop_App**: The PyQt6-based music generation desktop application (`python_app/`)
- **Platform_API**: The FastAPI backend service providing authentication, credit management, and proxied AI generation endpoints (`platform_api/`)
- **Auth_Client**: The HTTP client module within the Desktop_App responsible for communicating with Platform_API authentication endpoints
- **API_Client**: The HTTP client module within the Desktop_App responsible for communicating with Platform_API generation endpoints
- **Token_Store**: The secure local storage mechanism within the Desktop_App that persists JWT access and refresh tokens between sessions
- **Login_View**: The PyQt6 UI view displayed at application startup for user authentication (login and registration)
- **License_Gate**: The component that checks whether the authenticated user has an active license and controls access to generation features
- **Generation_Proxy**: The service layer within the Desktop_App that routes generation requests (draft, suno, image) through the Platform_API instead of calling external AI services directly
- **JWT**: JSON Web Token used for authenticating API requests
- **Access_Token**: Short-lived JWT used to authorize individual API requests
- **Refresh_Token**: Long-lived token used to obtain a new Access_Token without re-authentication

## Requirements

### Requirement 1: User Authentication — Login

**User Story:** As a desktop app user, I want to log in with my email and password, so that I can access the app's generation features through my Platform API account.

#### Acceptance Criteria

1. WHEN the Desktop_App starts, THE Login_View SHALL be displayed before any other application view is accessible
2. WHEN a user submits valid email and password credentials, THE Auth_Client SHALL send a POST request to `/api/v1/auth/login` on the Platform_API
3. WHEN the Platform_API returns a successful token response, THE Token_Store SHALL persist the Access_Token and Refresh_Token locally
4. WHEN authentication succeeds, THE Desktop_App SHALL navigate from the Login_View to the main application window
5. IF the Platform_API returns a 401 status code, THEN THE Login_View SHALL display an "Invalid email or password" error message
6. IF the Platform_API returns a 403 status code indicating account lockout, THEN THE Login_View SHALL display a message indicating the account is temporarily locked
7. IF the Platform_API is unreachable (network error or timeout), THEN THE Login_View SHALL display a connection error message with a retry option

### Requirement 2: User Authentication — Registration

**User Story:** As a new user, I want to create an account from the desktop app, so that I can start using the music generation platform.

#### Acceptance Criteria

1. THE Login_View SHALL provide a navigation element to switch between login and registration forms
2. WHEN a user submits the registration form, THE Auth_Client SHALL send a POST request to `/api/v1/auth/register` with email, password, and display_name fields
3. WHEN the Platform_API returns a 201 status code, THE Login_View SHALL display a success message and switch to the login form
4. IF the Platform_API returns a 409 status code (duplicate email), THEN THE Login_View SHALL display a message indicating the email is already registered
5. IF the Platform_API returns a 422 status code with validation errors, THEN THE Login_View SHALL display all returned field-level error messages

### Requirement 3: Token Management

**User Story:** As an authenticated user, I want my session to persist across app restarts and refresh automatically, so that I do not have to log in frequently.

#### Acceptance Criteria

1. WHEN the Desktop_App starts and valid tokens exist in the Token_Store, THE Auth_Client SHALL attempt to validate the stored Access_Token by calling the Platform_API
2. IF the stored Access_Token is expired, THEN THE Auth_Client SHALL send a POST request to `/api/v1/auth/refresh` with the stored Refresh_Token to obtain new tokens
3. WHEN the token refresh succeeds, THE Token_Store SHALL replace the old tokens with the new Access_Token and Refresh_Token
4. IF the token refresh fails (401 response), THEN THE Desktop_App SHALL clear the Token_Store and display the Login_View
5. WHEN any API request receives a 401 response, THE Auth_Client SHALL attempt one token refresh before failing the request
6. THE Token_Store SHALL store tokens using the Windows Data Protection API (DPAPI) for secure local encryption
7. WHEN the user logs out, THE Auth_Client SHALL send a POST request to `/api/v1/auth/logout` and THE Token_Store SHALL clear all stored tokens

### Requirement 4: License Enforcement

**User Story:** As a platform operator, I want the desktop app to check the user's license status, so that only licensed users can access generation features.

#### Acceptance Criteria

1. WHEN authentication succeeds, THE License_Gate SHALL send a GET request to `/api/v1/licenses/validate` to check the user's license status
2. IF the license validation returns an active license, THEN THE Desktop_App SHALL enable all generation features (draft, suno, image)
3. IF the license validation returns no active license or an expired license, THEN THE Desktop_App SHALL display a message indicating that an active license is required
4. WHILE the user has no active license, THE Desktop_App SHALL disable the song draft generation, music generation (Suno), and image generation controls
5. WHILE the user has no active license, THE Desktop_App SHALL allow access to all non-generation features (video export, YouTube upload, settings, profiles)
6. WHEN the user opens the application with a previously valid license that has since expired, THE License_Gate SHALL display a license expired notification and disable generation features

### Requirement 5: Song Draft Generation via Platform API

**User Story:** As a desktop app user, I want song draft generation to be routed through the Platform API, so that the platform manages LLM keys and credits centrally.

#### Acceptance Criteria

1. WHEN the user triggers song draft generation, THE Generation_Proxy SHALL send a POST request to `/api/v1/generation/draft` with language, creativity_level, description, structure, avoid_titles, avoid_albums, avoid_openings, forced_title, forced_album, and forced_opening fields
2. WHEN the Platform_API returns a successful response with title, album, and lyrics, THE Generation_Proxy SHALL return the draft data to the calling coordinator in the same format as the existing direct LLM call
3. IF the Platform_API returns a 402 status code (insufficient credits), THEN THE Generation_Proxy SHALL raise an error indicating the user has insufficient credits
4. IF the Platform_API returns a 403 status code (license expired), THEN THE Generation_Proxy SHALL raise an error indicating the license has expired
5. THE Generation_Proxy SHALL include the Access_Token in the Authorization header of all generation requests
6. THE Desktop_App SHALL remove the local DeepSeek API key and SLAI LLM API key settings from the application configuration

### Requirement 6: Music Generation (Suno) via Platform API

**User Story:** As a desktop app user, I want Suno music generation to be routed through the Platform API, so that the platform manages Suno API keys and credits centrally.

#### Acceptance Criteria

1. WHEN the user triggers Suno music generation, THE Generation_Proxy SHALL send a POST request to `/api/v1/generation/suno` with model, title, lyrics, style, and instrumental fields
2. WHEN the Platform_API returns a 202 response with a task_id, THE Generation_Proxy SHALL return the task_id to the calling coordinator
3. WHEN the coordinator polls for Suno task status, THE Generation_Proxy SHALL send a GET request to `/api/v1/generation/suno/{task_id}`
4. WHEN the task status response indicates SUCCESS with audio URLs, THE Generation_Proxy SHALL return the audio URLs to the calling coordinator for download
5. IF the Platform_API returns a 402 status code (insufficient credits), THEN THE Generation_Proxy SHALL raise an error indicating the user has insufficient credits
6. THE Desktop_App SHALL remove the local Suno API key setting from the application configuration
7. THE Desktop_App SHALL retain the local audio download logic (downloading MP3 files from the returned URLs to the configured output directories)

### Requirement 7: Image Generation via Platform API

**User Story:** As a desktop app user, I want image generation to be routed through the Platform API, so that the platform manages FAL and SLAI image API keys centrally.

#### Acceptance Criteria

1. WHEN the image generation worker processes a job, THE Generation_Proxy SHALL send a POST request to `/api/v1/generation/image` with prompt, provider, resolution, style_strength, and base_image (base64-encoded) fields
2. WHEN the Platform_API returns a successful response with image_base64, THE Generation_Proxy SHALL decode the base64 data and return PNG bytes to the calling image pipeline
3. IF the Platform_API returns a 402 status code (insufficient credits), THEN THE Generation_Proxy SHALL raise an error indicating the user has insufficient credits
4. THE Desktop_App SHALL remove the local FAL IMG API key and SLAI IMG API key settings from the application configuration
5. THE Generation_Proxy SHALL support both "fal" and "slai" provider values, matching the existing provider selection logic in the Desktop_App settings

### Requirement 8: API Key Removal

**User Story:** As a platform operator, I want local API keys for AI services removed from the desktop app, so that all key management happens centrally through the Platform API key pool.

#### Acceptance Criteria

1. THE Desktop_App SHALL remove the following settings from the UI and configuration: sunoApiKey, deepseekApiKey, slaiLlmApiKey, falImgApiKey, slaiImgApiKey
2. THE Desktop_App SHALL retain all non-AI-service settings (output directories, resolution, style strength, profile configurations, YouTube OAuth)
3. WHEN the Desktop_App loads an existing configuration that contains removed API key fields, THE Desktop_App SHALL ignore those fields without error
4. THE Desktop_App SHALL add a new configuration setting for the Platform_API base URL (default: `http://localhost:8000/api/v1`)

### Requirement 9: Transparent UX Preservation

**User Story:** As a desktop app user, I want the generation experience to feel identical after the integration, so that the only visible change is the login screen at startup.

#### Acceptance Criteria

1. THE Generation_Proxy SHALL maintain the same function signatures and return types as the existing direct service calls so that coordinators require minimal changes
2. THE Desktop_App SHALL preserve the existing progress reporting, status messages, and error display behavior for all generation workflows
3. THE Desktop_App SHALL preserve the existing batch processing flow (multi-song draft → Suno submission → image generation) without user-facing behavioral changes
4. WHEN a generation request fails due to a network error, THE Generation_Proxy SHALL raise a descriptive error that integrates with the existing error handling UI
5. THE Desktop_App SHALL preserve the existing Suno polling and download behavior, only replacing the API submission and status check calls with Platform_API equivalents
