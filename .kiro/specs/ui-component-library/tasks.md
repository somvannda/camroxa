# Implementation Plan: UI Component Library

## Overview

This plan extends the existing `python_app/design_system/` package with updated color tokens, new widget components (GradientButton, StatusBadge, Icon, GhostButton, OutlinedButton, TableActionButton, IndeterminateProgress), new layout components (GlassCard, QuickActionCard/Grid, StatCard/Group, PromoCard), enhanced SidebarNav, and QSS generator extensions for tooltips, tables, inputs, progress bars, and button variants.

## Tasks

- [x] 1. Extend Token Registry with new color fields and validation
  - [x] 1.1 Add new color token fields to ColorTokens dataclass
    - Add `surface_elevated`, `accent_glow`, `secondary_accent`, `secondary_accent_hover`, `status_active`, `status_inactive`, `status_premium`, `status_warning`, and `border_glass` fields to the existing `ColorTokens` frozen dataclass in `python_app/design_system/tokens.py`
    - Update the default dark theme values to the deep navy palette: `surface_base=#0a0e27`, `surface_raised=#0f1538`, `surface_overlay=#1a1f3a`, `surface_sunken=#070b1e`, `surface_elevated=#1e2548`, `accent=#00d4ff`, `accent_glow=#00d4ff66`, `secondary_accent=#7c3aed`, `secondary_accent_hover=#a855f7`, `status_active=#10b981`, `status_inactive=#6b7280`, `status_premium=#a855f7`, `status_warning=#f59e0b`, `border_glass=#ffffff1a`
    - Ensure backward compatibility — existing field defaults remain unchanged where not explicitly updated
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 1.2 Implement token validation extension in TokenRegistry
    - Add `_HEX_COLOR_RE` regex pattern matching `#RRGGBB` or `#RRGGBBAA`
    - Extend `validate_variant()` to validate all color token fields against the hex regex
    - Add typography size range validation (8–72 positive integers)
    - Add spacing range validation (0–64 non-negative integers)
    - Add shape radius range validation (0–32 non-negative integers)
    - Raise `ValueError` listing ALL invalid tokens (not fail-fast) when any validation fails
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

  - [ ]* 1.3 Write property tests for token validation (Properties 1, 2)
    - **Property 1: Token-to-QSS Color Round Trip** — For any valid ThemeTokens, every color token value appears verbatim in the generated QSS string
    - **Property 2: Token Validation Catches Invalid Values** — For any invalid ThemeTokens, validate_variant() returns non-empty errors listing all invalid fields; for valid tokens, returns empty list
    - **Validates: Requirements 1.7, 15.1, 15.2, 15.3, 15.4, 15.5, 15.6**
    - Create test file at `python_app/tests/test_ui_component_library_properties.py`
    - Implement custom strategies: `valid_hex_color()`, `invalid_hex_color()`, `valid_theme_tokens()`

- [x] 2. Implement Icon widget
  - [x] 2.1 Create SVG icon assets directory and Icon widget
    - Create `python_app/design_system/assets/icons/` directory
    - Add a placeholder/fallback icon SVG file (`circle.svg`)
    - Create `python_app/design_system/widgets/icon.py` with the `Icon` class
    - Implement SVG rendering via `QSvgRenderer` with color tinting by modifying SVG stroke attribute
    - Support size variants: small (16px), medium (20px), large (24px), xlarge (32px)
    - Support opacity parameter (0.0–1.0) clamped to bounds
    - Implement fallback behavior: render placeholder icon and log warning when icon name not found
    - Export from `python_app/design_system/widgets/__init__.py`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ]* 2.2 Write property tests for Icon widget (Properties 12, 13)
    - **Property 12: Icon Size Variant Mapping** — For any size variant, widget fixed width/height equals expected pixel value
    - **Property 13: Icon Opacity and Color Storage** — For any valid opacity and color, Icon stores those values correctly
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.6**

- [x] 3. Implement GlassCard layout component
  - [x] 3.1 Create GlassCard widget
    - Create `python_app/design_system/layouts/glass_card.py` with the `GlassCard` class
    - Implement rounded corners (12px default), semi-transparent `surface_elevated` background, 1px `border_glass` border
    - Support title (bold 14-16px white) and optional subtitle (muted text) labels
    - Apply consistent internal padding (16px default) from spacing tokens
    - Implement hover state with border brightness increase (border to ~20% white opacity)
    - Implement clickable mode: emit `clicked` signal, cursor change on hover
    - Support configurable padding and border_radius overrides via constructor
    - Provide `addWidget()` method for content layout
    - Export from `python_app/design_system/layouts/__init__.py`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [ ]* 3.2 Write property tests for GlassCard (Properties 3, 4)
    - **Property 3: GlassCard Configuration Preservation** — For any valid padding (0–64), border-radius (0–32), title, and subtitle, GlassCard preserves all configured values
    - **Property 4: GlassCard Clickable Signal Emission** — For clickable=True, mouse press emits `clicked` signal exactly once
    - **Validates: Requirements 2.2, 2.3, 2.4, 2.6, 2.7**

- [x] 4. Implement StatusBadge and GradientButton widgets
  - [x] 4.1 Create StatusBadge widget
    - Create `python_app/design_system/widgets/status_badge.py` with the `StatusBadge` class
    - Implement pill mode: rounded-full corners, 6-8px horizontal padding, 2-4px vertical padding, caption font
    - Implement dot mode: 8px diameter circle, no text
    - Support predefined variants: "active" (green), "inactive" (gray), "premium" (purple), "warning" (orange)
    - Map variants to status token colors from the token registry
    - Support custom color overrides via `background_color` and `text_color` parameters
    - Fallback to "inactive" variant for unknown variant strings with warning log
    - Export from `python_app/design_system/widgets/__init__.py`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 4.2 Create GradientButton widget
    - Create `python_app/design_system/widgets/gradient_button.py` with the `GradientButton` class
    - Implement custom `paintEvent` with `QLinearGradient` for accent-to-lighter gradient background
    - Attach `QGraphicsDropShadowEffect` using `accent_glow` token color for outer glow
    - Use 8px border-radius, bold white text, standard horizontal padding
    - Implement hover: increase blur radius and lighten gradient stops
    - Implement pressed: reduce glow and darken gradient stops
    - Implement disabled state: remove shadow effect, use flat muted background
    - Support optional leading icon (icon name) rendered to the left of text via the Icon widget
    - Export from `python_app/design_system/widgets/__init__.py`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ]* 4.3 Write property test for StatusBadge (Property 5)
    - **Property 5: StatusBadge Variant-to-Color Mapping** — For any variant in {active, inactive, premium, warning}, StatusBadge applies the corresponding status token color; custom overrides replace defaults
    - **Validates: Requirements 3.2, 3.4, 3.6**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement QuickAction components
  - [x] 6.1 Create QuickActionCard and QuickActionGrid
    - Create `python_app/design_system/layouts/quick_action.py` with `QuickActionCard` and `QuickActionGrid` classes
    - QuickActionCard: centered icon above text label, glass-card styling (rounded corners, semi-transparent border, subtle background)
    - QuickActionCard: emit `action_triggered` signal with action key string on click
    - QuickActionCard: hover shows border highlight with accent color at reduced opacity
    - QuickActionGrid: arrange cards in `QGridLayout` with configurable column count and gap spacing
    - QuickActionGrid: accept list of action descriptors `[{"key", "icon_name", "label"}]`, render one card per item
    - QuickActionGrid: forward `action_triggered` signals from child cards
    - Validate that action descriptors have required "key" field, raise `ValueError` for malformed descriptors
    - Export from `python_app/design_system/layouts/__init__.py`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 6.2 Write property tests for QuickAction components (Properties 6, 7)
    - **Property 6: QuickActionCard Signal Emission with Key** — For any non-empty key, click emits `action_triggered` with that key
    - **Property 7: QuickActionGrid Item Count and Column Layout** — For any list (1–20 items) and columns (1–8), grid renders exactly len(items) cards in correct column layout
    - **Validates: Requirements 5.3, 5.5, 5.6**

- [x] 7. Implement StatCard and PromoCard components
  - [x] 7.1 Create StatCard and StatCardGroup
    - Create `python_app/design_system/layouts/stat_card.py` with `StatCard` and `StatCardGroup` classes
    - StatCard: display metric label (muted, caption) above metric value (primary, bold)
    - StatCard: compact card container with consistent padding from spacing tokens
    - StatCard: optional icon (accent color) rendered to the left of label/value pair
    - StatCard: `setValue()` method updates displayed text without recreating widget
    - StatCardGroup: arrange StatCards horizontally or vertically with subtle separators
    - StatCardGroup: accept list of stat descriptors `[{"label", "value", "icon_name"}]`, render one StatCard per item
    - Export from `python_app/design_system/layouts/__init__.py`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 7.2 Create PromoCard widget
    - Create `python_app/design_system/layouts/promo_card.py` with `PromoCard` class
    - Custom `paintEvent` with `QLinearGradient` for gradient background (purple-to-blue default)
    - Display title (bold, white), description (muted/light), and action button
    - 12px border-radius consistent with GlassCard styling
    - Emit `action_clicked` signal when action button clicked
    - Support optional icon/badge alongside title
    - Accept configurable `gradient_start` and `gradient_end` colors via constructor
    - Fallback to default gradient when invalid color strings provided
    - Export from `python_app/design_system/layouts/__init__.py`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 7.3 Write property tests for StatCard and PromoCard (Properties 8, 9, 10)
    - **Property 8: StatCard Value Display and Update** — For any label, initial value, and new value, StatCard displays correctly and setValue updates without changing label
    - **Property 9: StatCardGroup Renders Correct Item Count** — For any list (1–12 items), group renders exactly len(items) StatCard children
    - **Property 10: PromoCard Content Display and Signal** — For any title, description, button_text, and gradient colors, PromoCard displays text and button click emits signal
    - **Validates: Requirements 6.1, 6.4, 6.5, 6.6, 7.1, 7.2, 7.4, 7.6**

- [x] 8. Enhance SidebarNav and implement button variants
  - [x] 8.1 Enhance SidebarNav with groups, promo slot, hover, separators
    - Modify `python_app/design_system/layouts/sidebar_nav.py` to extend the existing `SidebarNav`
    - Add item grouping with optional group header labels (uppercase muted caption text)
    - Add `separator` flag per item to render horizontal divider line below that item
    - Add hover state: subtle background tint for inactive items
    - Active state: semi-transparent accent background + accent icon tint
    - Inactive state: icon and label in muted/secondary text color
    - Add dedicated bottom slot area via `setBottomWidget()` for PromoCard or arbitrary widget
    - Items now support: `{"key", "icon", "label", "group": str|None, "separator": bool}`
    - Navigation items use Icon widget (20px) on left and body typography label on right
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 8.2 Implement Ghost and Outlined button variants
    - Add `GhostButton` and `OutlinedButton` classes to `python_app/design_system/widgets/buttons.py`
    - GhostButton: transparent bg, accent text, no border; set `uiRole="ghost"` property
    - OutlinedButton: transparent bg, 1px accent border, accent text; set `uiRole="outlined"` property
    - Both support `danger=True` mode (sets `uiRole="ghostDanger"` / `uiRole="outlinedDanger"`)
    - Both support same size and icon parameters as standard buttons
    - Export from `python_app/design_system/widgets/__init__.py`
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

  - [ ]* 8.3 Write property tests for SidebarNav and button variants (Properties 11, 14)
    - **Property 11: Ghost and Outlined Button Role Mapping** — For any button type and danger flag, uiRole property is set correctly
    - **Property 14: SidebarNav Item Rendering and Separator Flags** — For any valid nav items list, all items render and separator=True items have dividers
    - **Validates: Requirements 8.1, 8.4, 8.7, 12.1, 12.2, 12.6**

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement TableActionButton and IndeterminateProgress widgets
  - [x] 10.1 Create TableActionButton widget
    - Create `python_app/design_system/widgets/table_action_button.py` with `TableActionButton` class
    - Support variants: "ghost", "outlined", "launch" (accent background)
    - Support icon-only mode (no text, reduced padding) and icon-with-text mode
    - Hover displays accent-colored background tint
    - Compact rounded styling for table action columns
    - Export from `python_app/design_system/widgets/__init__.py`
    - _Requirements: 10.3, 10.4, 10.5, 10.6_

  - [x] 10.2 Create IndeterminateProgress widget
    - Create `python_app/design_system/widgets/indeterminate_progress.py` with `IndeterminateProgress` class
    - Implement animated horizontal bar with accent-colored segment sweeping left-to-right
    - Use `QPropertyAnimation` on internal position property for smooth animation
    - Provide `start()` and `stop()` methods
    - Custom `paintEvent` for rendering the animated segment
    - Export from `python_app/design_system/widgets/__init__.py`
    - _Requirements: 14.2, 14.3_

- [x] 11. Extend QSS Generator with new styling rules
  - [x] 11.1 Add tooltip, menu, and table styling to QSS Generator
    - Add `_tooltips()` section builder: `QToolTip` with overlay background, 1px semi-transparent border, 6px radius, body text
    - Add `QMenu` styling: glass-morphism border, overlay background, rounded corners
    - Add `QMenu::item:selected` styling: accent-tinted background
    - Add `QMenu::separator` styling: separator token at reduced opacity
    - Add `_enhanced_tables()` section builder: alternating row backgrounds (odd=surface_raised, even=surface_base)
    - Add column header styling: muted text, smaller font-size (uppercase treatment), bottom border separator
    - _Requirements: 10.1, 10.2, 13.1, 13.2, 13.3, 13.4_

  - [x] 11.2 Add input, progress, and button variant styling to QSS Generator
    - Add `_enhanced_inputs()` section builder: `surface_overlay` background, 1px semi-transparent border, 8px radius, min-height 38px
    - Add placeholder text styling in `text_muted` color
    - Add focus state: accent border + subtle outer glow
    - Add disabled styling: reduced opacity text, sunken background
    - Add `_enhanced_progress()` section builder: sunken background track, accent fill, rounded endpoints, 7px height, centered caption text
    - When value reaches 100%, display full accent fill without animation
    - Add `_ghost_outlined()` section builder: QSS for `uiRole` property selectors
    - Ghost: transparent bg, accent text; hover: semi-transparent accent bg
    - Outlined: transparent bg, accent border; hover: filled accent bg, white text
    - GhostDanger/OutlinedDanger: danger color variants
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 14.1, 14.4, 14.5, 12.3, 12.4_

  - [ ]* 11.3 Write property test for QSS structural completeness (Property 15)
    - **Property 15: QSS Structural Completeness for New Selectors** — For any valid ThemeTokens, QSS contains selectors for QToolTip, ghost, outlined, ghostDanger, outlinedDanger, QProgressBar, and :hover pseudo-states
    - **Validates: Requirements 12.3, 12.4, 13.1, 13.2, 14.1**

- [x] 12. Integration wiring and package exports
  - [x] 12.1 Update package __init__.py exports and wire all components
    - Update `python_app/design_system/widgets/__init__.py` to export all new widgets: Icon, GradientButton, GhostButton, OutlinedButton, StatusBadge, TableActionButton, IndeterminateProgress
    - Update `python_app/design_system/layouts/__init__.py` to export all new layouts: GlassCard, QuickActionCard, QuickActionGrid, StatCard, StatCardGroup, PromoCard
    - Update `python_app/design_system/__init__.py` top-level exports if applicable
    - Verify QSS Generator calls all new section builders in its `generate()` method
    - Ensure global stylesheet application picks up all new rules without code changes in consuming widgets
    - _Requirements: 1.7, 15.6_

  - [ ]* 12.2 Write unit tests for component behaviors
    - Create `python_app/tests/test_ui_component_library_unit.py`
    - Test default dark theme has correct new token values
    - Test GlassCard hover applies border style change
    - Test StatusBadge dot_mode renders 8px circle with no text
    - Test GradientButton has QGraphicsDropShadowEffect attached
    - Test GradientButton disabled removes shadow effect
    - Test Icon fallback behavior when file not found
    - Test IndeterminateProgress animation start/stop
    - Test TableActionButton icon-only vs icon-with-text modes
    - Test SidebarNav bottom slot renders provided widget
    - Test QSS output contains `min-height: 38px` for inputs
    - _Requirements: 2.5, 3.5, 4.2, 4.6, 9.5, 14.3_

  - [ ]* 12.3 Write integration tests for composed widgets
    - Create `python_app/tests/test_ui_component_library_integration.py`
    - Test GlassCard renders correctly inside a parent layout
    - Test QuickActionGrid signal propagation (card click → grid signal)
    - Test SidebarNav with PromoCard in bottom slot renders correctly
    - Test global QSS with new tokens styles all new button variants
    - Test full component tree: GlassCard containing StatCardGroup renders without error
    - _Requirements: 5.3, 8.5, 12.1, 12.2_

- [x] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific visual behaviors, edge cases, and fallback logic
- Integration tests verify Qt runtime rendering and signal propagation through composed widgets
- All widgets use the existing token registry consumption pattern (QSS property selectors + frozen dataclass tokens)
- The GradientButton and PromoCard use custom `paintEvent` with QPainter since QSS doesn't support linear-gradient on QPushButton

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["1.3", "2.2", "3.1"] },
    { "id": 3, "tasks": ["3.2", "4.1", "4.2"] },
    { "id": 4, "tasks": ["4.3", "6.1", "7.1", "7.2"] },
    { "id": 5, "tasks": ["6.2", "7.3", "8.1", "8.2"] },
    { "id": 6, "tasks": ["8.3", "10.1", "10.2"] },
    { "id": 7, "tasks": ["11.1", "11.2"] },
    { "id": 8, "tasks": ["11.3", "12.1"] },
    { "id": 9, "tasks": ["12.2", "12.3"] }
  ]
}
```
