# Implementation Plan: Dynamic Text Overlay

## Overview

This plan implements a programmatic text overlay rendering system using Pillow/PIL as an alternative to AI-based thumbnail overlay generation. The implementation follows the existing project architecture — services for rendering logic, database layer for persistence, features for coordination, and views for UI. Each task builds incrementally, starting with the data model and renderer, then persistence, pipeline integration, and finally the UI layer.

## Tasks

- [x] 1. Create Text Style Preset data model and validation
  - [x] 1.1 Create `services/text_overlay_renderer.py` with `TextStylePreset` dataclass and `validate_preset` function
    - Define the `TextStylePreset` dataclass with all fields: name, font_path, font_size, primary_color, position, glow_color, glow_radius, shadow_offset_x, shadow_offset_y, shadow_color, stroke_width, stroke_color, gradient_enabled, gradient_start_color, gradient_end_color, line_spacing, alignment, max_text_width_pct, vertical_padding_pct
    - Set default values per requirements: glow_radius=0, shadow_offset=(0,0), stroke_width=0, gradient_enabled=False, line_spacing=1.4, alignment="center", max_text_width_pct=80, vertical_padding_pct=10
    - Implement `validate_preset()` that checks all field constraints (font_size 12–400, glow_radius 0–50, stroke_width 0–10, line_spacing 1.0–3.0, max_text_width_pct 20–90, vertical_padding_pct 2–30, position enum, alignment enum, RGBA hex format)
    - Return list of error messages (empty list = valid)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x]* 1.2 Write property test for preset field constraint validation
    - **Property 1: Preset field constraints are enforced**
    - Use Hypothesis to generate random TextStylePreset values and verify validate_preset correctly accepts/rejects based on field ranges
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

  - [x]* 1.3 Write property test for form input validation correctness
    - **Property 10: Form input validation correctness**
    - Generate random strings and integers for name, font_size, and color fields; verify validation rejects empty names, out-of-range font_size, and invalid hex color strings
    - **Validates: Requirements 5.5**

- [x] 2. Implement Font Manager
  - [x] 2.1 Create `services/font_manager.py` with `FontManager` class
    - Implement `__init__` accepting fonts_dir and optional default_font_path
    - Implement `load_font(font_path, size)` with font caching by (path, size) tuple
    - Implement fallback logic: if specified font file doesn't exist, fall back to bundled default sans-serif font
    - Implement `list_available_fonts()` scanning for .ttf and .otf files
    - Implement `is_available()` checking if fonts directory exists and has at least one font file
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 3. Implement Text Overlay Renderer
  - [x] 3.1 Implement `render_text_overlay()` function in `services/text_overlay_renderer.py`
    - Create transparent RGBA canvas at target resolution (width × height)
    - Render each track title on a separate line with line_spacing multiplier
    - Implement font size reduction loop: iteratively reduce font size when text exceeds max_text_width_pct
    - Position text block according to layout position parameter (top, center, bottom)
    - Apply horizontal alignment (left, center, right)
    - Return fully transparent image when titles list is empty
    - _Requirements: 3.1, 3.2, 3.3, 3.8, 3.9_

  - [x] 3.2 Implement text effects rendering (glow, stroke, shadow, gradient)
    - Implement shadow effect: render text copy at shadow_offset in shadow_color behind all other layers
    - Implement glow effect: render text in glow_color, apply Gaussian blur at glow_radius, composite behind main text
    - Implement stroke effect: render text outline at stroke_width and stroke_color behind main text fill
    - Implement gradient fill: when gradient_enabled, fill text with vertical linear gradient from gradient_start_color to gradient_end_color instead of solid primary_color
    - Layer ordering: shadow → glow → stroke → fill (back to front)
    - _Requirements: 3.4, 3.5, 3.6, 3.7_

  - [x]* 3.3 Write property test for rendering round-trip validity
    - **Property 4: Rendering round-trip produces valid RGBA PNG**
    - Generate random valid presets and non-empty title lists; verify output is valid RGBA Image at exact target dimensions
    - **Validates: Requirements 3.1, 3.10**

  - [x]* 3.4 Write property test for multi-line vertical distribution
    - **Property 5: Multi-line rendering places N titles across N vertical regions**
    - Generate lists of N titles; verify N distinct vertical bands of non-transparent pixels
    - **Validates: Requirements 3.2**

  - [x]* 3.5 Write property test for max width constraint
    - **Property 6: Rendered text never exceeds max width constraint**
    - Generate presets and long titles; verify non-transparent pixel bounding box stays within max_text_width_pct
    - **Validates: Requirements 3.3**

  - [x]* 3.6 Write property test for text position placement
    - **Property 7: Text position matches layout setting**
    - Generate presets with each position value; verify vertical center of mass falls in expected region
    - **Validates: Requirements 3.8**

- [x] 4. Checkpoint - Core rendering validated
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Preset Database Layer
  - [x] 5.1 Create `database/preset_db.py` with table creation and seed functions
    - Implement `create_text_style_presets_table(cfg)` with all columns per the design schema (id, name, font_path, font_size, primary_color, position, all effect/gradient/layout columns, used_count, used_at, created_at, updated_at)
    - Implement `seed_default_presets(cfg)` inserting "Neon Glow", "Bold Modern", and "Streetwear" built-in presets if not already present
    - Call table creation and seeding from the application migration pathway
    - _Requirements: 2.1, 2.5_

  - [x] 5.2 Implement preset CRUD operations in `database/preset_db.py`
    - Implement `upsert_text_style_preset(cfg, preset)` — insert or update by name, return saved record
    - Implement `delete_text_style_preset(cfg, preset_id)` — remove record by ID
    - Implement `list_text_style_presets(cfg)` — return all presets ordered by name ASC
    - Implement `pick_least_used_text_preset(cfg, exclude_ids)` — select preset with lowest used_count, increment used_count and set used_at
    - _Requirements: 2.2, 2.3, 2.4, 4.2_

  - [x]* 5.3 Write property test for preset upsert idempotence
    - **Property 2: Preset upsert idempotence**
    - Generate random preset names and two distinct value sets; verify double upsert results in single record with second values
    - **Validates: Requirements 2.2**

  - [x]* 5.4 Write property test for preset listing order
    - **Property 3: Preset listing is ordered by name**
    - Generate random preset names; verify list returns case-insensitive alphabetical order
    - **Validates: Requirements 2.4**

  - [x]* 5.5 Write property test for least-used rotation
    - **Property 8: Least-used rotation selects minimum used_count**
    - Generate presets with varying used_count values; verify minimum is selected and incremented
    - **Validates: Requirements 4.2**

- [x] 6. Implement Profile Thumbnail Mode Configuration
  - [x] 6.1 Extend profile image config to include `thumbnailOverlayMode` field
    - Add `"thumbnailOverlayMode"` key to the `image_config` JSONB field on profiles, defaulting to `"ai"`
    - Create helper function `_get_thumbnail_overlay_mode(db_cfg, profile_id, settings)` that reads the profile's config and returns mode string
    - Ensure existing profiles default to `"ai"` when the field is absent
    - _Requirements: 6.1, 6.3_

- [x] 7. Implement Pipeline Integration
  - [x] 7.1 Add preset-text thumbnail path to `services/image_generation.py`
    - In `_run_one_image_job()`, after determining `kind == "thumbnail"`, check profile's `thumbnailOverlayMode`
    - When mode is `"preset_text"`: retrieve track titles via `list_songs_by_batch_id`, pick least-used preset, call `render_text_overlay`, apply `_scale_overlay_center(overlay, 0.91)`, composite onto bg_cover, save, and mark job ready
    - When mode is `"ai"`: existing AI flow unchanged (FAL/SLAI provider, chroma-key, compositing)
    - Skip AI provider call, chroma-key step, and black-background input preparation for preset-text jobs
    - Initialize FontManager with fonts directory from application settings
    - _Requirements: 4.1, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x]* 7.2 Write property test for overlay scaling centering
    - **Property 9: Overlay scaling preserves centering**
    - Generate random RGBA overlay images; verify `_scale_overlay_center(overlay, 0.91)` preserves dimensions and centers content
    - **Validates: Requirements 4.3**

  - [x]* 7.3 Write unit tests for pipeline mode routing
    - Test that `_get_thumbnail_overlay_mode` returns correct mode for each profile config
    - Test that preset-text path skips AI provider call
    - Test that AI path remains unchanged when mode is "ai"
    - _Requirements: 4.1, 4.6, 4.8_

- [x] 8. Checkpoint - Backend integration complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement Preset Manager Coordinator
  - [x] 9.1 Create `features/text_presets/` package with coordinator
    - Create `features/text_presets/__init__.py`
    - Create `features/text_presets/coordinator.py` with `TextPresetManagerCoordinator` class
    - Implement `load_presets()` — loads all presets for UI display
    - Implement `save_preset(preset_data)` — validates and persists, raises ValidationError on invalid input
    - Implement `delete_preset(preset_id)` — removes preset from database
    - Implement `render_preview(preset_data, sample_text, width, height)` — renders preview image for UI form
    - Implement `has_presets()` — returns True if at least one preset exists (for mode switch validation)
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.6, 6.5_

- [x] 10. Implement Preset Manager UI
  - [x] 10.1 Create Preset Manager dialog in `views/` layer
    - Create preset list widget showing scrollable list of all presets with name and primary color indicator
    - Implement "Add Preset" button opening form dialog with all fields (name, font path dropdown, font size, colors, effects, layout)
    - Implement "Edit" button opening form dialog pre-populated with existing values
    - Implement "Delete" button with confirmation prompt
    - Ensure list supports 100+ presets without performance degradation (use virtual scrolling or lazy rendering)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.8_

  - [x] 10.2 Implement live preview in preset form dialog
    - Add preview panel to the form dialog rendering "Track Title Preview" text with current form values
    - Update preview dynamically as user modifies fields
    - Use `TextPresetManagerCoordinator.render_preview()` for rendering
    - Display font dropdown populated from `FontManager.list_available_fonts()`
    - Show "No custom fonts available" message when fonts directory is empty or missing
    - _Requirements: 5.6, 7.3, 7.5_

  - [x] 10.3 Add "Text Presets" button to Image workspace page
    - Add "Text Presets" button in the Thumbnail Samples section of `views/image_view.py`
    - Wire button click to open the Preset Manager dialog
    - _Requirements: 5.7_

- [x] 11. Implement Profile Settings UI for Thumbnail Mode
  - [x] 11.1 Add thumbnail overlay mode dropdown to profile settings
    - Add dropdown in profile image settings section with options "AI (FAL/SLAI)" and "Preset Text (Local)"
    - Save selected mode to profile's `image_config["thumbnailOverlayMode"]` field
    - Validate at least one preset exists before allowing switch to "preset_text" — show error message if none exist
    - _Requirements: 6.2, 6.4, 6.5_

- [x] 12. Implement Manual Thumbnail Generation from Video Page
  - [x] 12.1 Add "Generate Thumbnail" button to Video page
    - Add "Generate Thumbnail" button in `views/video_view.py` for the currently selected track/batch
    - When clicked, create a Thumbnail_Job using the profile's configured Thumbnail_Mode
    - Check for existing Background_Image — display error toast if none exists
    - Generated thumbnail appears in job queue on Image page following same flow as automatic generation
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 13. Final checkpoint - Full feature validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after core rendering and pipeline integration
- Property tests validate universal correctness properties from the design document
- The project uses Python with Pillow/PIL for rendering, PostgreSQL for persistence, PyQt6 for UI, and Hypothesis for property-based testing
- The Font Manager and Text Overlay Renderer are pure services with no database access — easy to test in isolation
- Pipeline integration reuses the existing `_scale_overlay_center` and `Image.alpha_composite` calls with the same overlay artifact type

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "3.1"] },
    { "id": 2, "tasks": ["3.2"] },
    { "id": 3, "tasks": ["3.3", "3.4", "3.5", "3.6", "5.1"] },
    { "id": 4, "tasks": ["5.2", "6.1"] },
    { "id": 5, "tasks": ["5.3", "5.4", "5.5", "7.1"] },
    { "id": 6, "tasks": ["7.2", "7.3", "9.1"] },
    { "id": 7, "tasks": ["10.1", "11.1", "12.1"] },
    { "id": 8, "tasks": ["10.2", "10.3"] }
  ]
}
```
