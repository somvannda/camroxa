# Implementation Plan: UI Design System

## Overview

Build a comprehensive, modular UI design system for the MusicGenerator PyQt6 desktop application. The system provides a centralized token registry, QSS stylesheet generator, reusable widget and layout components, theme variant support, backward compatibility shims, and developer documentation. Implementation proceeds bottom-up: tokens → QSS generator → widgets → layouts → integration → documentation.

## Tasks

- [x] 1. Set up package structure and token registry
  - [x] 1.1 Create design system package structure and token dataclasses
    - Create `python_app/design_system/` package with `__init__.py`
    - Create `python_app/design_system/tokens.py` with frozen dataclasses: `ColorTokens`, `TypographyTokens`, `SpacingTokens`, `ShapeTokens`, `ThemeTokens`
    - Implement `TokenRegistry` class with: `register_variant()`, `set_active()`, `get_active()`, `get_token()`, `as_dict()`, `validate_variant()`
    - Register the default "dark" variant with cyan/teal accent palette (#00bcd4 range)
    - Implement validation: raise `ValueError` listing missing keys when variant is incomplete
    - Implement dot-path access (`get_token("colors.accent")`)
    - Implement `as_dict()` returning flat dict for backward compatibility with `build_ui_tokens()`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 15.1, 15.2, 15.3, 15.4_

  - [x]* 1.2 Write property tests for token registry
    - **Property 14: Theme Variant Validation**
    - **Validates: Requirements 15.1, 15.3, 15.4**
    - Create `python_app/tests/test_design_system_properties.py`
    - Implement custom Hypothesis strategies: `valid_color_hex()`, `valid_theme_tokens()`, `partial_theme_tokens()`
    - Test: any incomplete ThemeTokens-like object raises ValueError listing all missing fields
    - Test: any complete valid ThemeTokens instance registers successfully

  - [x]* 1.3 Write unit tests for token registry
    - Test default dark theme has expected accent color in #00bcd4 range
    - Test `get_token()` returns correct values for various paths
    - Test `as_dict()` returns flat dictionary with expected keys
    - Test `KeyError` for unknown variant name in `set_active()`
    - Test `KeyError` for invalid path in `get_token()`
    - _Requirements: 1.5, 1.6, 1.7, 15.1, 15.4_

- [x] 2. Implement QSS generator
  - [x] 2.1 Create QSS generator module
    - Create `python_app/design_system/qss_generator.py`
    - Implement `QSSGenerator` class with `generate()` method
    - Implement section builders: `_base_widgets()`, `_buttons()`, `_inputs()`, `_lists_and_tables()`, `_scrollbars()`, `_sliders()`, `_tabs()`, `_menus()`, `_checkboxes()`, `_progress_bars()`, `_style_roles()`
    - Generate selectors for all 14 base widget types: QPushButton, QLabel, QLineEdit, QComboBox, QSlider, QProgressBar, QCheckBox, QTabWidget, QTableWidget, QListWidget, QScrollBar, QSpinBox, QTextEdit, QMenu
    - Generate property-selector rules for Style_Roles: uiRole="primary", "secondary", "danger", "success", "toggle", "transport", "transportPrimary"
    - Generate pseudo-state rules: :hover, :pressed, :checked, :disabled, :focus
    - Generate table/list styling with hover rows, themed headers, selection highlighting
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x]* 2.2 Write property tests for QSS generator
    - **Property 1: Token-to-QSS Round Trip**
    - **Validates: Requirements 1.5, 1.6**
    - Test: every color token value appears verbatim in generated QSS string
    - **Property 2: QSS Structural Completeness**
    - **Validates: Requirements 2.2, 2.3, 2.4, 12.3**
    - Test: QSS contains selectors for all 14 widget types, all Style_Roles, and pseudo-states
    - **Property 3: QSS Syntactic Validity**
    - **Validates: Requirements 2.6**
    - Test: balanced curly braces, no empty rule blocks, every block has at least one declaration

  - [x]* 2.3 Write unit tests for QSS generator
    - Test generated QSS with default dark theme contains expected selectors
    - Test QSS changes when token values are modified
    - Test QSS includes uiField property selectors for "card" and "standalone"
    - _Requirements: 2.1, 2.2, 2.6_

- [x] 3. Checkpoint - Token and QSS foundation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement widget components - buttons and toggle
  - [x] 4.1 Implement button components
    - Create `python_app/design_system/widgets/__init__.py`
    - Create `python_app/design_system/widgets/buttons.py`
    - Implement `DesignButton(QPushButton)` base class setting `uiRole` property from variant string
    - Implement `PrimaryButton`, `SecondaryButton`, `DangerButton`, `SuccessButton` subclasses
    - Implement `IconButton(QPushButton)` with SVG icon support and optional tooltip
    - Implement `ToggleButton(QPushButton)` with checkable behavior and checked pseudo-state
    - Unknown variant falls back to "primary" with warning log
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x]* 4.2 Write property test for button variant mapping
    - **Property 4: Button Variant-to-Property Mapping**
    - **Validates: Requirements 3.7**
    - Test: for any valid variant string, `DesignButton(variant=v)` sets `widget.property("uiRole") == v`

  - [x] 4.3 Implement toggle switch component
    - Create `python_app/design_system/widgets/toggle_switch.py`
    - Implement `ToggleSwitch(QWidget)` with custom `paintEvent` drawing rounded track and circular knob
    - Use `QPropertyAnimation` on `_knob_position` for 150ms slide animation
    - Emit `toggled(bool)` signal on state change
    - Support optional text label with configurable left/right position
    - Implement keyboard accessibility: Space key toggles, Tab provides focus navigation
    - Off state: dark track, muted knob; On state: cyan/teal track, white knob
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x]* 4.4 Write property test for toggle switch signals
    - **Property 5: Toggle Switch Signal Correctness**
    - **Validates: Requirements 4.5**
    - Test: each toggle emits `toggled` signal with boolean negation of previous state

- [x] 5. Implement widget components - slider and inputs
  - [x] 5.1 Implement custom slider component
    - Create `python_app/design_system/widgets/custom_slider.py`
    - Implement `CustomSlider(QSlider)` with configurable min, max, step, and orientation
    - Style via QSS: muted track background, accent-colored sub-page fill, styled handle with border
    - Support horizontal and vertical orientations
    - Emit `valueChanged` signal on drag
    - Arrow key adjustment by configured step value on keyboard focus
    - Raise `ValueError` if min ≥ max at construction
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x]* 5.2 Write property test for slider configuration
    - **Property 6: Slider Configuration Bounds**
    - **Validates: Requirements 5.6**
    - Test: for any valid (min, max, step) triple, slider properties match configured values

  - [x] 5.3 Implement input field components
    - Create `python_app/design_system/widgets/inputs.py`
    - Implement `StyledLineEdit(QLineEdit)` with field_variant property ("card"/"standalone"), placeholder support, focus highlight
    - Implement `StyledComboBox(QComboBox)` with field_variant property, themed dropdown
    - Implement `StyledSpinBox(QSpinBox)` with field_variant property, themed arrows
    - Each sets `uiField` Qt property for QSS property-selector matching
    - Invalid variant falls back to "standalone" with warning log
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x]* 5.4 Write property test for input field variants
    - **Property 7: Input Field Variant Mapping**
    - **Validates: Requirements 6.5, 6.6**
    - Test: for any input class and valid variant, `widget.property("uiField") == variant`

- [x] 6. Implement widget components - labels, transport, now playing
  - [x] 6.1 Implement typography label components
    - Create `python_app/design_system/widgets/labels.py`
    - Implement `TypedLabel(QLabel)` with `LEVELS` tuple and `setLevel()` method
    - Map each level to corresponding `uiRole` property value for QSS styling
    - Support dynamic text updates via `setText()` without altering the assigned level/role
    - Unknown level falls back to "body" with warning log
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x]* 6.2 Write property test for typography label levels
    - **Property 10: Typography Label Level Mapping and Stability**
    - **Validates: Requirements 9.1, 9.4**
    - Test: for any valid level and text, `TypedLabel` sets correct uiRole; `setText()` does not alter it

  - [x] 6.3 Implement transport button and seek bar
    - Create `python_app/design_system/widgets/transport.py`
    - Implement `TransportButton(QPushButton)` with SIZES dict {small:28, medium:36, large:44}
    - Set fixed width/height based on size variant, apply uiRole "transport" or "transportPrimary"
    - Support icon_name and tooltip parameters
    - Implement `SeekBar(QWidget)` composing CustomSlider + two TypedLabel (elapsed/total) in QHBoxLayout
    - Format time labels as "MM:SS" from millisecond values
    - Emit `valueChanged` signal from internal slider
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x]* 6.4 Write property tests for transport components
    - **Property 11: TransportButton Size Mapping**
    - **Validates: Requirements 10.2**
    - Test: for any valid size variant, button fixed dimensions equal expected pixels
    - **Property 12: SeekBar Time Formatting**
    - **Validates: Requirements 10.6**
    - Test: for any non-negative ms value (0–86400000), elapsed label displays correct "MM:SS"

  - [x] 6.5 Implement now playing card component
    - Create `python_app/design_system/widgets/now_playing_card.py`
    - Implement `NowPlayingCard(QWidget)` with `setTrackInfo()` method
    - Use Card layout as container with accent-bordered left edge highlight
    - Display album art thumbnail, track title (title level), artist (caption level), duration (muted level)
    - Display placeholder graphic (muted background + music note icon) when no album art
    - _Requirements: 14.1, 14.2, 14.3, 14.4_

- [x] 7. Checkpoint - Widget components complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement layout components
  - [x] 8.1 Implement card and panel layout components
    - Create `python_app/design_system/layouts/__init__.py`
    - Create `python_app/design_system/layouts/card.py`
    - Implement `Card(QWidget)` with configurable title, padding (0–64, clamped with warning), internal spacing between children
    - Rounded corners, subtle background differentiation from page surface
    - Create `python_app/design_system/layouts/panel.py`
    - Implement `Panel(QWidget)` with optional header area, content area, configurable border/separator
    - `setHeaderWidget()` and `addContent()` methods
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x]* 8.2 Write property test for card and panel configuration
    - **Property 8: Card and Panel Configuration Application**
    - **Validates: Requirements 7.1, 7.3, 7.4**
    - Test: for any valid padding and title, Card layout margins equal padding, title label shows text

  - [x] 8.3 Implement sidebar navigation component
    - Create `python_app/design_system/layouts/sidebar_nav.py`
    - Implement `SidebarNav(QWidget)` accepting items list of dicts with "key", "icon", "label"
    - Render vertical list with consistent height, padding, and icon-to-text spacing from tokens
    - Active item: distinct background, white icon tint; Inactive: muted text/icon
    - `setActiveItem(page_key)` method for programmatic selection
    - Emit `navigation_requested(str)` signal on item click
    - Raise `ValueError` for items missing required "key" field
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x]* 8.4 Write property test for sidebar navigation
    - **Property 9: SidebarNav Item Rendering and Signal Emission**
    - **Validates: Requirements 8.1, 8.4, 8.5**
    - Implement `valid_nav_items()` Hypothesis strategy
    - Test: for any non-empty items list, SidebarNav renders exactly len(items) entries
    - Test: clicking any item emits `navigation_requested` with that item's "key"

  - [x] 8.5 Implement section divider component
    - Create `python_app/design_system/layouts/section_divider.py`
    - Implement `SectionDivider(QWidget)` with custom `paintEvent` drawing horizontal line using separator token color
    - _Requirements: 7.5_

- [x] 9. Implement backward compatibility and theme switching
  - [x] 9.1 Implement backward compatibility shim
    - Create `python_app/design_system/_compat.py`
    - Implement `check_inline_stylesheet_conflict()` that logs deprecation warning when widget has both inline stylesheet and design system role
    - Warning message includes widget identifier and role name
    - Ensure existing `uiRole`, `uiPanel`, `uiField` property values continue to work in generated QSS
    - _Requirements: 12.3, 12.4, 12.5_

  - [x]* 9.2 Write property test for deprecation warnings
    - **Property 13: Deprecation Warning for Stylesheet Conflicts**
    - **Validates: Requirements 12.5**
    - Test: any widget with non-empty inline stylesheet + design system role triggers warning containing widget identifier and role name

  - [x] 9.3 Implement runtime theme switching
    - Wire `TokenRegistry.set_active()` to regenerate QSS and reapply to QApplication
    - Implement bootstrap integration point that applies global QSS at startup
    - Ensure unmigrated views receive base theme styling automatically from global QSS
    - Design system widgets render correctly inside existing views without full migration
    - _Requirements: 12.1, 12.2, 15.5_

- [x] 10. Checkpoint - All components and integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Wire public API and documentation
  - [x] 11.1 Create public API exports in __init__.py
    - Export all widget components, layout components, TokenRegistry, QSSGenerator from `python_app/design_system/__init__.py`
    - Create `python_app/design_system/widgets/__init__.py` with widget exports
    - Create `python_app/design_system/layouts/__init__.py` with layout exports
    - _Requirements: 1.5, 12.2_

  - [x] 11.2 Create pattern library documentation
    - Create `python_app/design_system/PATTERN_LIBRARY.md`
    - Document each Widget_Component: name, purpose, constructor parameters, variants, code usage example
    - Document each Layout_Component: name, purpose, constructor parameters, composition example
    - Document complete token list by category (color, typography, spacing, shape) with hex values
    - Document migration guide: how to convert existing view from inline styling to design system components
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [x]* 11.3 Write integration tests
    - Create `python_app/tests/test_design_system_integration.py`
    - Test global QSS applied at startup styles widgets correctly
    - Test design system widget renders inside existing view
    - Test runtime theme switching updates all widgets
    - Test inline stylesheet coexistence with design system roles
    - _Requirements: 2.5, 12.1, 12.2, 15.5_

- [x] 12. Final checkpoint - All tests pass and documentation complete
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document using Hypothesis
- Unit tests validate specific examples and edge cases
- Integration tests require `pytest-qt` with QApplication fixture
- The design system package is at `python_app/design_system/` and is separate from existing `app/theme.py`
- Existing `theme.py` continues to function during migration via `TokenRegistry.as_dict()` compatibility

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3"] },
    { "id": 4, "tasks": ["4.1", "4.3", "5.1", "5.3", "6.1"] },
    { "id": 5, "tasks": ["4.2", "4.4", "5.2", "5.4", "6.2", "6.3"] },
    { "id": 6, "tasks": ["6.4", "6.5"] },
    { "id": 7, "tasks": ["8.1", "8.3", "8.5"] },
    { "id": 8, "tasks": ["8.2", "8.4"] },
    { "id": 9, "tasks": ["9.1", "9.3"] },
    { "id": 10, "tasks": ["9.2"] },
    { "id": 11, "tasks": ["11.1", "11.2", "11.3"] }
  ]
}
```
