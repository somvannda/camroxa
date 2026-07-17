# Implementation Plan: Sample Pack Manager

## Overview

Implement the Sample Pack Downloads and Sample Library Manager feature following the coordinator pattern. The feature lives at `features/sample_pack/` with UI handlers at `app/sample_pack_ui_handlers.py`. All components use protocol-based DI, worker threads for I/O, and the event bus for UI updates.

## Tasks

- [x] 1. Set up feature module structure and domain models
  - [x] 1.1 Create `features/sample_pack/` package with domain models and protocols
    - Create `features/sample_pack/__init__.py` with public exports
    - Create `features/sample_pack/models.py` with `SamplePackInfo`, `SampleFileInfo`, and `DownloadResult` frozen dataclasses
    - Create `features/sample_pack/protocols.py` with `SamplePackApiClientPort`, `SamplePackDownloaderPort`, and `SampleLibraryScannerPort` protocols
    - _Requirements: 1.1, 2.1, 3.1_

- [x] 2. Implement SamplePackApiClient
  - [x] 2.1 Implement the API client for fetching sample packs
    - Create `features/sample_pack/api_client.py`
    - Implement `SamplePackApiClient` class with httpx, following `GenerationProxy` pattern
    - Handle token-based auth via `TokenStorePort` and `AuthClientPort`
    - Implement `list_packs()` with 401 retry logic and categorization into background/thumbnail groups
    - Raise typed `NetworkError` / `AuthenticationError` on failures
    - _Requirements: 1.1, 1.2, 1.4_

  - [ ]* 2.2 Write property test for pack list categorization
    - **Property 1: Pack list categorization preserves data and groups correctly**
    - **Validates: Requirements 1.2, 1.3**

  - [ ]* 2.3 Write unit tests for SamplePackApiClient
    - Test successful pack list fetch and parsing
    - Test 401 handling with token refresh and retry
    - Test network error → `NetworkError` raised with correct message
    - Test empty response handling
    - _Requirements: 1.1, 1.4_

- [x] 3. Implement SamplePackDownloader
  - [x] 3.1 Implement the downloader with ZIP extraction
    - Create `features/sample_pack/downloader.py`
    - Implement `SamplePackDownloader` class with stream download (8KB chunks)
    - Implement ZIP validation and extraction of image files only (.png, .jpg, .jpeg, .webp)
    - Implement Google Drive URL normalization (`_normalize_google_drive_url`)
    - Implement progress callback and cancellation support
    - Clean up temp files on success or failure
    - Return `DownloadResult` with success status and file count
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 3.2 Write property test for ZIP extraction round-trip
    - **Property 2: ZIP extraction round-trip**
    - **Validates: Requirements 2.2, 2.3**

  - [ ]* 3.3 Write unit tests for SamplePackDownloader
    - Test Google Drive URL normalization for various share link formats
    - Test download cancellation mid-stream
    - Test invalid/corrupt ZIP handling → `DownloadResult(success=False)`
    - Test non-image file skipping during extraction
    - _Requirements: 2.1, 2.2, 2.3_

- [x] 4. Implement SampleLibraryScanner
  - [x] 4.1 Implement the directory scanner
    - Create `features/sample_pack/scanner.py`
    - Implement `SampleLibraryScanner` class wrapping existing `list_images_in_folder()`
    - Filter to supported extensions (.png, .jpg, .jpeg, .webp)
    - Sort results alphabetically (case-insensitive) by filename
    - Return empty list for missing/invalid directories without error
    - Return `list[SampleFileInfo]` with absolute path and filename
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 4.2 Write property test for scanner filtering and sorting
    - **Property 3: Scanner returns only supported images, sorted alphabetically**
    - **Validates: Requirements 3.1, 3.2**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement SamplePackCoordinator
  - [x] 6.1 Implement the coordinator with pack fetching and install logic
    - Create `features/sample_pack/coordinator.py`
    - Implement `SamplePackCoordinator` with constructor DI for all dependencies
    - Implement `fetch_packs()` running on worker thread, emitting `packs_loaded` / `packs_load_failed` events
    - Implement `get_cached_packs()` returning categorized pack dict
    - Implement `install_pack(pack_id, category)` with pre-validation (dir configured, not already installing)
    - Run download/extract on worker thread, emit progress/completed/failed events
    - Auto-call `refresh_library()` after successful install
    - _Requirements: 1.1, 1.2, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 6.2 Implement library scanning and curation logic in the coordinator
    - Implement `refresh_library()` scanning both background and thumbnail dirs
    - Implement `toggle_sample(category, file_path)` with max-5 enforcement
    - Implement `get_selected_samples(category)` and `get_selection_count(category)`
    - Implement `set_random_mode(category, enabled)` and `get_random_mode(category)`
    - Persist selections to settings via `settings_updater` on every change
    - Emit `library_refreshed` event after scan
    - _Requirements: 3.1, 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 6.3 Write property test for toggle self-inverse
    - **Property 4: Toggle is self-inverse**
    - **Validates: Requirements 4.1**

  - [ ]* 6.4 Write property test for selection count invariant
    - **Property 5: Selection count invariant**
    - **Validates: Requirements 4.2, 4.3**

  - [ ]* 6.5 Write property test for selection persistence round-trip
    - **Property 6: Selection persistence round-trip**
    - **Validates: Requirements 4.4**

  - [ ]* 6.6 Write unit tests for coordinator
    - Test install button disabled when destination dir is empty
    - Test install rejected while another install is in progress
    - Test successful install flow emits correct event sequence
    - Test toggle at max count returns False and state unchanged
    - Test random mode persistence
    - _Requirements: 2.4, 2.5, 4.2, 4.5_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement UI handlers and preview widget
  - [x] 8.1 Create the Sample Preview Widget
    - Create `app/sample_pack_ui_handlers.py` (or split if preferred)
    - Implement `SamplePreviewWidget` as a QLabel container with 16:7 aspect ratio
    - Support `show_preview(file_path)` loading QPixmap scaled to aspect ratio
    - Support `clear_preview()` showing placeholder text
    - Display full file path below the preview
    - Add "Open File" button calling `QDesktopServices.openUrl()` or `os.startfile()`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 8.2 Implement SamplePackUIHandlers wiring
    - Wire "Reload Packs" button → `coordinator.fetch_packs()`
    - Wire "Install" buttons → `coordinator.install_pack()` with disable/enable on progress
    - Wire "Refresh Samples" button → `coordinator.refresh_library()`
    - Wire sample list item clicks → `coordinator.toggle_sample()` and pin preview
    - Wire hover events → `preview_widget.show_preview()`
    - Wire random toggle buttons → `coordinator.set_random_mode()`
    - Wire "Open Link" button → `webbrowser.open(source_value)`
    - Listen to event bus → update widget states (progress bar, button enable, lists)
    - Display "Selected N/5" count per category
    - Display "No background/thumbnail sample images found." when list is empty
    - _Requirements: 1.3, 2.4, 2.5, 2.6, 3.1, 3.3, 4.1, 4.2, 4.3, 4.5, 5.1, 5.2_

- [x] 9. Wire feature into Preferences tab
  - [x] 9.1 Register coordinator and connect to Preferences tab
    - Instantiate `SamplePackApiClient`, `SamplePackDownloader`, `SampleLibraryScanner`
    - Instantiate `SamplePackCoordinator` with all dependencies injected
    - Add Sample Pack Downloads panel and Sample Library Manager panel to Preferences tab UI
    - Wire `SamplePackUIHandlers` to the coordinator and Preferences tab widgets
    - Trigger `fetch_packs()` and `refresh_library()` on Preferences tab open
    - _Requirements: 1.1, 3.1_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties defined in the design document
- Unit tests validate specific examples and edge cases
- All I/O operations (network, filesystem) run on worker threads — never block the Qt event loop
- The coordinator has zero Qt imports; all UI interaction flows through the event bus and handler layer

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "3.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.2", "3.3", "4.2"] },
    { "id": 3, "tasks": ["6.1"] },
    { "id": 4, "tasks": ["6.2"] },
    { "id": 5, "tasks": ["6.3", "6.4", "6.5", "6.6"] },
    { "id": 6, "tasks": ["8.1", "8.2"] },
    { "id": 7, "tasks": ["9.1"] }
  ]
}
```
