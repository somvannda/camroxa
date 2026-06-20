# Requirements Document

## Introduction

This feature adds FAL (fal.ai) as an additional image generation provider alongside the existing SLAI provider. Users can independently select which provider to use for background image generation and thumbnail image generation, and configure a FAL API key in the settings. The FAL provider follows the same structural pattern as the existing SLAI provider, using the FAL Flux Schnell image generation API.

## Glossary

- **Image_Generation_Service**: The service layer (`image_generation.py`) that orchestrates image job execution by delegating to the selected provider.
- **FAL_Provider**: A new provider module (`image_provider_fal.py`) that calls the fal.ai Flux Schnell API to generate images from a prompt and base image.
- **SLAI_Provider**: The existing provider module (`image_provider_slai.py`) that calls the SLAI API to generate images.
- **Settings_Accessor**: The callable that returns the current application settings dictionary.
- **Image_Coordinator**: The coordinator (`features/image/coordinator.py`) that manages image generation workflows and polling.
- **Settings_UI**: The settings panel UI where users configure API keys and provider selections.
- **Background_Image**: A full-resolution image generated as the primary visual for a music release.
- **Thumbnail_Image**: A composited image overlaying AI-generated text/graphics onto a background for use as a video thumbnail.

## Requirements

### Requirement 1: FAL API Key Setting

**User Story:** As a user, I want to add and store a FAL API key in the application settings, so that the FAL provider can authenticate requests to the fal.ai API.

#### Acceptance Criteria

1. THE Settings_UI SHALL display a FAL API Key input field in the API Keys settings section.
2. THE Settings_Accessor SHALL persist the FAL API key under the setting key `falImgApiKey`.
3. WHEN the user saves settings with a FAL API key value, THE Settings_Accessor SHALL store the value and make it available to the Image_Generation_Service.
4. THE Settings_UI SHALL mask the FAL API key input as a password field.

### Requirement 2: Background Image Provider Selection

**User Story:** As a user, I want to choose between SLAI and FAL for background image generation, so that I can use whichever AI provider produces better results for my background images.

#### Acceptance Criteria

1. THE Settings_UI SHALL display a provider selection dropdown for background image generation with options "SLAI" and "FAL".
2. THE Settings_Accessor SHALL persist the background image provider selection under the setting key `imageBackgroundProvider`.
3. WHEN the background image provider setting is empty or missing, THE Image_Generation_Service SHALL default to "slai".
4. WHEN a background image job executes, THE Image_Generation_Service SHALL delegate the request to the provider specified by `imageBackgroundProvider`.

### Requirement 3: Thumbnail Image Provider Selection

**User Story:** As a user, I want to choose between SLAI and FAL for thumbnail image generation, so that I can use whichever AI provider produces better results for my thumbnail overlays.

#### Acceptance Criteria

1. THE Settings_UI SHALL display a provider selection dropdown for thumbnail image generation with options "SLAI" and "FAL".
2. THE Settings_Accessor SHALL persist the thumbnail image provider selection under the setting key `imageThumbnailProvider`.
3. WHEN the thumbnail image provider setting is empty or missing, THE Image_Generation_Service SHALL default to "slai".
4. WHEN a thumbnail image job executes, THE Image_Generation_Service SHALL delegate the request to the provider specified by `imageThumbnailProvider`.

### Requirement 4: FAL Provider Implementation

**User Story:** As a developer, I want a FAL provider module that follows the same interface pattern as the SLAI provider, so that image generation can be delegated to FAL without changing the coordination logic.

#### Acceptance Criteria

1. THE FAL_Provider SHALL expose a function `fal_generate_image_png_bytes` with the same parameter signature as `slai_generate_image_png_bytes` (api_key, model, prompt, image_png_bytes, resolution, timeout_sec).
2. THE FAL_Provider SHALL call the fal.ai Flux Schnell API endpoint to generate images.
3. THE FAL_Provider SHALL return valid PNG image bytes on success.
4. IF the FAL API key is not configured, THEN THE FAL_Provider SHALL raise a RuntimeError with a descriptive message.
5. IF the FAL API returns an error response, THEN THE FAL_Provider SHALL raise a RuntimeError containing the HTTP status and error details.
6. IF the FAL API request times out, THEN THE FAL_Provider SHALL raise a RuntimeError indicating a timeout occurred.

### Requirement 5: Provider Routing in Image Generation Service

**User Story:** As a developer, I want the image generation service to route requests to the correct provider based on the job kind (background vs thumbnail) and the corresponding provider setting, so that each image type uses the user-selected provider.

#### Acceptance Criteria

1. WHEN processing a background image job, THE Image_Generation_Service SHALL read the `imageBackgroundProvider` setting and call the corresponding provider function.
2. WHEN processing a thumbnail image job, THE Image_Generation_Service SHALL read the `imageThumbnailProvider` setting and call the corresponding provider function.
3. WHEN the selected provider is "fal", THE Image_Generation_Service SHALL use the `falImgApiKey` setting for authentication.
4. WHEN the selected provider is "slai", THE Image_Generation_Service SHALL use the `slaiImgApiKey` setting for authentication.
5. IF the API key for the selected provider is missing, THEN THE Image_Generation_Service SHALL raise an error indicating which provider key is missing.

### Requirement 6: Coordinator API Key Validation

**User Story:** As a user, I want the image coordinator to check that the selected provider has a valid API key before starting image generation, so that jobs do not fail immediately due to missing credentials.

#### Acceptance Criteria

1. WHEN the Image_Coordinator checks whether image generation is available, THE Image_Coordinator SHALL verify that the API key for at least one configured provider (background or thumbnail) is present.
2. WHEN a manual image poll is triggered and the background provider API key is missing, THE Image_Coordinator SHALL display a status message naming the missing provider key.
3. WHEN auto-poll timer syncs, THE Image_Coordinator SHALL consider image generation available if the API key for the background provider is present.

### Requirement 7: Default Settings for FAL Provider

**User Story:** As a user, I want sensible defaults for the FAL provider settings, so that I only need to enter my API key to start using FAL.

#### Acceptance Criteria

1. THE Settings_Accessor SHALL default `falImgApiKey` to an empty string.
2. THE Settings_Accessor SHALL default `imageBackgroundProvider` to "slai".
3. THE Settings_Accessor SHALL default `imageThumbnailProvider` to "slai".
