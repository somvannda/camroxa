# Requirements Document

## Introduction

This feature adds a visual text overlay editor directly within the Video page's live preview canvas (the existing `SpectrumPreview` OpenGL widget). Users design text style presets interactively — positioning, resizing, and styling text blocks on top of the actual background image in real-time — rather than using the existing form-based `PresetManagerDialog`. Designed presets are saved to the database and used during thumbnail generation. The feature also fixes the existing preview frame offset/padding misalignment.

This builds on top of the existing `dynamic-text-overlay` spec which provides the `TextStylePreset` dataclass, `Text_Overlay_Renderer`, `FontManager`, preset database layer, and `PresetManagerCoordinator`.

## Glossary

- **Text_Editor_Overlay**: The interactive PyQt6/OpenGL layer rendered on top of the SpectrumPreview canvas that displays editable text blocks with selection handles, supporting drag and resize interactions.
- **Text_Block**: A single text element on the canvas representing either a track title placeholder or custom user-typed text, rendered with a specific `TextStylePreset` configuration.
- **Selection_Handle**: Interactive UI affordances (corner and edge rectangles) displayed around a selected Text_Block that allow the user to resize the text by dragging.
- **Preview_Canvas**: The existing `SpectrumPreview` QOpenGLWidget on the Video page that renders the background image, audio visualizer, and now additionally the Text_Editor_Overlay.
- **Canvas_Coordinate_System**: The normalized coordinate system mapping pixel positions on the Preview_Canvas widget to positions on the target output resolution, accounting for aspect ratio and scaling.
- **Text_Style_Preset**: The existing named configuration defining all visual properties for text rendering (font, size, colors, effects, position, layout) — as defined in the dynamic-text-overlay spec.
- **Preset_Manager_Coordinator**: The existing feature coordinator (`features/text_presets/coordinator.py`) that handles preset CRUD operations and preview rendering.
- **Frame_Offset**: The misalignment between the Preview_Canvas widget boundaries and the actual rendered content area caused by incorrect padding or viewport calculations.

## Requirements

### Requirement 1: Preview Frame Offset Fix

**User Story:** As a user, I want the video preview to fill the preview container correctly without misaligned padding, so that what I see in the editor matches the actual output dimensions.

#### Acceptance Criteria

1. THE Preview_Canvas SHALL render content that fills the entire widget area within the AspectRatioBox without extra padding or offset between the rendered content and the widget boundaries.
2. WHEN the output resolution changes via the resolution dropdown, THE Preview_Canvas SHALL recalculate the viewport to fill the new aspect ratio container without introducing frame offset.
3. THE Preview_Canvas viewport SHALL map pixel-for-pixel to the widget dimensions reported by `width()` and `height()` with zero margin between the OpenGL viewport and the widget edges.
4. WHEN the Preview_Canvas is resized (e.g., window resize), THE Preview_Canvas SHALL maintain zero-offset rendering by updating the viewport to match the new widget dimensions on every paint cycle.

### Requirement 2: Text Editor Overlay Layer

**User Story:** As a user, I want an interactive text editing layer on top of the video preview, so that I can visually design text overlay presets directly on the canvas with the real background visible.

#### Acceptance Criteria

1. THE Text_Editor_Overlay SHALL render on top of all existing preview content (background, audio visualizer, particles, logo) in the SpectrumPreview paint cycle.
2. THE Text_Editor_Overlay SHALL support displaying one or more Text_Blocks simultaneously on the canvas.
3. WHEN no Text_Blocks exist on the canvas, THE Text_Editor_Overlay SHALL display no visual elements and pass all mouse events through to the underlying preview interaction handlers (background drag, visualizer position drag).
4. THE Text_Editor_Overlay SHALL render each Text_Block using the same styling pipeline as the existing `Text_Overlay_Renderer` (font, color, stroke, glow, shadow, gradient) to ensure visual fidelity between the editor and the generated thumbnail output.
5. WHEN the user activates the text editor mode, THE Text_Editor_Overlay SHALL become the active interaction layer, intercepting mouse events for text manipulation instead of passing them to background or visualizer controls.
6. THE Text_Editor_Overlay SHALL provide a toolbar or panel with controls to enter/exit text editing mode, add new Text_Blocks, and access preset save/load operations.

### Requirement 3: Custom Text Content

**User Story:** As a user, I want to type custom text and see it rendered with preset styles on the preview, so that I can preview how track titles or other text will look on the final thumbnail.

#### Acceptance Criteria

1. WHEN the user adds a new Text_Block, THE Text_Editor_Overlay SHALL allow the user to enter custom text content via an inline text input or a dedicated text field in the editor toolbar.
2. THE Text_Editor_Overlay SHALL provide a "Track Title" placeholder mode where the Text_Block displays sample text (e.g., "Track Title Preview") representing how actual track titles will appear at thumbnail generation time.
3. WHEN the user modifies the text content of a Text_Block, THE Text_Editor_Overlay SHALL re-render the text on the canvas within 300 milliseconds using debounced updates.
4. THE Text_Block SHALL support multi-line text content, rendering each line according to the preset's line_spacing parameter.
5. WHEN a Text_Block is in "Track Title" placeholder mode, THE Text_Editor_Overlay SHALL visually indicate the placeholder state (e.g., muted label or badge) to distinguish the placeholder from custom user text.

### Requirement 4: Drag to Reposition Text Blocks

**User Story:** As a user, I want to drag text blocks to reposition them on the preview canvas, so that I can place text exactly where I want it on the thumbnail.

#### Acceptance Criteria

1. WHEN the user clicks on a Text_Block in text editor mode, THE Text_Editor_Overlay SHALL select that Text_Block and display Selection_Handles around the block's bounding box.
2. WHEN the user drags a selected Text_Block, THE Text_Editor_Overlay SHALL move the text block in real-time following the mouse cursor with the rendered text position updating on each frame.
3. THE Text_Editor_Overlay SHALL convert drag pixel offsets from widget coordinates to Canvas_Coordinate_System values, ensuring the position is resolution-independent and maps correctly to the target output resolution.
4. WHEN the user releases the mouse after dragging, THE Text_Editor_Overlay SHALL commit the new position to the Text_Block state.
5. WHEN a Text_Block is dragged beyond the canvas boundaries, THE Text_Editor_Overlay SHALL clamp the text block position to keep at least 10% of the block visible within the canvas area.
6. WHEN the user clicks on an empty area of the canvas (no Text_Block under cursor) in text editor mode, THE Text_Editor_Overlay SHALL deselect the currently selected Text_Block and hide Selection_Handles.

### Requirement 5: Resize Text Blocks

**User Story:** As a user, I want to resize text blocks by dragging handles on the preview canvas, so that I can adjust text size and bounding area visually.

#### Acceptance Criteria

1. WHEN a Text_Block is selected, THE Text_Editor_Overlay SHALL display eight Selection_Handles (four corners and four edge midpoints) around the text block's bounding box.
2. WHEN the user drags a corner Selection_Handle, THE Text_Editor_Overlay SHALL scale the text block proportionally (maintaining aspect ratio) based on the drag distance.
3. WHEN the user drags an edge midpoint Selection_Handle, THE Text_Editor_Overlay SHALL adjust the text block's maximum width constraint (for horizontal edges) or reposition vertically (for vertical edges) based on the drag direction.
4. WHILE the user drags a Selection_Handle, THE Text_Editor_Overlay SHALL display the updated text rendering in real-time, re-rendering the text with the adjusted font size or width constraint.
5. THE Text_Editor_Overlay SHALL enforce minimum text block dimensions: font size at least 12 pixels and maximum width at least 20% of canvas width at the target resolution.
6. THE Text_Editor_Overlay SHALL enforce maximum text block dimensions: font size at most 400 pixels and maximum width at most 90% of canvas width at the target resolution.

### Requirement 6: Per-Track Preset Assignment and Save

**User Story:** As a user, I want to design preset styles in the visual editor and save them, so that saved presets are used during thumbnail generation instead of random rotation.

#### Acceptance Criteria

1. WHEN the user designs a text layout on the canvas (positioning, sizing, styling one or more Text_Blocks), THE Text_Editor_Overlay SHALL allow the user to save the current canvas state as a named Text_Style_Preset.
2. WHEN the user saves a preset from the text editor, THE Text_Editor_Overlay SHALL persist the position (x, y as percentages of canvas dimensions), font size, and all style properties to the existing preset database via the Preset_Manager_Coordinator.
3. THE Text_Editor_Overlay SHALL provide a "Load Preset" action that populates the canvas with Text_Blocks from a previously saved preset, restoring positions, sizes, and styles.
4. WHEN generating thumbnails, THE Image_Generation_Pipeline SHALL use presets saved from the visual editor with their stored position coordinates rather than the generic top/center/bottom positioning.
5. THE Text_Editor_Overlay SHALL display a list or dropdown of existing saved presets, allowing the user to switch between them for editing or preview.
6. WHEN the user modifies a loaded preset and saves, THE Text_Editor_Overlay SHALL update the existing preset record (upsert by name) via the Preset_Manager_Coordinator.

### Requirement 7: Text Block Style Controls

**User Story:** As a user, I want to adjust text styling properties (font, color, effects) while seeing changes live on the preview, so that I can fine-tune the appearance before saving.

#### Acceptance Criteria

1. WHEN a Text_Block is selected, THE Text_Editor_Overlay SHALL display a style properties panel with controls for: font selection, font size, primary color, stroke (width and color), glow (radius and color), shadow (offset and color), and gradient (enabled, start/end colors).
2. WHEN the user changes any style property in the panel, THE Text_Editor_Overlay SHALL re-render the selected Text_Block on the canvas within 300 milliseconds using debounced updates.
3. THE style properties panel SHALL use the same field ranges and constraints as the existing PresetFormDialog: font size 12–400, glow radius 0–50, stroke width 0–10, line spacing 1.0–3.0, max width 20–90%, vertical padding 2–30%.
4. THE style properties panel SHALL include a color picker (QColorDialog with alpha channel) for each color field, matching the existing PresetFormDialog interaction pattern.
5. THE style properties panel SHALL display available fonts from the configured fonts directory using the existing FontManager, with a fallback message when no custom fonts are available.

### Requirement 8: Canvas-to-Output Coordinate Mapping

**User Story:** As a user, I want the text positions I set in the preview to map accurately to the generated thumbnail output, so that what I see in the editor is what I get in the final image.

#### Acceptance Criteria

1. THE Canvas_Coordinate_System SHALL define text positions as percentage offsets (0–100%) relative to the canvas width and height, ensuring positions are resolution-independent.
2. WHEN a preset with percentage-based positions is used for thumbnail generation at a specific resolution, THE Text_Overlay_Renderer SHALL convert percentage positions to pixel positions at the target resolution, producing output matching the editor preview.
3. FOR ALL valid percentage positions (0–100% for both x and y), converting to pixels at any supported resolution and back to percentages SHALL produce values within 0.5% of the original (round-trip property).
4. WHEN the Preview_Canvas widget is resized, THE Text_Editor_Overlay SHALL maintain the visual position of Text_Blocks relative to the background image by recalculating pixel positions from the stored percentage values.
5. THE Canvas_Coordinate_System SHALL account for the aspect ratio difference between the widget display size and the target output resolution, ensuring text placement is consistent regardless of the preview widget's current pixel dimensions.

### Requirement 9: Editor Mode Integration with Existing Video Page

**User Story:** As a user, I want the text editor to integrate smoothly with the existing Video page controls without disrupting the current workflow (playback, export, background editing).

#### Acceptance Criteria

1. THE Video page SHALL include a "Text Editor" toggle button in the preview header area (alongside the existing "Live Preview" and "Background" buttons) to enter and exit text editing mode.
2. WHILE text editor mode is inactive, THE Preview_Canvas SHALL behave identically to the current implementation with no visual or interaction changes.
3. WHEN text editor mode is active, THE Preview_Canvas SHALL disable background drag interactions (the existing `_bg_edit_mode` behavior) and visualizer position drag to prevent conflicts with text block manipulation.
4. WHILE text editor mode is active, THE Preview_Canvas SHALL continue rendering the background image, audio visualizer, particles, and logo underneath the text editor layer so the user sees the full visual context.
5. WHEN the user exits text editor mode, THE Text_Editor_Overlay SHALL hide all Selection_Handles and editing UI but continue rendering any placed Text_Blocks as a non-interactive overlay for reference.
6. THE text editor mode SHALL coexist with audio playback — the user can play audio and see the visualizer animate while editing text positions on the canvas.

