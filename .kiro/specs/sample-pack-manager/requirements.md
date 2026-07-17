# Requirements Document

## Introduction

Add Sample Pack Downloads and Sample Library Manager panels to the Desktop App's Preferences tab, replicating the exact functionality from the Electron app (`camxora/src/renderer/src/features/settings/SettingsWorkspacePage.tsx` → `renderSettingsTab()`). This includes downloading image sample packs from admin-managed URLs, extracting them into local sample directories, scanning those directories for available sample files, and providing an interactive curation UI for selecting up to 5 background and 5 thumbnail samples.

## Glossary

- **Sample_Pack**: A ZIP/archive file containing background or thumbnail sample images, hosted at an admin-managed URL and listed via the Platform API.
- **Sample_Library**: The local filesystem folders (BG samples dir, Thumb samples dir) containing extracted sample image files.
- **Curation**: The process of selecting up to 5 images from the available samples to use as the preferred subset for generation.
- **Image_Source_Mode**: "AI" (auto-generate) or "Manual" (user-provided files in batch folders).

## Requirements

### Requirement 1: Sample Pack List API Client

**User Story:** As a user, I want the Desktop App to fetch available sample packs from the Platform API, so that I can see what's available to download.

#### Acceptance Criteria

1. THE Desktop_App SHALL call `GET /image-sample-packs` via a service client to retrieve a list of available sample packs.
2. WHEN the response is received, THE Desktop_App SHALL categorize packs by type: "background" and "thumbnail".
3. THE Desktop_App SHALL display each pack's `name`, `notes`, and `source_value` (download URL).
4. IF the API call fails, THEN THE Desktop_App SHALL display an error message "Unable to load sample pack list." and allow retry.

### Requirement 2: Sample Pack Download & Extraction

**User Story:** As a user, I want to download and install a sample pack into my local samples directory, so that new samples are available for image generation.

#### Acceptance Criteria

1. WHEN the user selects a background pack and clicks "Install", THE Desktop_App SHALL download the file from `source_value` URL.
2. WHEN the download completes, THE Desktop_App SHALL extract the archive contents into the configured `imageBackgroundSamplesDir`.
3. WHEN the user selects a thumbnail pack and clicks "Install", THE Desktop_App SHALL download and extract into `imageThumbnailSamplesDir`.
4. WHILE a download/extraction is in progress, THE Desktop_App SHALL disable the Install button and show progress indication.
5. IF the destination directory is not configured (empty), THEN THE Desktop_App SHALL disable the Install button.
6. WHEN the user clicks "Open Link", THE Desktop_App SHALL open the pack's `source_value` URL in the system browser.

### Requirement 3: Sample Library Scanner

**User Story:** As a user, I want the Desktop App to scan my sample directories and show available image files, so that I can curate which samples to use.

#### Acceptance Criteria

1. WHEN the user opens the Preferences tab or clicks "Refresh Samples", THE Desktop_App SHALL scan `imageBackgroundSamplesDir` and `imageThumbnailSamplesDir` for image files (*.png, *.jpg, *.jpeg, *.webp).
2. THE Desktop_App SHALL display the list of found sample files by filename, sorted alphabetically.
3. IF no sample files are found in a directory, THE Desktop_App SHALL display "No background/thumbnail sample images found."

### Requirement 4: Sample Curation

**User Story:** As a user, I want to select up to 5 preferred samples from each category, so that image generation uses my curated subset.

#### Acceptance Criteria

1. WHEN the user clicks a sample file in the list, THE Desktop_App SHALL toggle its selection state (selected/deselected).
2. THE Desktop_App SHALL allow a maximum of 5 selected samples per category (background and thumbnail independently).
3. THE Desktop_App SHALL display "Selected N/5" count for each category.
4. THE Desktop_App SHALL persist the selected sample paths in the settings (`imageBgSamples` and `imageThumbSamples` arrays).
5. WHEN the user toggles "Random On/Off", THE Desktop_App SHALL persist `imageBgRandom` and `imageThumbRandom` boolean settings.
6. WHEN Random is On and samples are selected, generation SHALL use the selected subset first, then fall back to the full folder.

### Requirement 5: Sample Preview

**User Story:** As a user, I want to preview sample images by hovering or clicking them, so that I can make informed curation decisions.

#### Acceptance Criteria

1. WHEN the user hovers over a sample file in the list, THE Desktop_App SHALL display a preview of that image in the preview area.
2. WHEN the user clicks a sample file, THE Desktop_App SHALL keep that preview pinned until another is clicked.
3. THE Desktop_App SHALL display the preview at 16:7 aspect ratio.
4. THE Desktop_App SHALL show the full file path below the preview.
5. WHEN the user clicks "Open File", THE Desktop_App SHALL open the previewed file in the system file explorer.

## Reference

- Electron source: `camxora/src/renderer/src/features/settings/SettingsWorkspacePage.tsx` lines 2600-2950
- Platform API endpoint: `GET /api/v1/image-sample-packs` (already exists)
- Settings keys: `imageBgSamples`, `imageThumbSamples`, `imageBgRandom`, `imageThumbRandom`
