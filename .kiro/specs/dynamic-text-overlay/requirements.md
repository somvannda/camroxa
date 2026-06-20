# Requirements Document

## Introduction

This feature adds a programmatic text overlay option for thumbnail generation using Pillow/PIL, as an alternative to the existing AI-based overlay. Users can define unlimited text style presets with rich visual effects (neon glow, gradients, strokes, shadows). When enabled, the system automatically selects a random preset to render track titles onto the AI-generated background image — producing the final thumbnail and placing it in the same output directory as the current flow. The AI-based thumbnail generation remains fully intact; users can switch between "Preset Text" and "AI" modes per profile. The generated thumbnails appear in the existing job queue on the Image page, and manual thumbnail generation is also available on the Video page.

## Glossary

- **Text_Overlay_Renderer**: The Pillow-based service that renders text content onto a transparent PNG canvas using a specified style preset.
- **Text_Style_Preset**: A named configuration defining all visual properties for text rendering — font, size, colors, effects (glow, shadow, stroke), position, and layout rules. Users can create unlimited presets (100+).
- **Preset_Manager**: The UI component and persistence layer for creating, reading, updating, and deleting Text_Style_Presets.
- **Overlay_Image**: A transparent PNG image containing only the rendered text, suitable for alpha compositing onto a background image.
- **Track_Title_List**: The ordered list of song titles associated with a batch, sourced from the suno_tasks database table.
- **Image_Generation_Pipeline**: The existing service at `image_generation.py` that produces background and thumbnail images for music batches.
- **Thumbnail_Job**: An image job record of kind "thumbnail" that is enqueued and processed by the Image_Generation_Pipeline.
- **Thumbnail_Mode**: The per-profile setting that controls whether thumbnail overlays are generated via "AI" (existing FAL/SLAI flow) or "Preset Text" (programmatic rendering).
- **Background_Image**: The AI-generated background image produced by FAL/SLAI; used as the base for thumbnail compositing but NOT used for video export (video export uses the background image directly).

## Requirements

### Requirement 1: Text Style Preset Data Model

**User Story:** As a user, I want to define text style presets with rich visual properties, so that I can achieve specific aesthetic effects (neon glow, bold streetwear, etc.) without relying on AI generation.

#### Acceptance Criteria

1. THE Text_Style_Preset SHALL store a unique name, font family path, font size (in pixels), primary color (RGBA hex), and layout position (top, center, bottom, or custom coordinates).
2. THE Text_Style_Preset SHALL store optional effect parameters: glow color (RGBA hex), glow radius (integer pixels 0–50), shadow offset (x, y integer pixels), shadow color (RGBA hex), stroke width (integer pixels 0–10), and stroke color (RGBA hex).
3. THE Text_Style_Preset SHALL store optional gradient parameters: a boolean gradient flag, gradient start color (RGBA hex), and gradient end color (RGBA hex).
4. THE Text_Style_Preset SHALL store layout parameters: line spacing multiplier (float 1.0–3.0), horizontal alignment (left, center, right), maximum text width as a percentage of canvas width (integer 20–90), and vertical padding as a percentage of canvas height (integer 2–30).
5. WHEN a Text_Style_Preset is created without optional effect parameters, THE Preset_Manager SHALL default glow radius to 0, shadow offset to (0, 0), stroke width to 0, gradient flag to false, line spacing to 1.4, horizontal alignment to center, maximum text width to 80, and vertical padding to 10.
6. THE Text_Style_Preset data model SHALL support an unlimited number of user-created presets with no cap on the total count.

### Requirement 2: Preset Persistence

**User Story:** As a user, I want my text style presets saved to the database, so that they persist across application sessions and can be reused for future thumbnails.

#### Acceptance Criteria

1. THE Preset_Manager SHALL persist Text_Style_Presets in a PostgreSQL table with columns for each style property, plus a used_count and used_at column for rotation tracking.
2. WHEN a Text_Style_Preset with the same name already exists, THE Preset_Manager SHALL update the existing record rather than creating a duplicate.
3. WHEN a Text_Style_Preset is deleted, THE Preset_Manager SHALL remove the record from the database.
4. THE Preset_Manager SHALL provide a function to list all Text_Style_Presets ordered by name.
5. THE Preset_Manager SHALL seed the database with at least three built-in presets on first migration: "Neon Glow" (cyan glow effect, dark background optimized), "Bold Modern" (large white sans-serif, strong stroke), and "Streetwear" (condensed uppercase, gradient fill).

### Requirement 3: Text Overlay Rendering

**User Story:** As a user, I want the system to render track titles as a styled text overlay image, so that thumbnails have readable, aesthetically consistent typography without AI costs.

#### Acceptance Criteria

1. WHEN the Text_Overlay_Renderer receives a Track_Title_List and a Text_Style_Preset, THE Text_Overlay_Renderer SHALL produce an Overlay_Image as a transparent RGBA PNG at the target resolution.
2. THE Text_Overlay_Renderer SHALL render each track title on a separate line, respecting the line spacing multiplier from the preset.
3. WHEN the rendered text exceeds the maximum text width percentage, THE Text_Overlay_Renderer SHALL reduce the font size iteratively until all lines fit within the maximum width constraint.
4. THE Text_Overlay_Renderer SHALL apply glow effect by rendering the text in the glow color at the specified glow radius using Gaussian blur composited behind the main text.
5. THE Text_Overlay_Renderer SHALL apply stroke effect by rendering the text outline at the specified stroke width and stroke color behind the main text fill.
6. WHEN the gradient flag is true, THE Text_Overlay_Renderer SHALL fill the text with a vertical linear gradient from gradient start color to gradient end color instead of the primary solid color.
7. THE Text_Overlay_Renderer SHALL apply shadow effect by rendering a copy of the text at the shadow offset in the shadow color behind all other text layers.
8. THE Text_Overlay_Renderer SHALL position the text block according to the layout position parameter: top (top padding from top edge), center (vertically centered), or bottom (bottom padding from bottom edge).
9. WHEN the Track_Title_List is empty, THE Text_Overlay_Renderer SHALL produce a fully transparent Overlay_Image with no rendered content.
10. FOR ALL valid Text_Style_Presets and Track_Title_Lists, rendering then reading the Overlay_Image back SHALL produce a valid RGBA PNG with dimensions matching the target resolution (round-trip property).

### Requirement 4: Pipeline Integration

**User Story:** As a user, I want thumbnail generation to automatically use a randomly selected text style preset when configured, following the same output flow as AI-generated thumbnails (placed into the batch song directory, visible in the job queue).

#### Acceptance Criteria

1. WHEN a Thumbnail_Job is processed and the associated profile has Thumbnail_Mode set to "Preset Text", THE Image_Generation_Pipeline SHALL use the Text_Overlay_Renderer with a randomly selected Text_Style_Preset instead of calling the AI provider.
2. THE Image_Generation_Pipeline SHALL select the Text_Style_Preset randomly using least-used rotation logic (picking the preset with the lowest used_count) to distribute style variety across thumbnails.
3. WHEN the Text_Overlay_Renderer produces an Overlay_Image, THE Image_Generation_Pipeline SHALL composite the Overlay_Image onto the Background_Image using alpha compositing, matching the existing compositing behavior (scale to 91% and center).
4. THE Image_Generation_Pipeline SHALL save the final composited thumbnail image to the same output directory as the current flow (the batch song output directory) with the same naming convention.
5. THE Image_Generation_Pipeline SHALL mark the Thumbnail_Job as ready in the database after saving, using the existing mark_image_job_ready function.
6. WHEN a Thumbnail_Job is processed and the profile has Thumbnail_Mode set to "AI", THE Image_Generation_Pipeline SHALL use the existing AI-based overlay generation flow (FAL/SLAI provider call, chroma-key, compositing) with no changes.
7. THE Image_Generation_Pipeline SHALL retrieve the Track_Title_List for the batch from the database using the existing list_songs_by_batch_id function.
8. WHEN a Thumbnail_Job uses the Text_Overlay_Renderer, THE Image_Generation_Pipeline SHALL skip the AI provider call, the chroma-key step, and the black-background input preparation for that job.
9. THE generated thumbnail SHALL appear in the existing job queue table on the Image workspace page with the same status indicators as AI-generated thumbnails.

### Requirement 5: Preset Management UI

**User Story:** As a user, I want to manage text style presets from the application interface, so that I can create, edit, and delete presets and preview their appearance.

#### Acceptance Criteria

1. THE Preset_Manager UI SHALL display a scrollable list of all Text_Style_Presets with their name and a visual indicator of the primary color.
2. WHEN the user clicks "Add Preset", THE Preset_Manager UI SHALL open a form dialog with fields for all preset properties (name, font, size, colors, effects, layout).
3. WHEN the user clicks "Edit" on an existing preset, THE Preset_Manager UI SHALL open the form dialog pre-populated with the preset's current values.
4. WHEN the user clicks "Delete" on a preset, THE Preset_Manager UI SHALL prompt for confirmation and then remove the preset from the database.
5. WHEN the user saves a preset from the form dialog, THE Preset_Manager UI SHALL validate that the name is non-empty, font size is between 12 and 400, and all color values are valid RGBA hex strings before persisting.
6. THE Preset_Manager UI SHALL display a live preview rendering sample text ("Track Title Preview") using the current form values, updating as the user modifies fields.
7. THE Preset_Manager UI SHALL be accessible from the Image workspace page as a "Text Presets" button in the Thumbnail Samples section.
8. THE Preset_Manager UI SHALL support managing more than 100 presets without performance degradation in the list view.

### Requirement 6: Profile-Level Thumbnail Mode Selection

**User Story:** As a user, I want to choose between AI-generated and preset-based text overlays per music profile, so that different channels can use different thumbnail generation methods.

#### Acceptance Criteria

1. THE music profile image configuration SHALL include a "thumbnailOverlayMode" field with values: "ai" (existing AI flow), "preset_text" (programmatic rendering), defaulting to "ai".
2. WHEN a profile has "thumbnailOverlayMode" set to "preset_text", THE Image_Generation_Pipeline SHALL use the Text_Overlay_Renderer with random preset selection for all Thumbnail_Jobs associated with that profile.
3. WHEN a profile has "thumbnailOverlayMode" set to "ai", THE Image_Generation_Pipeline SHALL use the existing AI-based overlay generation with no behavior changes.
4. THE music profile settings UI SHALL include a dropdown for selecting the thumbnail overlay mode, with options "AI (FAL/SLAI)" and "Preset Text (Local)".
5. WHEN the user switches a profile from "ai" to "preset_text" mode, THE Preset_Manager SHALL validate that at least one Text_Style_Preset exists in the database before allowing the switch.

### Requirement 7: Font Management

**User Story:** As a user, I want to use custom fonts for text overlays, so that I can match specific visual aesthetics like cyberpunk, streetwear, or clean modern styles.

#### Acceptance Criteria

1. THE Text_Overlay_Renderer SHALL load fonts from a configurable fonts directory path stored in the application settings.
2. WHEN the specified font file does not exist, THE Text_Overlay_Renderer SHALL fall back to a bundled default sans-serif font.
3. THE Preset_Manager UI SHALL display a dropdown of available font files found in the configured fonts directory.
4. THE application SHALL support TrueType (.ttf) and OpenType (.otf) font file formats.
5. IF the fonts directory does not exist or is empty, THEN THE Preset_Manager UI SHALL display a message indicating that no custom fonts are available and that the default font is in use.

### Requirement 8: Manual Thumbnail Generation from Video Page

**User Story:** As a user, I want to manually trigger thumbnail generation from the Video page for specific tracks, so that I can regenerate thumbnails on demand without going through the full batch pipeline.

#### Acceptance Criteria

1. THE Video page UI SHALL include a "Generate Thumbnail" button for the currently selected track or batch.
2. WHEN the user clicks "Generate Thumbnail" on the Video page, THE Image_Generation_Pipeline SHALL create a Thumbnail_Job for the selected item using the profile's configured Thumbnail_Mode (AI or Preset Text).
3. WHEN manually generating a thumbnail in "preset_text" mode, THE Image_Generation_Pipeline SHALL use the Background_Image already generated for the batch as the base for compositing.
4. IF no Background_Image exists for the selected batch, THEN THE Image_Generation_Pipeline SHALL display an error message indicating that a background image must be generated first.
5. THE manually generated thumbnail SHALL appear in the job queue on the Image page following the same flow as automatically generated thumbnails.
