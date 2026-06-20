# Requirements Document

## Introduction

This document defines requirements for a comprehensive UI component library update to the MusicGenerator PyQt6 desktop application's design system. The update aligns the visual language with a modern, professional dashboard aesthetic: deep navy backgrounds, cyan/teal accents, glass-morphism card surfaces, gradient primary buttons with glow effects, status badges, icon integration, and a full set of reusable higher-level components (quick-action grids, stat cards, promotional cards). The library builds on top of the existing `python_app/design_system/` package (tokens, QSS generator, widget/layout modules) and extends it with new color tokens, component types, and refined styling to match the reference design.

## Glossary

- **Component_Library**: The complete set of reusable styled PyQt6 widgets and layout containers in `python_app/design_system/` that implement the reference design language
- **Design_Token**: A named design constant (color, size, spacing, radius, shadow) stored in the Token_Registry and consumed by the QSS_Generator and widget components
- **Token_Registry**: The centralized registry (`tokens.py`) holding all Design_Tokens as frozen dataclasses with theme variant support
- **QSS_Generator**: The module (`qss_generator.py`) that compiles Design_Tokens into a complete Qt Style Sheet string applied globally
- **Glass_Card**: A card surface with semi-transparent background, subtle border, and slight frosted-glass visual effect achieved via background opacity and border color
- **Status_Badge**: A small colored pill or dot widget indicating item state (active, inactive, premium, warning)
- **Quick_Action_Card**: A clickable card with icon and label arranged in a grid, used for shortcuts/actions
- **Stat_Card**: A key-value display card showing a metric label and value with subtle separator styling
- **Gradient_Button**: A primary button rendered with a linear gradient background and optional outer glow shadow effect
- **Icon_System**: The SVG icon integration layer providing Lucide/Feather-style outlined icons throughout the UI
- **Promo_Card**: A promotional/call-to-action card with gradient background used in sidebar areas (e.g., "Go Premium")
- **Nav_Sidebar**: The left sidebar navigation component with icon+label items, active highlighting, and optional bottom promo card area
- **Surface_Level**: A hierarchical background color tier (base, raised, overlay, sunken, elevated) defining depth in the UI

## Requirements

### Requirement 1: Updated Color Token Palette

**User Story:** As a developer, I want the token palette updated to match the reference design's deep navy color scheme with cyan/teal and purple accents, so that the entire application has the correct foundation colors.

#### Acceptance Criteria

1. THE Token_Registry SHALL define surface color tokens covering at least 5 depth levels: base (#0a0e27 range), raised (#0f1538 range), overlay (#1a1f3a range), sunken (#070b1e range), and elevated (#1e2548 range)
2. THE Token_Registry SHALL define a primary accent color token in the cyan/teal range (#00d4ff to #0ea5e9) with hover, pressed, and glow variants
3. THE Token_Registry SHALL define a secondary accent color token in the purple/violet range (#7c3aed to #a855f7) with hover variant
4. THE Token_Registry SHALL define semi-transparent border tokens for glass-morphism effects (e.g., rgba white at 8-12% opacity expressed as hex-with-alpha or a dedicated border-glass token)
5. THE Token_Registry SHALL define status color tokens for: active (green #10b981), inactive (gray #6b7280), premium (purple #a855f7), and warning (orange #f59e0b)
6. THE Token_Registry SHALL define a glow/shadow color token derived from the primary accent at reduced opacity for button glow effects
7. WHEN the updated tokens are applied, THE QSS_Generator SHALL produce stylesheets using the new palette values without code changes in consuming widgets

### Requirement 2: Glass-Morphism Card Component

**User Story:** As a developer, I want a glass-morphism card component with frosted-glass appearance, so that content sections have the layered, elevated look from the reference design.

#### Acceptance Criteria

1. THE Component_Library SHALL provide a Glass_Card widget with rounded corners (12px radius), semi-transparent background (elevated surface color), and a 1px semi-transparent border
2. THE Glass_Card SHALL accept a title string rendered with section-title typography (bold, 14-16px, white)
3. THE Glass_Card SHALL accept an optional subtitle string rendered with muted typography below the title
4. THE Glass_Card SHALL apply consistent internal padding (16-20px) from spacing tokens to all content
5. WHEN the Glass_Card is hovered, THE Glass_Card SHALL display a subtle border brightness increase to indicate interactivity
6. THE Glass_Card SHALL support a "clickable" mode that emits a clicked signal and applies cursor change on hover
7. THE Glass_Card SHALL support configurable padding and border-radius overrides via constructor parameters

### Requirement 3: Status Badge Component

**User Story:** As a developer, I want small colored status indicator badges, so that I can show item states (active, inactive, premium) consistently across tables and lists.

#### Acceptance Criteria

1. THE Component_Library SHALL provide a Status_Badge widget that renders as a small colored pill with rounded corners (full radius) and text label
2. THE Status_Badge SHALL support predefined variants: "active" (green background + text), "inactive" (gray background + text), "premium" (purple background + text), "warning" (orange background + text)
3. THE Status_Badge SHALL render at a compact size with horizontal padding (6-8px) and vertical padding (2-4px) using caption-level font size
4. WHEN a developer creates a Status_Badge with a variant string, THE Status_Badge SHALL apply the corresponding background color, text color, and border from status tokens
5. THE Status_Badge SHALL support a "dot" mode that renders only a small colored circle (8px diameter) without text for inline status indicators
6. THE Status_Badge SHALL support custom color overrides via optional background_color and text_color parameters

### Requirement 4: Gradient Button with Glow Effect

**User Story:** As a developer, I want a primary call-to-action button with gradient background and glow effect, so that important actions stand out with the polished look from the reference design.

#### Acceptance Criteria

1. THE Component_Library SHALL provide a Gradient_Button widget with a linear gradient background transitioning from the primary accent to a slightly lighter shade
2. THE Gradient_Button SHALL render with a subtle outer glow effect (box-shadow simulation via QGraphicsDropShadowEffect) using the accent glow token color
3. THE Gradient_Button SHALL use rounded corners (8px radius), bold white text, and horizontal padding consistent with standard buttons
4. WHEN the Gradient_Button is hovered, THE Gradient_Button SHALL increase the glow intensity and lighten the gradient stops
5. WHEN the Gradient_Button is pressed, THE Gradient_Button SHALL reduce the glow and darken the gradient stops to provide pressed feedback
6. WHEN the Gradient_Button is disabled, THE Gradient_Button SHALL remove the glow effect and display a muted flat background
7. THE Gradient_Button SHALL support an optional leading icon (SVG path or icon name) rendered to the left of the text label

### Requirement 5: Quick Action Card Grid

**User Story:** As a developer, I want a grid of clickable quick-action cards (icon + label), so that dashboard shortcuts are rendered in the consistent card-grid pattern from the reference design.

#### Acceptance Criteria

1. THE Component_Library SHALL provide a Quick_Action_Card widget that displays a centered icon above a text label within a bordered card container
2. THE Quick_Action_Card SHALL use Glass_Card styling (rounded corners, semi-transparent border, subtle background differentiation)
3. WHEN the user clicks a Quick_Action_Card, THE Quick_Action_Card SHALL emit an action_triggered signal with the action identifier string
4. WHEN the user hovers a Quick_Action_Card, THE Quick_Action_Card SHALL display a border highlight using the accent color at reduced opacity
5. THE Component_Library SHALL provide a Quick_Action_Grid layout widget that arranges Quick_Action_Cards in a responsive grid with configurable column count and gap spacing
6. THE Quick_Action_Grid SHALL accept a list of action descriptors (each containing: key, icon_name, label) and render one Quick_Action_Card per item

### Requirement 6: Stat/Metric Display Card

**User Story:** As a developer, I want a stat card component showing key-value pairs with clean formatting, so that system info and metrics are displayed in the consistent style from the reference design.

#### Acceptance Criteria

1. THE Component_Library SHALL provide a Stat_Card widget that displays a metric label (muted text, caption size) above a metric value (primary text, subtitle/body size, bold)
2. THE Stat_Card SHALL use a compact card container with consistent padding from spacing tokens
3. THE Stat_Card SHALL support an optional icon rendered to the left of the label/value pair using the accent color
4. THE Component_Library SHALL provide a Stat_Card_Group layout that arranges multiple Stat_Cards horizontally or vertically with subtle separators between items
5. THE Stat_Card_Group SHALL accept a list of stat descriptors (each containing: label, value, optional icon_name) and render one Stat_Card per item
6. WHEN the stat value changes via a setValue method, THE Stat_Card SHALL update the displayed text without recreating the widget

### Requirement 7: Promotional/CTA Sidebar Card

**User Story:** As a developer, I want a promotional card with gradient background for sidebar CTAs (like "Go Premium"), so that upsell and call-to-action elements match the reference design.

#### Acceptance Criteria

1. THE Component_Library SHALL provide a Promo_Card widget with a gradient background (purple-to-blue or configurable gradient stops)
2. THE Promo_Card SHALL display a title (bold, white), description text (muted/light), and an action button
3. THE Promo_Card SHALL use rounded corners (12px radius) consistent with Glass_Card styling
4. WHEN the user clicks the Promo_Card action button, THE Promo_Card SHALL emit an action_clicked signal
5. THE Promo_Card SHALL support an optional icon or badge displayed alongside the title
6. THE Promo_Card SHALL accept configurable gradient start and end colors via constructor parameters

### Requirement 8: Enhanced Sidebar Navigation

**User Story:** As a developer, I want the sidebar navigation enhanced with active-state highlighting, icon tinting, compact spacing, and an optional promo card slot at the bottom, so that it matches the reference design's navigation pattern.

#### Acceptance Criteria

1. THE Nav_Sidebar SHALL render navigation items with a Lucide-style outlined icon (20px) on the left and text label on the right using body typography
2. WHEN a navigation item is active, THE Nav_Sidebar SHALL highlight the item row with a semi-transparent accent background and tint the icon to the accent color
3. WHEN a navigation item is inactive, THE Nav_Sidebar SHALL display the icon and label in muted/secondary text color
4. THE Nav_Sidebar SHALL support item grouping with optional group header labels rendered in uppercase muted text (caption size)
5. THE Nav_Sidebar SHALL provide a dedicated bottom slot area for a Promo_Card or arbitrary widget
6. WHEN the user hovers an inactive navigation item, THE Nav_Sidebar SHALL display a subtle background tint without changing icon color
7. THE Nav_Sidebar SHALL accept a separator flag per item to render a horizontal divider line below that item

### Requirement 9: Icon Integration System

**User Story:** As a developer, I want a consistent icon system using Lucide/Feather-style outlined SVG icons with color tinting support, so that icons throughout the UI are stylistically cohesive and themeable.

#### Acceptance Criteria

1. THE Component_Library SHALL provide an Icon widget that renders an SVG icon from a named icon set at a specified size (default 20px)
2. THE Icon widget SHALL support color tinting by applying the specified color token to the SVG fill or stroke attribute
3. THE Icon widget SHALL support size variants: small (16px), medium (20px), large (24px), and xlarge (32px)
4. THE Icon widget SHALL load icons from a local SVG asset directory (`python_app/assets/icons/`) by icon name
5. IF the requested icon name does not exist in the asset directory, THEN THE Icon widget SHALL render a placeholder fallback icon and log a warning
6. THE Icon widget SHALL support an optional opacity parameter (0.0 to 1.0) for muted/decorative icon usage

### Requirement 10: Enhanced Table Styling with Action Columns

**User Story:** As a developer, I want table styling that includes per-row action buttons, alternating subtle row backgrounds, and styled column headers matching the reference design, so that data tables look polished and functional.

#### Acceptance Criteria

1. THE QSS_Generator SHALL produce table row styling with alternating backgrounds: odd rows using surface_raised, even rows using surface_base
2. THE QSS_Generator SHALL produce column header styling with muted text color, uppercase font treatment (via font-size reduction), and bottom border separator
3. THE Component_Library SHALL provide a Table_Action_Button widget rendered as a compact, rounded button (ghost or outlined style) for use in table action columns
4. THE Table_Action_Button SHALL support icon-only mode (rendering a single icon without text) and icon-with-text mode
5. WHEN the user hovers a Table_Action_Button, THE Table_Action_Button SHALL display an accent-colored background tint
6. THE Component_Library SHALL provide a "Launch" button variant for Table_Action_Button that uses the primary accent color as background

### Requirement 11: Updated Input Field Styling

**User Story:** As a developer, I want input fields styled with deeper dark backgrounds and the reference design's border treatment, so that forms match the overall visual language.

#### Acceptance Criteria

1. THE QSS_Generator SHALL produce input field styling with surface_overlay background (#1a1f3a range), 1px semi-transparent border, and 8px border-radius
2. THE QSS_Generator SHALL produce placeholder text styling in the muted text color token
3. WHEN an input field receives focus, THE input field SHALL display a 1px accent-colored border with a subtle outer glow effect
4. THE QSS_Generator SHALL produce disabled input styling with reduced opacity text and sunken background
5. THE input components SHALL match the reference design's 36-40px minimum height for comfortable touch/click targets

### Requirement 12: Ghost and Outlined Button Variants

**User Story:** As a developer, I want ghost (text-only) and outlined (border-only) button variants in addition to filled buttons, so that secondary actions use the subtler button styles from the reference design.

#### Acceptance Criteria

1. THE Component_Library SHALL provide a Ghost_Button variant with transparent background, accent-colored text, no border, and hover background tint
2. THE Component_Library SHALL provide an Outlined_Button variant with transparent background, 1px accent-colored border, accent text, and filled background on hover
3. WHEN a Ghost_Button is hovered, THE Ghost_Button SHALL display a semi-transparent accent background tint
4. WHEN an Outlined_Button is hovered, THE Outlined_Button SHALL fill with the accent color and switch text to white
5. THE Ghost_Button and Outlined_Button SHALL support the same size and icon parameters as standard button components
6. THE Ghost_Button and Outlined_Button SHALL support a "danger" color mode that uses danger token colors instead of accent colors

### Requirement 13: Tooltip and Popover Styling

**User Story:** As a developer, I want tooltips and popover menus styled with the dark glass-morphism treatment, so that contextual information overlays match the overall design language.

#### Acceptance Criteria

1. THE QSS_Generator SHALL produce QToolTip styling with overlay surface background, 1px semi-transparent border, 6px border-radius, and body text styling
2. THE QSS_Generator SHALL produce QMenu styling consistent with the glass-morphism card treatment: overlay background, semi-transparent border, rounded corners
3. THE QSS_Generator SHALL produce QMenu item hover styling using the selection color with accent-tinted background
4. THE QSS_Generator SHALL produce QMenu separator styling using the separator token color at reduced opacity

### Requirement 14: Progress and Loading Indicators

**User Story:** As a developer, I want themed progress bars and loading indicators, so that async operation feedback matches the design system.

#### Acceptance Criteria

1. THE QSS_Generator SHALL produce progress bar styling with sunken background track, accent-colored fill chunk, rounded endpoints, and 6-8px height
2. THE Component_Library SHALL provide an Indeterminate_Progress widget that displays a continuous accent-colored animation indicating loading state
3. THE Indeterminate_Progress widget SHALL use a horizontal bar with animated accent-colored segment that sweeps left-to-right repeatedly
4. WHEN the progress value reaches 100%, THE progress bar SHALL display the full accent-colored fill without animation
5. THE progress bar text (percentage) SHALL use caption typography in primary text color, centered within the bar

### Requirement 15: Token and Component Consistency Validation

**User Story:** As a developer, I want validation that ensures tokens and components stay internally consistent, so that theme changes do not produce broken or mismatched visual output.

#### Acceptance Criteria

1. WHEN a Theme_Variant is registered, THE Token_Registry SHALL validate that all required color tokens produce valid hex color strings matching the pattern #RRGGBB or #RRGGBBAA
2. WHEN a Theme_Variant is registered, THE Token_Registry SHALL validate that typography size tokens are positive integers within the range 8-72
3. WHEN a Theme_Variant is registered, THE Token_Registry SHALL validate that spacing tokens are non-negative integers within the range 0-64
4. WHEN a Theme_Variant is registered, THE Token_Registry SHALL validate that shape radius tokens are non-negative integers within the range 0-32
5. IF any token value fails validation, THEN THE Token_Registry SHALL raise a ValueError listing all invalid tokens with their values and expected constraints
6. THE QSS_Generator SHALL produce output where every referenced color token value from the active theme appears verbatim in the generated QSS string

