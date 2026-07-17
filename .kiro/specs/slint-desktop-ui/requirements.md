# Requirements Document

## Introduction

Complete rebuild of the existing CAMXORA (MusicGenerator) PyQt6 desktop application UI using the Slint UI framework in Rust. The goal is an exact visual match of the current dark-themed desktop application, reproducing all pages, navigation, design tokens, typography, spacing, and color scheme pixel-for-pixel. The Rust application lives in the `camxora_rust/` folder within the workspace and serves as a modern, high-performance replacement for the Python desktop frontend.

## Glossary

- **App_Shell**: The top-level window container comprising the custom title bar, sidebar navigation, main content area, and footer status bar
- **Sidebar**: The 260px fixed-width left navigation panel containing the user profile section, navigation menu items, and logout button
- **Title_Bar**: The custom frameless window title bar providing brand identity display and window control buttons (minimize, maximize, close)
- **Footer_Bar**: The global status bar at the bottom of the application window displaying contextual status information across three zones (left, center, right)
- **Nav_Item**: A clickable navigation button in the sidebar that switches the visible page in the main content area
- **Design_Token_System**: The set of color, typography, spacing, and shape constants that define the visual theme of the application
- **Page_Stack**: The stacked content area to the right of the sidebar that displays one active page at a time based on navigation selection
- **Profile_Section**: The top portion of the sidebar displaying the user avatar (gradient circle with initials), username, plan badge, and credit balance
- **Settings_Tab_Bar**: The horizontal tab strip within the Settings page allowing switching between sub-pages (Profiles, YouTube, Publication, Preferences, Descriptions, Structures, Pools, Suno)
- **Profile_Panel**: The left panel of the Settings/Profiles tab showing the list of channel profiles with search, profile items, and limit indicator
- **Detail_Panel**: The right panel of the Settings/Profiles tab showing the editable form fields for the currently selected profile
- **Slint_Compiler**: The Slint build tool that compiles `.slint` declarative UI files into native Rust code at build time

## Requirements

### Requirement 1: Rust Project Scaffold

**User Story:** As a developer, I want a well-structured Rust + Slint project in `camxora_rust/`, so that I can build and iterate on the desktop UI with clear module boundaries.

#### Acceptance Criteria

1. THE App_Shell SHALL use a Cargo workspace located at `camxora_rust/` with a single binary crate using Rust edition 2021
2. THE App_Shell SHALL declare `slint` as a runtime dependency and `slint-build` as a build dependency in `Cargo.toml` with pinned versions
3. THE App_Shell SHALL organize `.slint` UI files in a `ui/` subdirectory with at minimum a root `app-window.slint` file that defines the main application window, and separate `.slint` files for each distinct page or reusable component
4. THE App_Shell SHALL provide a `main.rs` entry point that initializes the Slint event loop and displays the main window with a minimum size of 800×600 pixels
5. THE App_Shell SHALL compile successfully with `cargo build` on Windows (stable toolchain) producing zero errors and zero warnings
6. THE App_Shell SHALL include a `build.rs` file that invokes `slint-build` to compile all `.slint` files from the `ui/` subdirectory prior to the main compilation

### Requirement 2: Custom Title Bar

**User Story:** As a user, I want a custom frameless title bar showing the CAMXORA brand and window controls, so that the application has a cohesive branded appearance.

#### Acceptance Criteria

1. THE Title_Bar SHALL render as a frameless window decoration with a height of 38px and background color `#060b20`
2. THE Title_Bar SHALL display the brand name "CAMXORA" in Open Sans 14px bold weight and the subtitle "DESKTOP STUDIO" in Open Sans 11px regular weight with color `#7b8fb5`
3. THE Title_Bar SHALL provide minimize, maximize, and close buttons aligned to the right edge with 30x30px hit areas and a horizontal gap of no more than 2px between each button
4. WHEN the close button is clicked, THE App_Shell SHALL terminate the application process
5. WHEN the maximize button is clicked, THE App_Shell SHALL toggle between maximized and the previous windowed size and position
6. WHEN the minimize button is clicked, THE App_Shell SHALL minimize the window to the system taskbar
7. WHEN the user presses and drags within the title bar area outside of the button hit areas, THE App_Shell SHALL move the application window by the same pixel delta as the pointer movement
8. WHEN the user double-clicks the title bar area outside of the button hit areas, THE App_Shell SHALL toggle between maximized and the previous windowed size and position
9. WHEN the user hovers over a window control button, THE Title_Bar SHALL display a visible hover state within 100ms; WHEN the close button is hovered, the hover state SHALL use a distinct contrasting background color differentiating it from minimize and maximize hover states
10. WHILE the pointer is outside the button hit areas of the Title_Bar, THE Title_Bar SHALL allow window drag initiation and SHALL NOT trigger any button action

### Requirement 3: Sidebar Navigation

**User Story:** As a user, I want a sidebar with navigation items and my profile information, so that I can switch between application pages and see my account status.

#### Acceptance Criteria

1. THE Sidebar SHALL render at a fixed width of 260px, occupying the full height of the application window, with background color `#0A1530`
2. THE Profile_Section SHALL display a 72px circular avatar with a linear gradient background from `#7466F1` to `#A259FF`, showing user initials (first letter of first name and first letter of last name) in 26px bold white text
3. THE Profile_Section SHALL display the username in Open Sans 14px bold weight with color `#eef4ff`, centered below the avatar, truncated with an ellipsis if the username exceeds 20 characters
4. THE Profile_Section SHALL display a plan badge with gold background `#F2C94C`, dark text `#1a1a2e`, font-size 10px bold, padding 2px 8px, border-radius 4px
5. THE Profile_Section SHALL display the credit balance and expiry text in 11px with color `rgba(255,255,255,0.5)` centered below the badge
6. THE Sidebar SHALL render a 1px separator line with color `rgba(255,255,255,0.06)` between the profile section and the navigation menu
7. THE Sidebar SHALL display exactly 10 Nav_Items in order: Dashboard, Profile, Workflow, Progress, Music, Image, Video, Merger, Settings, Log
8. WHILE a Nav_Item is in the default (inactive) state, THE Sidebar SHALL render the Nav_Item label in color `#7b8fb5` with a 20px icon tinted to the same color and a height of 44px
9. WHILE a Nav_Item is in the active state, THE Sidebar SHALL render the Nav_Item with a gradient background from `#7466F1` to `#A259FF`, white label text, and white icon tint
10. WHEN a Nav_Item is clicked, THE App_Shell SHALL switch the Page_Stack to display the corresponding page matching the Nav_Item label and set that Nav_Item to active state while setting all other Nav_Items to default state
11. WHEN the Sidebar is first displayed, THE Sidebar SHALL set the Dashboard Nav_Item to the active state
12. THE Sidebar SHALL display a logout button at the bottom with a red-tinted (`#ef4444`) icon and text, separated by a 1px line from the Nav_Items above
13. WHEN the logout button is clicked, THE App_Shell SHALL end the current user session and navigate to the login screen

### Requirement 4: Main Content Area and Page Stack

**User Story:** As a user, I want the main content area to show the active page content, so that I can interact with different features of the application.

#### Acceptance Criteria

1. THE Page_Stack SHALL occupy the remaining horizontal space to the right of the Sidebar and the full vertical height of the application window
2. THE Page_Stack SHALL display exactly one page at a time, with all other pages hidden, corresponding to the currently active Nav_Item
3. THE Page_Stack SHALL provide a placeholder page for each of the 10 navigation entries (Dashboard, Profile, Workflow, Progress, Music, Image, Video, Merger, Settings, Log), where each placeholder displays the page name as visible text so the active page is identifiable
4. WHEN the application launches, THE Page_Stack SHALL display the Dashboard page by default
5. WHEN the user selects a Nav_Item in the Sidebar, THE Page_Stack SHALL swap the visible page to the corresponding page within one frame (≤16ms rendering time) without animation
6. IF the Page_Stack receives a navigation index that does not correspond to any of the 10 defined pages, THEN THE Page_Stack SHALL remain on the currently displayed page without change

### Requirement 5: Footer Status Bar

**User Story:** As a user, I want a status bar at the bottom of the window, so that I can see contextual application status at a glance.

#### Acceptance Criteria

1. THE Footer_Bar SHALL remain fixed at the bottom of the application window, spanning the full width below the main content area, regardless of content scrolling
2. THE Footer_Bar SHALL have a fixed height of 28px with background color `#060b20` and a 1px top border of color `#263653`
3. THE Footer_Bar SHALL display three text zones: left-aligned, center-aligned, and right-aligned, each in Open Sans 11px with color `#7b8fb5`
4. THE Footer_Bar SHALL accept dynamic text content for each of the three zones, updating the displayed text immediately upon receiving new content
5. IF the text content for any zone exceeds the available zone width, THEN THE Footer_Bar SHALL truncate the text with an ellipsis ("…") without wrapping to a second line
6. IF no text content has been set for a zone, THEN THE Footer_Bar SHALL display that zone as empty with no placeholder text, preserving the layout of the remaining zones

### Requirement 6: Design Token System

**User Story:** As a developer, I want all visual constants defined as reusable tokens in Slint global structs, so that theme consistency is guaranteed and future changes are centralized.

#### Acceptance Criteria

1. THE Design_Token_System SHALL define all color tokens as Slint global properties with the following values: surface_base `#060b20`, surface_raised `#0A1530`, surface_overlay `#101a38`, surface_elevated `#14203e`, text_primary `#eef4ff`, text_secondary `#d9e5fb`, text_muted `#7b8fb5`, accent `#1ABCFE`, secondary_accent `#7466F1`, success `#0ACF83`, warning `#F24E1E`, danger `#FF7262`, border `#263653`
2. THE Design_Token_System SHALL define typography tokens as Slint global properties: font_family "Open Sans", size_title 18px, size_subtitle 14px, size_body 14px, size_caption 11px, weight_regular 400, weight_medium 500, weight_bold 700
3. THE Design_Token_System SHALL define spacing tokens as Slint global properties: padding_sm 4px, padding_md 8px, padding_lg 16px, gap_sm 4px, gap_md 8px, gap_lg 16px, margin_sm 4px, margin_md 12px, margin_lg 24px
4. THE Design_Token_System SHALL define shape tokens as Slint global properties: radius_sm 4px, radius_md 8px, radius_lg 12px, border_width_thin 1px, border_width_medium 2px
5. THE Design_Token_System SHALL expose tokens through a Slint `export global` struct accessible to all component files via qualified property access (e.g., `DesignTokens.accent`), with each token category (colors, typography, spacing, shape) grouped within the same global or into separate named globals
6. WHEN a Slint component file references a color, font size, spacing, radius, or border width value, THE Design_Token_System SHALL ensure that value is sourced from a token global property rather than an inline literal, verified by confirming zero occurrences of raw hex color codes or numeric size literals (other than 0 or 1) in component `.slint` files outside of the token definition file
7. IF a token property defined in criteria 1–4 is missing from the Slint global struct, THEN THE Design_Token_System SHALL fail compilation of any component that references the missing property, providing a compile-time error indicating the undefined token name

### Requirement 7: Settings Page with Tabbed Interface

**User Story:** As a user, I want the Settings page to have a tab bar with multiple sub-pages, so that I can manage different configuration categories.

#### Acceptance Criteria

1. THE Settings_Tab_Bar SHALL display 8 tabs in the following left-to-right order: Profiles, YouTube, Publication, Preferences, Descriptions, Structures, Pools, Suno
2. WHILE a tab is in inactive state, THE Settings_Tab_Bar SHALL render the tab label in color `#7b8fb5` with background transparent
3. WHILE a tab is in active state, THE Settings_Tab_Bar SHALL render the tab label in color `#eef4ff` with a 2px bottom border indicator in color `#1ABCFE`
4. WHEN a tab is clicked, THE Settings_Tab_Bar SHALL set that tab to active state, set all other tabs to inactive state, and display the corresponding sub-page content in the settings content area
5. THE Settings_Tab_Bar SHALL have a height of 44px with a 1px bottom border of color `#263653`
6. WHEN the Settings page is first displayed, THE Settings_Tab_Bar SHALL set the Profiles tab to active state and display the Profiles sub-page content

### Requirement 8: Settings Profiles Sub-Page Layout

**User Story:** As a user, I want the Profiles settings tab to show my channel profiles in a split-panel layout, so that I can browse and edit profile configurations.

#### Acceptance Criteria

1. THE Profile_Panel SHALL render on the left side with a fixed width of 320px and background color `#0A1530`
2. THE Profile_Panel SHALL display a "Your Profiles" header in Open Sans 14px bold with color `#eef4ff`
3. THE Profile_Panel SHALL provide a search input field with placeholder text "Search profiles..." styled with background `#101a38`, border `#263653`, border-radius 8px, and height 36px
4. THE Profile_Panel SHALL display a scrollable list of profile items limited to a maximum of 20 items, each showing a 36px circular colored avatar with the profile name's first two initials, profile name in 14px `#eef4ff`, and subtitle in 11px `#7b8fb5`
5. IF the user's profile count equals their plan-based maximum allowance, THEN THE Profile_Panel SHALL display a "Profile Limit Reached" indicator at the bottom in 11px `#7b8fb5` text
6. WHEN a profile item is clicked, THE Detail_Panel SHALL display the edit form for the selected profile within 200ms
7. WHEN a profile item is selected, THE Profile_Panel SHALL highlight the item with background color `#101a38`
8. THE Detail_Panel SHALL occupy the remaining horizontal space to the right of the Profile_Panel with padding of 24px
9. IF no profile is selected, THEN THE Detail_Panel SHALL display a placeholder state with the text "No profile selected" in 14px `#7b8fb5`
10. THE Detail_Panel SHALL display form fields: Name (text, max 100 characters), Folder name (text, max 100 characters), Run prefix (text, max 50 characters), Channel logo (image selector), Channel cover (image selector), Video template (dropdown), Reel template (dropdown), Output resolution (dropdown), and Image mode (dropdown)
11. THE Detail_Panel SHALL display form labels in Open Sans 11px with color `#7b8fb5` and input fields with background `#101a38`, border `#263653`, border-radius 8px, and height 36px
12. THE Detail_Panel SHALL display a "Save Changes" button styled with accent color `#1ABCFE` and a "Delete" button styled with danger color `#FF7262`
13. IF the user clicks "Delete" on a profile, THEN THE Detail_Panel SHALL display a confirmation prompt before proceeding with deletion

### Requirement 9: Window Geometry and Responsiveness

**User Story:** As a user, I want the application window to have sensible defaults and respond to resizing, so that the UI remains usable at different window dimensions.

#### Acceptance Criteria

1. THE App_Shell SHALL launch with a default window size of 1440x900 pixels, or the display's usable resolution if the display is smaller than 1440x900
2. THE App_Shell SHALL enforce a minimum window size of 1024x640 pixels, preventing the user from resizing the window below these dimensions
3. WHILE the window is resized, THE Page_Stack SHALL occupy a width equal to the window width minus the 260px Sidebar width, and a height equal to the window height minus the Title_Bar height minus the Footer_Bar height
4. WHILE the window is resized, THE Footer_Bar SHALL remain anchored to the bottom edge of the window spanning the full window width
5. WHILE the window is resized, THE Title_Bar SHALL remain anchored to the top edge of the window spanning the full window width
6. WHILE the window is resized, THE Sidebar SHALL maintain a fixed width of 260px and a height equal to the window height minus the Title_Bar height minus the Footer_Bar height

### Requirement 10: File Organization for Maintainability

**User Story:** As a developer, I want the Slint UI files organized by component and page, so that the codebase is navigable and each file has a single responsibility.

#### Acceptance Criteria

1. THE App_Shell SHALL organize the `ui/` directory with the following structure: `ui/main.slint` (root), `ui/theme.slint` (tokens), `ui/components/` (shared widgets), `ui/pages/` (page-level files)
2. THE App_Shell SHALL place each reusable component (title bar, sidebar, footer, nav item, profile card, tab bar, form field) in a separate `.slint` file within `ui/components/`, where each file exports exactly one top-level component and the filename matches the component name in kebab-case (e.g., `title-bar.slint` exports `TitleBar`)
3. THE App_Shell SHALL place each page (dashboard, profile, workflow, progress, music, image, video, merger, settings, log) in a separate `.slint` file within `ui/pages/`, where each file exports exactly one top-level page component and the filename matches the page name in kebab-case (e.g., `dashboard.slint` exports `Dashboard`)
4. THE App_Shell SHALL use Slint `import` statements in `ui/main.slint` to import all page components from `ui/pages/`, and each page file SHALL use `import` statements to reference any shared components it uses from `ui/components/`
5. THE App_Shell SHALL keep all Rust application logic in `src/` with `main.rs` as the single entry point that initializes the Slint UI window and binds Rust callbacks to Slint-declared callbacks
6. IF a `.slint` file within `ui/components/` or `ui/pages/` exceeds 200 lines, THEN THE App_Shell SHALL split it into smaller focused files, each maintaining the single-export-per-file convention
