# Implementation Plan: Unified Style System

## Overview

Consolidate MusicGenerator's seven competing style sources into a single Master QSS pipeline (`ThemeTokens → QSSGenerator → QApplication.setStyleSheet()`), extend that pipeline with new section builders for the app shell (title bar, sidebar, login screen), and migrate all inline `setStyleSheet()` calls to property-selector-based styling. The implementation follows a strict dependency order: foundation tokens → QSS generators → legacy deprecation → shell component rebuilds → inline style migration → verification.

## Tasks

- [x] 1. Foundation — Token additions and QSS generator extensions
  - [x] 1.1 Add 6 new ColorTokens fields to the frozen dataclass
    - Add `nav_active_gradient_start` (`#7c3aed`), `nav_active_gradient_end` (`#a855f7`), `brand_gradient_start` (`#4c1d95`), `brand_gradient_mid` (`#6d28d9`), `brand_gradient_end` (`#a855f7`), `title_bar_bg` (`#0a0e27`) fields to `ColorTokens` in `python_app/design_system/tokens.py`
    - Update `DEFAULT_DARK_THEME` construction to include the 6 new field values
    - Extend `TokenRegistry.as_dict()` to include flat-key mappings for the new fields (`nav_active_start`, `nav_active_end`, `brand_gradient_start`, `brand_gradient_mid`, `brand_gradient_end`, `title_bar_bg`)
    - Ensure `validate_variant()` validates the new fields with the same hex-color regex
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 1.2 Implement `_title_bar()` section builder in QSSGenerator
    - Add the `_title_bar()` method to `QSSGenerator` in `python_app/design_system/qss_generator.py`
    - Produce QSS for `QWidget[uiPanel="titleBar"]` (40px height, `title_bar_bg` background, no border)
    - Produce QSS for `QToolButton[uiRole="windowControl"]` (transparent bg, 32×28 fixed size, hover overlay)
    - Produce QSS for `QToolButton[uiRole="windowClose"]` (extends windowControl with danger-red hover)
    - Produce QSS for `QLabel[uiRole="appTitle"]` (brand title styling)
    - Register the new method call in `generate()`
    - _Requirements: 3.1, 3.2_

  - [x] 1.3 Implement `_sidebar_nav()` section builder in QSSGenerator
    - Add the `_sidebar_nav()` method to `QSSGenerator`
    - Produce QSS for `QWidget[uiPanel="sidebar"]` (fixed 200px max-width, `surface_base` background)
    - Produce QSS for `QPushButton[uiRole="navItem"]` (icon+text layout, 12px font, 20px icon, transparent bg)
    - Produce QSS for `QPushButton[uiRole="navItem"]:hover` (`surface_overlay` background)
    - Produce QSS for `QPushButton[uiRole="navItemActive"]` (purple gradient pill using `nav_active_gradient_start` → `nav_active_gradient_end`)
    - Produce QSS for `QWidget[uiPanel="userProfile"]` (bottom-anchored section, muted text)
    - _Requirements: 3.3, 3.4, 3.5_

  - [x] 1.4 Implement `_login_shell()` section builder in QSSGenerator
    - Add the `_login_shell()` method to `QSSGenerator`
    - Produce QSS for `QWidget[uiPanel="brandGradient"]` (purple gradient using `brand_gradient_start` → `brand_gradient_mid` → `brand_gradient_end`)
    - Produce QSS for `QWidget[uiPanel="loginTabBar"]` (dark semi-transparent container with glass border)
    - Produce QSS for `QPushButton[uiRole="loginTabActive"]` (purple gradient pill, white text, bold)
    - Produce QSS for `QPushButton[uiRole="loginTabInactive"]` (transparent bg, muted text, hover tint)
    - Produce QSS for `QLineEdit[uiField="loginInput"]` (48px height, 15px font, `secondary_accent_hover` focus border)
    - _Requirements: 3.6, 3.7_

  - [x] 1.5 Implement `_gradient_buttons()` section builder in QSSGenerator
    - Add the `_gradient_buttons()` method to `QSSGenerator`
    - Produce QSS for `QPushButton[uiRole="gradientPrimary"]` (purple gradient matching brand gradient, white text, 44px height, 8px radius)
    - Produce QSS for hover, pressed, and disabled states
    - _Requirements: 2.3_

  - [x]* 1.6 Write property test for QSS Completeness (Property 1)
    - **Property 1: QSS Completeness — All Shell Selectors Present with Token-Derived Values**
    - Use `@st.composite` to generate random valid `ThemeTokens` with randomized hex colors
    - Assert QSS string contains all 14 new selectors and their corresponding token values
    - **Validates: Requirements 2.1, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**

  - [x]* 1.7 Write property test for Legacy Selector Preservation (Property 2)
    - **Property 2: QSS Legacy Selector Preservation**
    - Use random `ThemeTokens` generator
    - Assert QSS string contains all 25+ legacy selector strings (`appRoot`, `appHeader`, `sidebarLeft`, `sidebarRight`, `appNav`, `center`, `footer`, `section`, `softSection`, `primary`, `secondary`, `danger`, `success`, `warning`, `toolbar`, `toggle`, `transport`, `transportPrimary`, `compactSecondary`, `tableIcon`, `appNavButton`, `headerLogout`, `trackList`, `card`, `standalone`)
    - **Validates: Requirements 7.2, 7.3**

  - [x]* 1.8 Write property test for Token Hex Format Enforcement (Property 6)
    - **Property 6: Token Validator Hex Format Enforcement**
    - Use `st.from_regex(r"^#[0-9a-fA-F]{6,8}$")` for valid cases, `st.text()` for invalid
    - Assert validator errors empty for valid hex, non-empty for invalid
    - **Validates: Requirements 8.7**

- [x] 2. Bridge — Legacy deprecation and style helper updates
  - [x] 2.1 Deprecate legacy theme module functions
    - Replace `build_ui_tokens()` body in `python_app/app/theme.py` with a `DeprecationWarning` that delegates to `TokenRegistry.as_dict()`
    - Replace `build_app_stylesheet()` body with a `DeprecationWarning` that returns an empty string
    - Ensure both functions retain their existing signatures for backward compatibility
    - _Requirements: 1.2, 1.3, 1.4_

  - [x] 2.2 Refactor `apply_cta_button()` to use property roles instead of inline QSS
    - Update `apply_cta_button()` in `python_app/views/helpers/style_helper.py` to remove the `setStyleSheet()` call
    - Map variant `"primary"` to `set_button_role(button, "gradientPrimary")`
    - Map `"success"` and `"warning"` to their existing roles (already in QSS)
    - Retain `setCursor` and `setMinimumHeight` logic
    - _Requirements: 2.6_

  - [x]* 2.3 Write property test for TokenRegistry.as_dict() Key Compatibility (Property 3)
    - **Property 3: TokenRegistry.as_dict() Key Compatibility**
    - Use random `ThemeTokens` generator
    - Assert `set(as_dict().keys()) >= LEGACY_KEYS` (37+ legacy keys) and all values are non-empty `str`
    - **Validates: Requirements 1.3, 7.4**

  - [x]* 2.4 Write property test for Style Helper Property Assignment Round-Trip (Property 4)
    - **Property 4: Style Helper Property Assignment Round-Trip**
    - Use `st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N")))` for role strings
    - Assert `set_panel_role(widget, role)` results in `widget.property("uiPanel") == role`, and equivalent for `set_button_role`/`set_label_role`/`set_field_role`
    - **Validates: Requirements 7.1**

- [x] 3. Checkpoint — Verify foundation and bridge layers
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Shell Component Rebuilds — Title bar, sidebar, login
  - [x] 4.1 Rebuild the title bar widget using property selectors
    - Refactor `_build_title_bar()` in `python_app/app/init_orchestrator.py` to use `set_panel_role(widget, "titleBar")` and `set_button_role(btn, "windowControl")`/`set_button_role(close_btn, "windowClose")`
    - Remove any inline `setStyleSheet()` calls from the title bar construction
    - Ensure title bar height is 40px, contains logo SVG + app name on left, window controls on right
    - Retain window drag and double-click maximize behavior
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x] 4.2 Rebuild the sidebar navigation using property selectors
    - Refactor `_build_primary_navigation_shell()` in `python_app/views/core_view.py` to use `set_panel_role(widget, "sidebar")` and `set_button_role(btn, "navItem")`
    - Implement active state switching: `set_button_role(active_btn, "navItemActive")` on navigation click
    - Add user profile section at the bottom with `set_panel_role(profile_widget, "userProfile")`
    - Remove all inline `setStyleSheet()` calls from sidebar construction
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x]* 4.3 Write property test for Sidebar Active State Toggle Exclusivity (Property 5)
    - **Property 5: Sidebar Active State Toggle Exclusivity**
    - Use `st.lists(st.text(min_size=1, max_size=20), min_size=2, max_size=10, unique=True)` for nav keys
    - Assert exactly one button has `navItemActive`, all others have `navItem`
    - **Validates: Requirements 5.3**

  - [x] 4.4 Rebuild login view to use property selectors exclusively
    - Replace all `setStyleSheet()` calls in `python_app/views/login_view.py` with property role assignments:
      - `set_panel_role(brand_panel, "brandGradient")` for the left brand panel
      - `set_panel_role(tab_container, "loginTabBar")` for the tab bar
      - `set_button_role(login_tab, "loginTabActive")` / `set_button_role(register_tab, "loginTabInactive")` for tabs
      - `set_field_role(input, "loginInput")` for all form inputs
      - `set_button_role(submit_btn, "gradientPrimary")` for submit buttons
    - Remove `_apply_tab_style()` method's inline QSS, replace with role toggling
    - Remove `_gradient_button_qss()` method entirely (no longer needed)
    - Retain window drag, double-click maximize, and DWM rounded corners logic
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

- [x] 5. Checkpoint — Verify shell component rebuilds
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Inline Style Migration — Remove remaining setStyleSheet calls from views
  - [x] 6.1 Audit and remove inline setStyleSheet calls from all view files
    - Search `python_app/views/` for all remaining `.setStyleSheet(` calls
    - For each occurrence, replace with the appropriate `set_*_role()` helper call using an existing or new property selector
    - If a required property selector does not exist in the QSS generator, add it to the appropriate section builder
    - _Requirements: 2.1, 2.2_

  - [x] 6.2 Remove legacy theme imports from non-test code
    - Search for `from python_app.app.theme import` in all non-test files
    - Replace `build_ui_tokens()` calls with `TokenRegistry().as_dict()`
    - Remove any calls to `build_app_stylesheet()`
    - Verify `apply_theme()` in `python_app/design_system/bootstrap.py` is the sole style application point
    - _Requirements: 1.1, 1.2_

  - [x] 6.3 Verify backward compatibility of existing style helper API
    - Confirm `set_panel_role`, `set_button_role`, `set_label_role`, `set_field_role` retain existing function signatures
    - Confirm `TokenRegistry.as_dict()` returns all legacy keys with non-empty values
    - Run the existing test suite (156 tests) to verify no regressions
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 7. Final Checkpoint — Full regression verification
  - Ensure all tests pass, ask the user if questions arise.
  - Run static analysis: grep `python_app/views/` for `.setStyleSheet(` — must return 0 hits
  - Run static analysis: grep for `from python_app.app.theme import` in non-test code — must return 0 hits

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each layer
- Property tests validate universal correctness properties from the design document using Hypothesis
- Unit tests validate specific examples and edge cases
- The implementation language is Python (PyQt6) as specified by the design document
- All new QSS selectors use the dynamic property pattern (`uiPanel`, `uiRole`, `uiField`) consistent with the existing style helper API

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "1.5"] },
    { "id": 2, "tasks": ["1.6", "1.7", "1.8", "2.1", "2.2"] },
    { "id": 3, "tasks": ["2.3", "2.4"] },
    { "id": 4, "tasks": ["4.1", "4.2", "4.4"] },
    { "id": 5, "tasks": ["4.3"] },
    { "id": 6, "tasks": ["6.1", "6.2"] },
    { "id": 7, "tasks": ["6.3"] }
  ]
}
```
