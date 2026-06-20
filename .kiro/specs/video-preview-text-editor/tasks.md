# Implementation Plan: Video Preview Text Editor

## Overview

This implementation adds an interactive text overlay editor to the Video page's live preview canvas. The plan builds incrementally: first fixing the viewport offset, then adding the coordinate mapper, text block state model, the overlay interaction layer, style panel, preset save/load integration, and finally wiring everything together with the existing Video page UI.

## Tasks

- [x] 1. Fix preview frame offset and implement coordinate mapper
  - [x] 1.1 Fix SpectrumPreview viewport to eliminate frame offset
    - Modify `paintGL()` to set the OpenGL viewport to `(0, 0, self.width(), self.height())` with zero margin
    - Ensure the viewport recalculates on every paint cycle and on resolution change via the resolution dropdown
    - Remove any existing padding or offset logic between the GL viewport and widget edges
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 Implement CanvasCoordinateMapper class
    - Create `views/components/canvas_coordinate_mapper.py` with `CanvasCoordinateMapper` and `CanvasRect` dataclass
    - Implement `_compute_canvas_rect()` accounting for aspect ratio letterboxing/pillarboxing
    - Implement `widget_to_pct()`, `pct_to_widget()`, `pct_to_output()`, `output_to_pct()`, `widget_delta_to_pct_delta()`
    - Implement `update()` method for resize/resolution change recalculation
    - Guard against division by zero when widget dimensions are 0
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 1.3 Write property tests for CanvasCoordinateMapper
    - **Property 2: Coordinate round-trip within tolerance**
    - **Property 3: Aspect-ratio-aware coordinate mapping**
    - **Validates: Requirements 8.3, 8.5, 4.3, 8.2, 8.4**

  - [ ]* 1.4 Write property test for viewport invariant
    - **Property 1: Viewport matches widget dimensions (zero offset)**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4**

- [ ] 2. Implement TextBlockState data model
  - [ ] 2.1 Create TextBlockState dataclass
    - Create `views/components/text_block_state.py` with all fields as defined in design
    - Implement `to_preset()` converting state to `TextStylePreset` for rendering
    - Implement `to_preset_dict(name)` for persistence including x_pct, y_pct position fields
    - Implement `from_preset_dict(data)` class method to restore state from saved preset dict
    - _Requirements: 6.2, 3.1, 3.2, 3.4_

  - [ ]* 2.2 Write property test for preset round-trip
    - **Property 11: Preset save captures complete canvas state**
    - **Validates: Requirements 6.2**

- [ ] 3. Implement TextEditorOverlay core
  - [ ] 3.1 Create TextEditorOverlay class with activation and block management
    - Create `views/components/text_editor_overlay.py`
    - Implement `__init__()`, `activate()`, `deactivate()`, `is_active` property
    - Implement `add_block()`, `remove_block()`, `select_block()`, `get_blocks()`
    - Implement `update_mapper()` for coordinate system updates on resize/resolution change
    - Implement `load_from_preset()` to populate canvas from saved preset data
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 6.3_

  - [ ] 3.2 Implement text block rendering pipeline
    - Implement `paint()` method using QPainter to draw all text blocks
    - Implement `_render_block_pixmap()` using `Text_Overlay_Renderer.render_text_overlay()` to generate PIL Image, convert to QPixmap
    - Implement `_schedule_rerender()` and `_do_deferred_render()` for 300ms debounced re-rendering
    - Implement pixmap caching with `_cache_key` to avoid unnecessary re-renders
    - Handle render errors with red outline placeholder and error logging
    - _Requirements: 2.4, 3.3, 7.2_

  - [ ]* 3.3 Write property test for all blocks rendered
    - **Property 4: All text blocks rendered**
    - **Validates: Requirements 2.2**

  - [ ]* 3.4 Write property test for editor rendering fidelity
    - **Property 5: Editor rendering matches output rendering**
    - **Validates: Requirements 2.4**

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement mouse interaction (drag and resize)
  - [ ] 5.1 Implement hit-testing and selection
    - Implement `_hit_test_block()` to detect which text block is under cursor position
    - Implement `_hit_test_handle()` to detect which selection handle is under cursor
    - Implement `_get_handle_rects()` to compute 8 handle rectangles (4 corners + 4 edge midpoints)
    - Implement `handle_mouse_press()` — select block on click, deselect on empty area click
    - _Requirements: 4.1, 4.6, 5.1_

  - [ ] 5.2 Implement drag-to-reposition
    - Implement drag logic in `handle_mouse_move()` and `handle_mouse_release()`
    - Convert pixel drag deltas to percentage using `CanvasCoordinateMapper.widget_delta_to_pct_delta()`
    - Update TextBlockState position in real-time during drag
    - Implement `_clamp_position()` to keep at least 10% of block visible within canvas
    - Commit final position on mouse release
    - _Requirements: 4.2, 4.3, 4.4, 4.5_

  - [ ] 5.3 Implement resize via selection handles
    - Implement corner handle drag for proportional scaling (maintain aspect ratio)
    - Implement edge midpoint handle drag for width constraint or vertical repositioning
    - Display updated rendering in real-time during resize
    - Implement `_clamp_dimensions()` to enforce font_size [12, 400] and max_text_width_pct [20, 90]
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 5.4 Write property tests for drag and resize
    - **Property 6: Drag position converts correctly to canvas percentages**
    - **Property 7: Position clamping keeps 10% visible**
    - **Property 8: Eight selection handles at correct positions**
    - **Property 9: Corner resize preserves aspect ratio**
    - **Property 10: Dimension bounds enforcement**
    - **Validates: Requirements 4.2, 4.5, 5.1, 5.2, 5.5, 5.6**

- [ ] 6. Implement TextStylePanel
  - [ ] 6.1 Create TextStylePanel widget
    - Create `views/components/text_style_panel.py` with all style controls
    - Implement font selection dropdown populated from FontManager with fallback message
    - Implement sliders/spinboxes: font size (12–400), glow radius (0–50), stroke width (0–10), line spacing (1.0–3.0), max width (20–90%), vertical padding (2–30%)
    - Implement color pickers using QColorDialog with alpha channel for: primary, stroke, glow, shadow, gradient start/end
    - Implement gradient toggle checkbox
    - Emit `style_changed` signal with debounced 300ms updates
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ] 6.2 Connect TextStylePanel to TextEditorOverlay
    - Implement `set_from_block()` to populate panel from selected TextBlockState
    - Wire `style_changed` signal to update selected block's style fields and trigger re-render
    - Show/hide panel based on block selection state
    - _Requirements: 7.2_

  - [ ]* 6.3 Write unit tests for TextStylePanel
    - Test field constraint ranges match design spec
    - Test debounce timer fires once for rapid changes
    - Test set_from_block correctly populates all fields
    - _Requirements: 7.3_

- [ ] 7. Implement preset save/load and database extension
  - [ ] 7.1 Extend database schema with position columns
    - Add `position_x_pct REAL DEFAULT NULL` and `position_y_pct REAL DEFAULT NULL` columns to `text_style_presets` table
    - Update database migration/initialization logic to add columns if not present
    - Update PresetManagerCoordinator to handle the new position fields on save and load
    - _Requirements: 6.2, 6.4_

  - [ ] 7.2 Implement preset save from text editor
    - Wire "Save Preset" button to extract current canvas state via `TextEditorOverlay.get_blocks()`
    - Convert TextBlockState to preset dict with position percentages via `to_preset_dict()`
    - Save via PresetManagerCoordinator (upsert by name)
    - Validate: block exists on canvas, preset name not empty
    - _Requirements: 6.1, 6.2, 6.6_

  - [ ] 7.3 Implement preset load into text editor
    - Wire "Load Preset" dropdown to list existing presets from PresetManagerCoordinator
    - On selection, call `TextEditorOverlay.load_from_preset()` to populate canvas
    - Restore positions, sizes, and all style properties from saved data
    - Handle empty preset list (disabled button with tooltip)
    - _Requirements: 6.3, 6.5_

  - [ ] 7.4 Update Text_Overlay_Renderer to use percentage positions
    - When `position_x_pct` and `position_y_pct` are present in preset data, convert to pixel coordinates at target resolution for absolute positioning
    - Fall back to existing `position` field ("top"/"center"/"bottom") when percentage fields are NULL
    - _Requirements: 6.4, 8.2_

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Wire Video page integration
  - [ ] 9.1 Add text editor toggle button and toolbar to Video page
    - Add "Text Editor" checkable toggle button in preview header alongside existing buttons
    - Create TextEditorToolbar widget with: "Add Text Block" button, text input field, preset dropdown, "Save Preset" button
    - Show/hide toolbar based on text editor mode state
    - _Requirements: 9.1, 2.6_

  - [ ] 9.2 Integrate TextEditorOverlay into SpectrumPreview
    - Initialize `TextEditorOverlay` in SpectrumPreview `__init__`
    - Implement `set_text_editor_mode()` to activate/deactivate overlay and disable background drag
    - Override `paintEvent()` to call `text_editor_overlay.paint()` after GL rendering
    - Override `mousePressEvent()`, `mouseMoveEvent()`, `mouseReleaseEvent()` to forward events to overlay when active
    - Ensure audio playback and visualizer continue animating while text editor is active
    - _Requirements: 9.2, 9.3, 9.4, 9.5, 9.6, 2.1, 2.3, 2.5_

  - [ ] 9.3 Implement custom text content and placeholder mode
    - Wire text input field in toolbar to update selected TextBlockState text content
    - Implement placeholder mode toggle — display "Track Title Preview" with visual indicator (badge/label)
    - Support multi-line text with line_spacing rendering
    - Trigger debounced re-render on text changes (within 300ms)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 9.4 Write property test for multi-line text rendering
    - **Property 12: Multi-line text renders all lines**
    - **Validates: Requirements 3.4**

- [ ] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties defined in the design document
- Unit tests validate specific examples and edge cases
- The implementation uses Python with PyQt6 and Hypothesis for property-based testing
- The existing `Text_Overlay_Renderer`, `FontManager`, `PresetManagerCoordinator`, and `TextStylePreset` are reused from the `dynamic-text-overlay` spec

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "2.1"] },
    { "id": 1, "tasks": ["1.3", "1.4", "2.2", "3.1"] },
    { "id": 2, "tasks": ["3.2", "5.1"] },
    { "id": 3, "tasks": ["3.3", "3.4", "5.2"] },
    { "id": 4, "tasks": ["5.3", "5.4", "6.1"] },
    { "id": 5, "tasks": ["6.2", "6.3", "7.1"] },
    { "id": 6, "tasks": ["7.2", "7.3", "7.4"] },
    { "id": 7, "tasks": ["9.1", "9.2"] },
    { "id": 8, "tasks": ["9.3", "9.4"] }
  ]
}
```
