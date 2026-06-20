# Implementation Plan: FAL Image Provider

## Overview

This plan implements the FAL (fal.ai Flux Schnell) image generation provider alongside the existing SLAI provider. The implementation adds settings for a FAL API key and per-job-kind provider selection, creates the FAL provider module, updates routing logic in the image generation service, and updates the coordinator's API key validation. Tasks build incrementally: settings and data model first, then the provider, then routing, then coordinator updates, and finally UI wiring.

## Tasks

- [x] 1. Add FAL settings to data model and settings extraction
  - [x] 1.1 Add default settings entries in `python_app/models/music_model.py`
    - Add `"falImgApiKey": ""`, `"imageBackgroundProvider": "slai"`, and `"imageThumbnailProvider": "slai"` to `DEFAULT_SETTINGS`
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 1.2 Update settings extraction in `python_app/features/music/settings.py`
    - Add extraction of `falImgApiKey`, `imageBackgroundProvider`, and `imageThumbnailProvider` in `extract_music_settings()`
    - Map to widget names: `music_settings_fal_img_key`, `music_settings_image_bg_provider`, `music_settings_image_thumb_provider`
    - _Requirements: 1.2, 1.3, 2.2, 3.2_

- [x] 2. Implement FAL provider module
  - [x] 2.1 Create `python_app/services/image_provider_fal.py`
    - Implement `fal_generate_image_png_bytes` with keyword-only parameters: `api_key`, `model`, `prompt`, `image_png_bytes`, `resolution`, `timeout_sec`
    - Validate API key is non-empty (raise RuntimeError if missing)
    - Parse resolution string into width/height integers
    - Submit queue request to `https://queue.fal.run/fal-ai/flux/schnell` with Authorization header
    - Poll status URL until COMPLETED or timeout
    - Download image from result URL, validate PNG magic bytes
    - Return raw PNG bytes
    - Implement retry logic: 2 retries on 5xx for submission, 3 retries with exponential backoff for image download
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ]* 2.2 Write property test for FAL provider — valid PNG return
    - **Property 4: FAL provider returns valid PNG on success**
    - Mock HTTP responses to simulate successful FAL API flow (queue submit → status COMPLETED → image download)
    - Use Hypothesis to generate random valid PNG byte sequences
    - Assert returned bytes start with PNG magic bytes `\x89PNG\r\n\x1a\n`
    - **Validates: Requirements 4.3**

  - [ ]* 2.3 Write property test for FAL provider — error propagation
    - **Property 6: FAL error response propagation**
    - Use Hypothesis to generate random HTTP status codes in range 400–599 and random error body text
    - Mock FAL API to return the error response
    - Assert RuntimeError is raised and message contains both the status code and error body text
    - **Validates: Requirements 4.5**

  - [ ]* 2.4 Write property test for FAL provider — missing API key error
    - **Property 5: Missing API key raises descriptive error (FAL provider portion)**
    - Use Hypothesis to generate empty/whitespace-only API key variants
    - Call `fal_generate_image_png_bytes` with generated key
    - Assert RuntimeError is raised with message identifying FAL as the provider
    - **Validates: Requirements 4.4**

- [x] 3. Checkpoint - Ensure FAL provider tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement provider routing in image generation service
  - [x] 4.1 Add `_resolve_provider` helper in `python_app/services/image_generation.py`
    - Accept `kind` ("background" or "thumbnail") and `settings` dict
    - Read `imageBackgroundProvider` or `imageThumbnailProvider` based on kind
    - Default to "slai" if setting is empty or missing
    - Return tuple of (provider_function, api_key)
    - Raise RuntimeError if API key for selected provider is missing
    - _Requirements: 2.3, 2.4, 3.3, 3.4, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 4.2 Update `_run_one_image_job` to use `_resolve_provider`
    - Replace hardcoded SLAI provider call with `_resolve_provider` routing
    - Pass the resolved API key and provider function
    - Determine job kind from job metadata (background vs thumbnail)
    - _Requirements: 5.1, 5.2_

  - [ ]* 4.3 Write property test for provider routing correctness
    - **Property 2: Provider routing correctness**
    - Use Hypothesis to generate random (job_kind, provider_setting) pairs from {"background", "thumbnail"} × {"slai", "fal"}
    - Mock both provider functions, invoke `_resolve_provider`, assert correct function selected
    - **Validates: Requirements 2.4, 3.4, 5.1, 5.2**

  - [ ]* 4.4 Write property test for API key selection by provider
    - **Property 3: API key selection by provider**
    - Use Hypothesis to generate random (provider, fal_key, slai_key) tuples
    - Mock provider functions, run routing, assert correct API key is passed
    - **Validates: Requirements 5.3, 5.4**

  - [ ]* 4.5 Write property test for missing API key in service
    - **Property 5: Missing API key raises descriptive error (service portion)**
    - Use Hypothesis to generate random (provider ∈ {"slai", "fal"}, empty_key_variant)
    - Call `_resolve_provider` and assert RuntimeError with provider name in message
    - **Validates: Requirements 5.5**

- [x] 5. Checkpoint - Ensure routing tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Update image coordinator API key validation
  - [x] 6.1 Update `trigger_image_poll` in `python_app/features/image/coordinator.py`
    - Check API key based on the selected background provider (`imageBackgroundProvider`)
    - If background provider is "fal", check `falImgApiKey`; if "slai", check `slaiImgApiKey`
    - Display status message naming the missing provider key when absent
    - _Requirements: 6.1, 6.2_

  - [x] 6.2 Update `sync_auto_poll_timer` in `python_app/features/image/coordinator.py`
    - Consider image generation available if the API key for the selected background provider is present
    - _Requirements: 6.3_

  - [ ]* 6.3 Write property test for coordinator availability logic
    - **Property 7: Coordinator availability reflects selected provider's key**
    - Use Hypothesis to generate random (provider ∈ {"slai", "fal"}, key_present: bool) combinations
    - Mock settings, verify coordinator considers generation available iff selected provider's key is non-empty
    - **Validates: Requirements 6.1, 6.2, 6.3**

- [x] 7. Add UI widgets for FAL settings
  - [x] 7.1 Add FAL API key field and provider dropdowns in `python_app/app/music_ui_handlers.py`
    - Create `music_settings_fal_img_key` QLineEdit with `QLineEdit.Password` echo mode
    - Create `music_settings_image_bg_provider` QComboBox with items: ("SLAI", "slai"), ("FAL", "fal")
    - Create `music_settings_image_thumb_provider` QComboBox with items: ("SLAI", "slai"), ("FAL", "fal")
    - Place in the API Keys / Image settings section of the settings panel
    - _Requirements: 1.1, 1.4, 2.1, 3.1_

  - [x] 7.2 Update `populate_suno_settings_ui` in `python_app/features/music/settings.py`
    - Populate FAL API key field value from settings
    - Set background provider dropdown to current setting value
    - Set thumbnail provider dropdown to current setting value
    - _Requirements: 1.3, 2.2, 3.2_

  - [ ]* 7.3 Write unit tests for settings round-trip
    - **Property 1: Settings persistence round-trip**
    - Use Hypothesis to generate random string values for `falImgApiKey`, random valid provider values for `imageBackgroundProvider` and `imageThumbnailProvider`
    - Store via settings accessor, read back, assert equality
    - **Validates: Requirements 1.2, 1.3, 2.2, 3.2**

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The FAL provider mirrors the SLAI provider's function signature for seamless routing
- Python `hypothesis` library is used for property-based tests (already present in project)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "7.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "7.2"] },
    { "id": 3, "tasks": ["4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "4.4", "4.5"] },
    { "id": 5, "tasks": ["6.1", "6.2"] },
    { "id": 6, "tasks": ["6.3", "7.3"] }
  ]
}
```
