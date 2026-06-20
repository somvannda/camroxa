# Implementation Plan: Desktop API Integration

## Overview

This plan implements the integration between the PyQt6 desktop application and the Platform API, replacing direct AI service calls with authenticated, credit-managed API requests. The implementation proceeds bottom-up: error types → token storage → auth client → license gate → generation proxy → UI (login view) → wiring into existing coordinators → configuration cleanup.

## Tasks

- [ ] 1. Create API error types and foundational infrastructure
  - [x] 1.1 Create the API error hierarchy module
    - Create `python_app/services/api_errors.py` with all error classes: `PlatformAPIError`, `NetworkError`, `AuthenticationError`, `AccountLockedError`, `TokenExpiredError`, `DuplicateEmailError`, `ValidationError`, `InsufficientCreditsError`, `LicenseExpiredError`, `GenerationError`
    - Each error stores `status_code` and `message`; `ValidationError` additionally stores `field_errors: dict[str, str]`
    - _Requirements: 5.3, 5.4, 6.5, 7.3, 1.5, 1.6, 1.7, 2.4, 2.5_

  - [x] 1.2 Add `platformApiBaseUrl` configuration setting
    - Add `platformApiBaseUrl` to the settings model/dataclass with default value `http://localhost:8000/api/v1`
    - Ensure the settings loader silently ignores removed API key fields (`sunoApiKey`, `deepseekApiKey`, `slaiLlmApiKey`, `falImgApiKey`, `slaiImgApiKey`) when loading existing config files
    - _Requirements: 8.4, 8.3_

  - [ ]* 1.3 Write property test for configuration loading ignoring removed keys
    - **Property 6: Configuration loading ignores removed keys**
    - **Validates: Requirements 8.3**
    - Use Hypothesis to generate random config dicts containing a mix of valid keys and removed API key fields, verify removed keys are absent and valid keys preserved after loading

- [x] 2. Implement Token Store
  - [x] 2.1 Create the Token Store module
    - Create `python_app/services/token_store.py` implementing `TokenStorePort` protocol
    - Implement `StoredTokens` frozen dataclass with `access_token` and `refresh_token`
    - Implement `load()`, `save()`, `clear()`, `has_tokens()` methods
    - Store tokens as DPAPI-encrypted JSON at `%LOCALAPPDATA%/MusicGenerator/auth_tokens.dat`
    - Use existing `dpapi_encrypt_to_base64` / `dpapi_decrypt_from_base64` from `services/dpapi.py`
    - Use atomic file write (write to `.tmp` then rename) to prevent corruption
    - _Requirements: 1.3, 3.3, 3.6, 3.7_

  - [ ]* 2.2 Write property test for token storage round-trip
    - **Property 1: Token storage round-trip**
    - **Validates: Requirements 1.3, 3.3, 3.6**
    - Use Hypothesis to generate arbitrary non-empty token string pairs, save to store, load back, assert equality; verify raw file does not contain plaintext tokens

  - [ ]* 2.3 Write unit tests for Token Store edge cases
    - Test loading from empty/missing file returns None
    - Test loading from corrupt file returns None without crashing
    - Test `clear()` removes the file
    - Test `has_tokens()` returns correct boolean
    - _Requirements: 3.4_

- [x] 3. Implement Auth Client
  - [x] 3.1 Create the Auth Client module
    - Create `python_app/services/auth_client.py` implementing `AuthClientPort` protocol
    - Implement `AuthTokens` frozen dataclass with `access_token`, `refresh_token`, `expires_in`
    - Implement `login()`, `register()`, `refresh()`, `logout()`, `validate()` methods
    - Use `httpx.Client` (sync) with configurable base URL and 15s default timeout
    - Map HTTP status codes to typed exceptions: 401→`AuthenticationError`, 403→`AccountLockedError`, 409→`DuplicateEmailError`, 422→`ValidationError`, network errors→`NetworkError`
    - `logout()` is best-effort (ignores errors)
    - _Requirements: 1.2, 1.5, 1.6, 1.7, 2.2, 2.3, 2.4, 2.5, 3.2, 3.4, 3.7_

  - [ ]* 3.2 Write property test for 401 triggering exactly one token refresh
    - **Property 2: 401 triggers exactly one token refresh**
    - **Validates: Requirements 3.5**
    - Mock HTTP responses to return 401, verify exactly one refresh attempt is made; verify a second 401 after refresh does not trigger another refresh

  - [ ]* 3.3 Write unit tests for Auth Client
    - Test login happy path returns tokens
    - Test login 401 raises `AuthenticationError`
    - Test login 403 raises `AccountLockedError`
    - Test register 201 succeeds
    - Test register 409 raises `DuplicateEmailError`
    - Test register 422 raises `ValidationError` with field errors
    - Test refresh happy path returns new tokens
    - Test refresh 401 raises `TokenExpiredError`
    - Test network timeout raises `NetworkError`
    - _Requirements: 1.2, 1.5, 1.6, 1.7, 2.2, 2.3, 2.4, 2.5, 3.2, 3.4_

- [x] 4. Implement License Gate
  - [x] 4.1 Create the License Gate module
    - Create `python_app/services/license_gate.py` implementing `LicenseGatePort` protocol
    - Implement `LicenseStatus` frozen dataclass with `is_active`, `plan_name`, `expires_at`
    - Implement `validate()` — calls `GET /api/v1/licenses/validate` with Bearer token
    - Implement `is_generation_allowed()` — returns cached status without network call
    - Implement `update_status()` and `get_cached_status()`
    - On network error during validation: use cached status if available, otherwise `is_active=False` (fail-safe)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ]* 4.2 Write property test for license gate blocking generation
    - **Property 5: License gate blocks all generation when inactive**
    - **Validates: Requirements 4.4**
    - Use Hypothesis to generate random generation operation types, verify all are blocked when `is_generation_allowed()` is False

  - [ ]* 4.3 Write unit tests for License Gate
    - Test active license enables generation
    - Test expired license disables generation
    - Test missing license disables generation
    - Test network error uses cached status
    - _Requirements: 4.1, 4.2, 4.3, 4.6_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Generation Proxy
  - [x] 6.1 Create the Generation Proxy module
    - Create `python_app/services/generation_proxy.py` implementing `GenerationProxyPort` protocol
    - Implement `generate_song_draft()` — POST to `/api/v1/generation/draft`, return `{"title", "album", "lyrics"}` dict matching existing format
    - Implement `submit_suno()` — POST to `/api/v1/generation/suno`, return `task_id` string
    - Implement `get_suno_status()` — GET to `/api/v1/generation/suno/{task_id}`, return `{"status", "audioUrls"}` dict
    - Implement `generate_image()` — POST to `/api/v1/generation/image` with base64-encoded image, return decoded PNG bytes
    - Include access token in `Authorization: Bearer` header for all requests
    - On 401: attempt one token refresh via AuthClient, then retry the request
    - On 402: raise `InsufficientCreditsError`; On 403: raise `LicenseExpiredError`
    - On network errors: raise `NetworkError` with descriptive message including URL or failure nature
    - Support `on_log` for HTTP timing info and `should_cancel` for pre-request cancellation check
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.5, 9.1, 9.4_

  - [ ]* 6.2 Write property test for generation request field mapping
    - **Property 3: Generation requests include all fields and auth header**
    - **Validates: Requirements 5.1, 5.5, 6.1, 7.1**
    - Use Hypothesis to generate random valid generation parameters (draft, suno, image), mock HTTP transport, verify all fields are present in the request body and the Authorization header contains the access token

  - [ ]* 6.3 Write property test for generation response pass-through
    - **Property 4: Generation response pass-through**
    - **Validates: Requirements 5.2, 6.2, 6.4, 7.2**
    - Use Hypothesis to generate random response payloads (draft title/album/lyrics, suno task_id, suno audio URLs, image base64), verify the proxy returns them unmodified to the caller

  - [ ]* 6.4 Write property test for network error descriptive messages
    - **Property 7: Network errors produce descriptive messages**
    - **Validates: Requirements 9.4**
    - Use Hypothesis with various network failure conditions, verify raised error message is non-empty and includes URL or failure nature

  - [ ]* 6.5 Write unit tests for Generation Proxy
    - Test draft generation happy path
    - Test suno submit happy path returns task_id
    - Test suno status polling returns audio URLs on SUCCESS
    - Test image generation returns decoded PNG bytes
    - Test 402 raises InsufficientCreditsError
    - Test 403 raises LicenseExpiredError
    - Test 401 triggers refresh then retries successfully
    - _Requirements: 5.1, 5.2, 6.1, 6.2, 6.4, 7.1, 7.2_

- [x] 7. Implement Login View and Controller
  - [x] 7.1 Create the Login View UI
    - Create `python_app/views/login_view.py` as a `QWidget` subclass
    - Implement centered card layout with app logo
    - Implement tab-style toggle between "Login" and "Register" forms
    - Login form: email field, password field, submit button
    - Register form: email field, password field, display name field, submit button
    - Error message area (red text below form)
    - Success message area (green text, for post-registration)
    - Loading spinner state on submit button
    - Retry button for network errors
    - Style using existing token-based QSS design system
    - Define signals: `login_requested(str, str)`, `register_requested(str, str, str)`, `switch_to_register()`, `switch_to_login()`
    - Define slots: `show_error(str)`, `show_field_errors(dict)`, `show_success(str)`, `set_loading(bool)`
    - _Requirements: 1.1, 1.5, 1.6, 1.7, 2.1, 2.3, 2.4, 2.5_

  - [x] 7.2 Create the Login Page Controller
    - Create `python_app/views/login_page_controller.py`
    - Constructor takes: `auth_client`, `token_store`, `license_gate`, `on_authenticated` callback
    - Implement `handle_login()` — spawn worker thread: call `auth_client.login()`, save tokens to `token_store`, check license via `license_gate`, call `on_authenticated()` on success
    - Implement `handle_register()` — spawn worker thread: call `auth_client.register()`, show success, switch to login form
    - Implement `attempt_auto_login()` — validate stored tokens or refresh them, navigate to main window on success
    - Map exceptions to view error display: `AuthenticationError`→"Invalid email or password", `AccountLockedError`→"Account temporarily locked", `NetworkError`→connection error with retry, `DuplicateEmailError`→"Email already registered", `ValidationError`→field errors
    - _Requirements: 1.2, 1.4, 1.5, 1.6, 1.7, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.4_

  - [ ]* 7.3 Write property test for field validation errors fully surfaced
    - **Property 8: Field validation errors are fully surfaced**
    - **Validates: Requirements 2.5**
    - Use Hypothesis to generate random dicts of field names → error messages, pass through the controller and verify the Login View displays all of them without dropping any

  - [ ]* 7.4 Write unit tests for Login Page Controller
    - Test successful login flow navigates to main window
    - Test login 401 shows error message
    - Test login network error shows retry option
    - Test successful registration shows success and switches to login
    - Test auto-login with valid stored tokens navigates to main window
    - Test auto-login with expired tokens triggers refresh
    - Test auto-login with failed refresh shows login view
    - _Requirements: 1.2, 1.4, 1.5, 1.7, 2.3, 3.1, 3.2, 3.4_

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Integrate into existing service modules
  - [x] 9.1 Modify `services/music_generation.py` to use Generation Proxy
    - Replace `generate_song_draft_with_deepseek()` and `generate_song_draft_with_slai()` with a unified `generate_song_draft()` function that delegates to `GenerationProxy.generate_song_draft()`
    - Remove `api_key` parameter from function signatures
    - Add `generation_proxy: GenerationProxyPort` parameter
    - Maintain the same return type `dict[str, str]` with keys `title`, `album`, `lyrics`
    - _Requirements: 5.1, 5.2, 9.1, 9.2_

  - [x] 9.2 Modify `services/music_suno.py` to use Generation Proxy
    - Replace `suno_api_generate()` calls with `GenerationProxy.submit_suno()`
    - Replace `suno_api_try_get_tracks()` calls with `GenerationProxy.get_suno_status()`
    - Remove Suno API key usage from all function signatures
    - Retain all local download logic (download MP3 from URLs, build output paths, plan run dir)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.7, 9.5_

  - [x] 9.3 Modify `services/image_generation.py` to use Generation Proxy
    - Replace FAL/SLAI direct provider calls in `_run_one_image_job()` with `GenerationProxy.generate_image()`
    - Remove `api_key` parameter from `_run_job_batch()` and `_run_one_image_job()`
    - Add `generation_proxy: GenerationProxyPort` parameter
    - Support both "fal" and "slai" provider values passed to the proxy
    - _Requirements: 7.1, 7.2, 7.4, 7.5_

  - [x] 9.4 Update Music Coordinator to use Generation Proxy
    - Modify `features/music/coordinator.py` constructor to accept `generation_proxy: GenerationProxyPort`
    - Update `prepare_suno_submission()` to no longer check for `sunoApiKey` in settings
    - Update `execute_suno_api_call()` to delegate to `generation_proxy.submit_suno()`
    - Update draft generation calls to use the proxy-based unified function
    - Catch `InsufficientCreditsError` and `LicenseExpiredError` in error handlers
    - _Requirements: 5.1, 6.1, 9.2, 9.3_

  - [x] 9.5 Update Image Coordinator to use Generation Proxy
    - Modify `features/image/coordinator.py` constructor to accept `generation_proxy: GenerationProxyPort`
    - Pass proxy to `run_pending_image_jobs()` instead of API key
    - Catch `InsufficientCreditsError` and `LicenseExpiredError` in error handlers
    - _Requirements: 7.1, 9.2, 9.3_

- [x] 10. Wire bootstrap startup flow and navigation
  - [x] 10.1 Modify `app/bootstrap.py` for auth-aware startup
    - Instantiate `TokenStore`, `AuthClient`, `LicenseGate`, `GenerationProxy` at app startup
    - Implement startup flow: check for stored tokens → validate/refresh → license check → show main window OR show Login View
    - On successful authentication from Login View: check license → enable/disable generation → navigate to main window
    - Inject `GenerationProxy` into music coordinator and image coordinator constructors
    - Wire `LoginPageController` with `on_authenticated` callback that transitions to main window
    - _Requirements: 1.1, 1.4, 3.1, 3.2, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 10.2 Implement license-based UI gating in main window
    - When `LicenseGate.is_generation_allowed()` returns False: disable draft generation, Suno generation, and image generation controls
    - Display license expired/missing message in a non-blocking notification or status area
    - Keep non-generation features enabled (video export, YouTube upload, settings, profiles)
    - When license is valid: enable all generation controls
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x] 10.3 Implement logout functionality
    - Add logout action/button to the main window (settings or menu area)
    - On logout: call `auth_client.logout()` (best-effort), clear `token_store`, navigate back to Login View
    - _Requirements: 3.7_

- [x] 11. Remove local API key settings from UI and configuration
  - [x] 11.1 Remove API key fields from settings UI
    - Remove input fields for `sunoApiKey`, `deepseekApiKey`, `slaiLlmApiKey`, `falImgApiKey`, `slaiImgApiKey` from the settings view
    - Retain all non-AI-service settings (output directories, resolution, style strength, profiles, YouTube OAuth)
    - _Requirements: 8.1, 8.2_

  - [x] 11.2 Clean up API key references from codebase
    - Remove any remaining imports or references to direct API keys in coordinators and services
    - Ensure no dead code paths remain that attempt to use the removed keys
    - Verify settings loader gracefully handles old config files with removed keys (no crash, no error)
    - _Requirements: 8.1, 8.3_

- [x] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation uses Python with `httpx` (sync) for HTTP communication, matching the desktop app's ThreadPoolExecutor threading model
- All new modules follow the Protocol-based dependency injection pattern established in the codebase
- HTTP mocking in tests uses `respx` library; DPAPI mocking uses simple base64 for cross-platform CI

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "6.1"] },
    { "id": 5, "tasks": ["6.2", "6.3", "6.4", "6.5", "7.1"] },
    { "id": 6, "tasks": ["7.2", "7.3", "7.4"] },
    { "id": 7, "tasks": ["9.1", "9.2", "9.3"] },
    { "id": 8, "tasks": ["9.4", "9.5"] },
    { "id": 9, "tasks": ["10.1"] },
    { "id": 10, "tasks": ["10.2", "10.3", "11.1"] },
    { "id": 11, "tasks": ["11.2"] }
  ]
}
```
