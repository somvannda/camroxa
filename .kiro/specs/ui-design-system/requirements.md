# Requirements Document

## Introduction

This document defines the requirements for a professional, scalable UI design system for the MusicGenerator PyQt6 desktop application. The design system provides a centralized theme token system, reusable widget components, layout primitives, and QSS stylesheet generation to achieve a modern dark theme with cyan/teal accents, consistent styling, and incremental adoptability across existing views.

## Glossary

- **Design_System**: The complete package of theme tokens, reusable widget components, layout components, QSS generation, and developer documentation that ensures consistent UI across the MusicGenerator application
- **Theme_Token**: A named constant representing a visual design value (color, font size, spacing, border-radius) used as the single source of truth for styling decisions
- **Token_Registry**: The centralized Python module that defines, stores, and provides access to all Theme_Tokens
- **QSS_Generator**: The module that produces Qt Style Sheet strings from Theme_Tokens for application-wide styling
- **Widget_Component**: A reusable, self-contained PyQt6 widget class that encapsulates both structure and styled appearance according to the design system
- **Layout_Component**: A reusable PyQt6 container widget that provides standard structural arrangements (sidebar, panel, toolbar, card) with built-in spacing and styling
- **Theme_Variant**: A complete set of token overrides that changes the visual appearance of the application (e.g., dark theme, light theme)
- **Style_Role**: A dynamic Qt property value applied to a widget that selects a predefined visual treatment from the QSS stylesheet
- **Pattern_Library**: Developer-facing documentation that describes available components, their usage, accepted properties, and visual examples

## Requirements

### Requirement 1: Theme Token Registry

**User Story:** As a developer, I want a centralized registry of design tokens, so that I can reference consistent color, typography, spacing, and shape values throughout the application without hardcoding.

#### Acceptance Criteria

1. THE Token_Registry SHALL define named color tokens for: background surfaces (at least 4 levels), text hierarchy (at least 3 levels), accent/primary, success, warning, danger, and border/separator colors
2. THE Token_Registry SHALL define named typography tokens for: font family, font sizes (at least 4 levels: title, subtitle, body, caption), and font weights (regular, medium, bold)
3. THE Token_Registry SHALL define named spacing tokens for: component padding (at least 3 sizes), layout gaps (at least 3 sizes), and margin values
4. THE Token_Registry SHALL define named shape tokens for: border-radius values (at least 3 sizes: small, medium, large) and border widths
5. THE Token_Registry SHALL expose all tokens as a typed Python dictionary accessible by string key
6. WHEN a token value is changed in the Token_Registry, THE QSS_Generator SHALL produce updated stylesheets reflecting the new value without code changes in consuming widgets
7. THE Token_Registry SHALL provide a frozen default dark theme with cyan/teal accent colors (#00bcd4 range), dark gray backgrounds (#1a1a2e to #16213e range), and white/light text

### Requirement 2: QSS Stylesheet Generation

**User Story:** As a developer, I want stylesheets automatically generated from tokens, so that theme changes propagate everywhere without manually editing QSS strings.

#### Acceptance Criteria

1. THE QSS_Generator SHALL produce a single application-wide QSS string from the current Token_Registry values
2. THE QSS_Generator SHALL generate style rules for all base Qt widget types used in the application: QPushButton, QLabel, QLineEdit, QComboBox, QSlider, QProgressBar, QCheckBox, QTabWidget, QTableWidget, QListWidget, QScrollBar, QSpinBox, QTextEdit, and QMenu
3. THE QSS_Generator SHALL generate style rules for all defined Style_Roles using Qt dynamic property selectors (e.g., `QPushButton[uiRole="primary"]`)
4. THE QSS_Generator SHALL generate hover, pressed, checked, and disabled pseudo-state rules for interactive widgets
5. WHEN the application applies the generated QSS string to QApplication, THE Design_System SHALL style all widgets matching the selectors without per-widget inline stylesheet assignments
6. THE QSS_Generator SHALL produce valid QSS syntax parseable by Qt6 without warnings

### Requirement 3: Button Components

**User Story:** As a developer, I want pre-built button variants, so that I can add consistent call-to-action, secondary, and icon buttons without manual styling.

#### Acceptance Criteria

1. THE Design_System SHALL provide a primary button component with cyan/teal background, white text, rounded corners, and hover/pressed states
2. THE Design_System SHALL provide a secondary button component with transparent/dark background, border, light text, and hover/pressed states
3. THE Design_System SHALL provide a danger button component with red background, white text, and hover/pressed states
4. THE Design_System SHALL provide a success button component with green background, white text, and hover/pressed states
5. THE Design_System SHALL provide an icon button component that displays an SVG icon tinted to the theme color with optional tooltip text
6. THE Design_System SHALL provide a toggle button component with on/off visual states using the checked pseudo-state
7. WHEN a developer creates a button component with a specified variant, THE Widget_Component SHALL apply the correct Style_Role without additional styling code

### Requirement 4: Toggle Switch Component

**User Story:** As a developer, I want a modern toggle switch widget, so that I can replace native checkboxes with a visually polished on/off control.

#### Acceptance Criteria

1. THE Design_System SHALL provide a Toggle_Switch Widget_Component that renders as a rounded track with a sliding circular knob
2. WHEN the Toggle_Switch is in the off state, THE Toggle_Switch SHALL display a dark track with a muted knob color
3. WHEN the Toggle_Switch is in the on state, THE Toggle_Switch SHALL display a cyan/teal track with a white knob
4. WHEN the user clicks the Toggle_Switch, THE Toggle_Switch SHALL animate the knob position transition within 150 milliseconds
5. THE Toggle_Switch SHALL emit a toggled signal with the new boolean state value
6. THE Toggle_Switch SHALL support an optional text label positioned to the left or right of the track
7. THE Toggle_Switch SHALL be accessible via keyboard (Space key toggles state, Tab key provides focus navigation)

### Requirement 5: Custom Slider Component

**User Story:** As a developer, I want styled slider controls for volume, seek, and value adjustment, so that the app has modern progress/range controls consistent with the theme.

#### Acceptance Criteria

1. THE Design_System SHALL provide a Custom_Slider Widget_Component that renders a rounded groove with a circular handle
2. THE Custom_Slider SHALL use theme token colors: muted track background, cyan/teal filled portion, and styled handle with border
3. THE Custom_Slider SHALL support horizontal and vertical orientations
4. WHEN the user drags the handle, THE Custom_Slider SHALL emit a valueChanged signal with the current integer value
5. THE Custom_Slider SHALL display the filled portion of the groove (from minimum to current value) in the accent color
6. THE Custom_Slider SHALL support custom minimum, maximum, and step values configured at instantiation
7. WHEN the Custom_Slider receives keyboard focus, THE Custom_Slider SHALL allow arrow key adjustment by the configured step value

### Requirement 6: Input Field Components

**User Story:** As a developer, I want consistent text input, combo box, and spin box components, so that all form fields share the same visual treatment.

#### Acceptance Criteria

1. THE Design_System SHALL provide a styled text input component with dark background, rounded border, themed placeholder text color, and focus highlight border
2. THE Design_System SHALL provide a styled combo box component with dark dropdown background, themed arrow indicator, and selection highlighting
3. THE Design_System SHALL provide a styled spin box component with themed up/down arrows and consistent border treatment
4. WHEN an input component receives focus, THE Widget_Component SHALL display a visible accent-colored border to indicate focus state
5. THE input components SHALL support a "card" field variant with transparent background for use inside card containers
6. THE input components SHALL support a "standalone" field variant with solid dark background for use on page surfaces

### Requirement 7: Card and Panel Layout Components

**User Story:** As a developer, I want reusable card and panel containers, so that I can organize content into visually distinct sections with consistent spacing and borders.

#### Acceptance Criteria

1. THE Design_System SHALL provide a Card Layout_Component with rounded corners, subtle background differentiation from the page surface, and configurable padding
2. THE Design_System SHALL provide a Panel Layout_Component with optional header area, content area, and configurable border/separator
3. THE Card Layout_Component SHALL accept a title string and render it with the section title typography token
4. WHEN content is added to a Card or Panel, THE Layout_Component SHALL apply the configured internal spacing between child widgets
5. THE Design_System SHALL provide a Section_Divider component that renders a horizontal line using the separator token color

### Requirement 8: Sidebar Navigation Component

**User Story:** As a developer, I want a reusable sidebar navigation component, so that page navigation is consistent and new pages can be added declaratively.

#### Acceptance Criteria

1. THE Design_System SHALL provide a Sidebar_Nav Layout_Component that renders a vertical list of navigation items with icon and text label
2. WHEN a navigation item is in the active state, THE Sidebar_Nav SHALL highlight the item with a distinct background color and white icon tint
3. WHEN a navigation item is in the inactive state, THE Sidebar_Nav SHALL display the item with muted text and icon colors
4. WHEN the user clicks a navigation item, THE Sidebar_Nav SHALL emit a navigation signal with the page identifier string
5. THE Sidebar_Nav SHALL accept navigation items as a list of dictionaries containing: page key, icon name, and display label
6. THE Sidebar_Nav SHALL render each item with consistent height, padding, and icon-to-text spacing defined by layout spacing tokens

### Requirement 9: Typography System

**User Story:** As a developer, I want a typography system with pre-defined text styles, so that headings, body text, and labels are consistent across all views.

#### Acceptance Criteria

1. THE Design_System SHALL provide Label Widget_Components for each typography level: page_title, section_title, subtitle, body, caption, and muted
2. WHEN a developer creates a typed label with a specified level, THE Widget_Component SHALL apply the corresponding font size, weight, and color from typography tokens
3. THE typography system SHALL define a consistent font family applied to all text in the application
4. THE typography labels SHALL support dynamic text updates while retaining the assigned style properties

### Requirement 10: Audio Player Control Components

**User Story:** As a developer, I want reusable audio transport controls (play, pause, skip, seek), so that the audio player section uses themed circular buttons and a styled seek bar.

#### Acceptance Criteria

1. THE Design_System SHALL provide a Transport_Button Widget_Component rendering as a circular button with an SVG icon center-aligned
2. THE Transport_Button SHALL support size variants: small (28px), medium (36px), and large (44px)
3. THE Transport_Button SHALL support a "primary" variant with accent background for the main play/pause action
4. WHEN the user hovers over a Transport_Button, THE Transport_Button SHALL display a lighter background state
5. THE Design_System SHALL provide a Seek_Bar Widget_Component that extends Custom_Slider with time position display (current / total) as adjacent labels
6. THE Seek_Bar SHALL display elapsed time on the left and total duration on the right using the caption typography style

### Requirement 11: Table and List Styling

**User Story:** As a developer, I want consistent table and list widget styling, so that playlist tables and track lists match the dark theme with proper hover and selection states.

#### Acceptance Criteria

1. THE QSS_Generator SHALL produce table styling with transparent background, themed header row (dark background, bold muted text), and row hover highlighting
2. THE QSS_Generator SHALL produce list widget styling with themed selection background (accent color), rounded item corners, and hover state
3. WHEN a table row is hovered, THE table widget SHALL display a subtle background color change using a color between the surface and selection colors
4. THE table header sections SHALL use the subtitle typography weight and muted text color
5. THE QSS_Generator SHALL produce grid line styling using the separator token color

### Requirement 12: Incremental Migration Support

**User Story:** As a developer, I want to migrate existing views to the design system one at a time, so that the app remains functional during the transition without visual breakage.

#### Acceptance Criteria

1. THE Design_System SHALL apply global QSS to QApplication at startup such that unmigrated views receive base theme styling automatically
2. WHEN a developer uses a Design_System Widget_Component inside an existing view, THE Widget_Component SHALL render correctly without requiring the entire view to be migrated
3. THE Design_System SHALL maintain backward compatibility with existing Style_Role property values already used in the codebase (uiRole, uiPanel, uiField)
4. THE Design_System SHALL not override existing inline stylesheets on widgets that have not been migrated to the design system
5. IF a widget has both an inline stylesheet and a design system Style_Role applied, THEN THE Design_System SHALL log a deprecation warning to assist migration tracking

### Requirement 13: Developer Documentation

**User Story:** As a developer, I want a pattern library document describing all available components and usage patterns, so that I can build new views consistently without reading implementation code.

#### Acceptance Criteria

1. THE Pattern_Library SHALL document each Widget_Component with: name, purpose, constructor parameters, available variants, and a code usage example
2. THE Pattern_Library SHALL document each Layout_Component with: name, purpose, constructor parameters, and a layout composition example
3. THE Pattern_Library SHALL document the complete token list organized by category (color, typography, spacing, shape) with visual swatches or hex values
4. THE Pattern_Library SHALL document the migration guide describing how to convert an existing view from inline styling to design system components
5. THE Pattern_Library SHALL be maintained as a Markdown file within the project repository

### Requirement 14: Now Playing Card Component

**User Story:** As a developer, I want a "Now Playing" card component that displays track metadata with album art, so that the audio section has a polished, recognizable layout.

#### Acceptance Criteria

1. THE Design_System SHALL provide a Now_Playing_Card Widget_Component with: album art thumbnail area, track title label, artist/subtitle label, and optional duration label
2. THE Now_Playing_Card SHALL use the Card Layout_Component as its container with accent-bordered left edge or top edge highlight
3. WHEN no album art is available, THE Now_Playing_Card SHALL display a placeholder graphic using the muted background color and a music note icon
4. THE Now_Playing_Card text elements SHALL use the typography system: title level for track name, caption level for artist, and muted level for duration

### Requirement 15: Theme Variant Support

**User Story:** As a developer, I want the token system to support multiple theme variants, so that future light themes or custom color schemes can be added without restructuring.

#### Acceptance Criteria

1. THE Token_Registry SHALL accept a theme variant identifier string to select which set of token values to load
2. THE Token_Registry SHALL provide a "dark" variant as the default containing the full cyan/teal dark theme palette
3. WHEN a new Theme_Variant is registered, THE Token_Registry SHALL validate that the variant provides values for all required token keys
4. IF a Theme_Variant is missing a required token key, THEN THE Token_Registry SHALL raise a descriptive error listing the missing keys
5. THE Design_System SHALL support runtime theme switching by regenerating the QSS string and reapplying it to QApplication
