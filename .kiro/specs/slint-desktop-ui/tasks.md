# Implementation Plan: Slint Desktop UI

## Overview

Rebuild the CAMXORA desktop application UI using the Slint UI framework in Rust. The implementation follows a bottom-up approach: project scaffold → design tokens → individual components → page assembly → window management → settings page with tabbed sub-pages. All code lives in `camxora_rust/`.

## Tasks

- [x] 1. Set up Rust project scaffold and build pipeline
  - [x] 1.1 Initialize Cargo project with Slint dependencies
    - Create `camxora_rust/Cargo.toml` with binary crate, edition 2021, `slint` dependency (pinned 1.12.x), and `slint-build` as build dependency
    - Create `camxora_rust/src/main.rs` with minimal Slint window initialization and event loop
    - Create `camxora_rust/build.rs` invoking `slint_build::compile("ui/main.slint")`
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6_

  - [x] 1.2 Create UI directory structure and root Slint file
    - Create `camxora_rust/ui/main.slint` with a minimal `AppWindow` component (Window with no-frame, preferred/min sizes)
    - Create empty directories: `ui/components/`, `ui/pages/`
    - Create placeholder `ui/theme.slint` with an empty `DesignTokens` global
    - Verify `cargo build` compiles successfully with zero errors and zero warnings
    - _Requirements: 1.3, 1.5, 10.1_

- [x] 2. Implement design token system
  - [x] 2.1 Define all design tokens in `ui/theme.slint`
    - Implement `export global DesignTokens` with all color tokens (surface_base, surface_raised, surface_overlay, surface_elevated, text_primary, text_secondary, text_muted, accent, secondary_accent, success, warning, danger, border, gradient_start, gradient_end, badge_gold, badge_text, logout_red)
    - Implement typography tokens (font_family, size_title, size_subtitle, size_body, size_caption, weight_regular, weight_medium, weight_bold)
    - Implement spacing tokens (padding_sm/md/lg, gap_sm/md/lg, margin_sm/md/lg)
    - Implement shape tokens (radius_sm/md/lg, border_width_thin, border_width_medium)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 3. Implement core UI components
  - [x] 3.1 Create the NavItem component (`ui/components/nav-item.slint`)
    - Implement 44px height nav button with icon (20px), label text, active/inactive states
    - Active state: gradient background (#7466F1→#A259FF), white text/icon
    - Inactive state: transparent background, muted text/icon color
    - Support `is-danger` property for logout button styling (red tint)
    - Emit `clicked` callback on TouchArea click
    - All colors/sizes sourced from DesignTokens
    - _Requirements: 3.8, 3.9, 3.10_

  - [x] 3.2 Create the ProfileCard component (`ui/components/profile-card.slint`)
    - Implement 72px circular avatar with linear gradient background, showing initials in 26px bold white
    - Display username (14px bold, text_primary), truncated with ellipsis at 20 chars
    - Display plan badge (gold background, dark text, 10px bold, 4px radius)
    - Display credits/expiry text (11px, 50% opacity white)
    - All values sourced from DesignTokens
    - _Requirements: 3.2, 3.3, 3.4, 3.5_

  - [x] 3.3 Create the TitleBar component (`ui/components/title-bar.slint`)
    - Implement 38px height bar with surface_base background
    - Brand section: "CAMXORA" (14px bold, text_primary) + "DESKTOP STUDIO" (11px regular, text_muted)
    - Window control buttons: minimize, maximize, close (30×30px hit areas, 2px gap)
    - Close button hover: distinct contrasting background color
    - TouchArea for drag region (excluding button hit areas)
    - Double-click on drag area emits maximize-toggle
    - Callbacks: on-close, on-minimize, on-maximize-toggle
    - _Requirements: 2.1, 2.2, 2.3, 2.7, 2.8, 2.9, 2.10_

  - [x] 3.4 Create the FooterBar component (`ui/components/footer-bar.slint`)
    - Implement 28px height bar with surface_base background and 1px top border (border color)
    - Three text zones: left-aligned, center-aligned, right-aligned (11px, text_muted)
    - Text overflow: elide (truncate with ellipsis)
    - Accept dynamic text via `left-text`, `center-text`, `right-text` properties
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 3.5 Create the Sidebar component (`ui/components/sidebar.slint`)
    - Implement 260px fixed width with surface_raised background
    - Include ProfileCard at top
    - 1px separator (rgba(255,255,255,0.06)) between profile and nav items
    - 10 NavItems in order: Dashboard, Profile, Workflow, Progress, Music, Image, Video, Merger, Settings, Log
    - Active state tracking via `current-page` in-out property
    - Logout button at bottom with red tint, separated by 1px line
    - Emit navigation callbacks to update current-page
    - _Requirements: 3.1, 3.6, 3.7, 3.10, 3.11, 3.12, 3.13_

- [x] 4. Checkpoint - Verify component compilation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement page placeholders and page stack
  - [x] 5.1 Create placeholder page components (`ui/pages/`)
    - Create 10 page files: `dashboard.slint`, `profile.slint`, `workflow.slint`, `progress.slint`, `music.slint`, `image.slint`, `video.slint`, `merger.slint`, `settings.slint`, `log.slint`
    - Each page exports a single component displaying the page name as centered text
    - Each page imports DesignTokens for consistent styling
    - _Requirements: 4.3, 10.3_

  - [x] 5.2 Assemble the root AppWindow with page stack (`ui/main.slint`)
    - Import all page components and shared components (TitleBar, Sidebar, FooterBar)
    - Implement VerticalLayout: TitleBar → HorizontalLayout(Sidebar + PageStack) → FooterBar
    - Page stack uses conditional visibility (`visible: current-page == N`) for each of the 10 pages
    - Wire Sidebar `current-page` property bidirectionally to root `current-page`
    - Wire TitleBar callbacks (on-close, on-minimize, on-maximize-toggle)
    - Wire FooterBar text properties
    - _Requirements: 4.1, 4.2, 4.4, 4.5, 4.6, 10.4_

- [x] 6. Implement Rust window management logic (`src/main.rs`)
  - [x] 6.1 Bind window control callbacks in Rust
    - Implement `on_close_requested` → `slint::quit_event_loop()`
    - Implement `on_minimize_requested` → `window().set_minimized(true)`
    - Implement `on_maximize_toggle_requested` → toggle `window().is_maximized()`
    - Set default window size 1440×900 (or display usable resolution if smaller)
    - Enforce minimum size 1024×640 via Slint min-width/min-height
    - _Requirements: 2.4, 2.5, 2.6, 9.1, 9.2_

  - [ ]* 6.2 Write unit tests for window management logic
    - Test navigation index validation (clamp/reject out-of-range values)
    - Test that minimize/maximize/close callbacks are wired correctly
    - _Requirements: 2.4, 2.5, 2.6, 4.6_

- [x] 7. Checkpoint - Verify full app shell builds and runs
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement Settings page with tabbed interface
  - [x] 8.1 Create the TabBar component (`ui/components/tab-bar.slint`)
    - Implement 44px height tab bar with 1px bottom border
    - Render tab labels: inactive = text_muted, active = text_primary with 2px bottom accent indicator
    - Accept `tabs` string array and `active-tab` in-out property
    - Emit tab-switched callback on click
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 8.2 Create the FormField component (`ui/components/form-field.slint`)
    - Implement reusable form field with label (11px, text_muted) and input (36px height, surface_overlay background, border color, 8px radius)
    - Support text input with max-length enforcement
    - Support dropdown variant for selection fields
    - _Requirements: 8.10, 8.11_

  - [x] 8.3 Implement the Settings page with tab switching (`ui/pages/settings.slint`)
    - Include TabBar with 8 tabs: Profiles, YouTube, Publication, Preferences, Descriptions, Structures, Pools, Suno
    - Implement conditional visibility for 8 sub-page content areas
    - Default to Profiles tab active on first display
    - _Requirements: 7.1, 7.4, 7.5, 7.6_

  - [x] 8.4 Implement Profiles sub-page split panel layout
    - Profile_Panel (left, 320px): header "Your Profiles" (14px bold), search input (36px, placeholder "Search profiles..."), scrollable profile list (max 20 items)
    - Each profile item: 36px circular avatar with initials, name (14px text_primary), subtitle (11px text_muted)
    - Selected profile highlighted with surface_overlay background
    - Profile limit indicator when at max capacity
    - Detail_Panel (right, fills remaining): padding 24px, form fields (Name, Folder name, Run prefix, Channel logo, Channel cover, Video template, Reel template, Output resolution, Image mode)
    - "No profile selected" placeholder state
    - Save Changes button (accent color) and Delete button (danger color)
    - Delete confirmation prompt
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 8.11, 8.12, 8.13_

- [x] 9. Checkpoint - Verify Settings page and all tabs
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Implement property-based tests and static analysis
  - [ ]* 10.1 Write property test for navigation state exclusivity
    - **Property 4: Navigation State Exclusivity**
    - Test that for any valid page index (0–9), setting current-page results in exactly that index being active
    - **Validates: Requirements 3.10, 4.2**

  - [ ]* 10.2 Write property test for invalid navigation index rejection
    - **Property 5: Invalid Navigation Index Rejection**
    - Test that any integer outside 0–9 leaves current page unchanged
    - **Validates: Requirements 4.6**

  - [ ]* 10.3 Write property test for username truncation
    - **Property 3: Username Truncation at Boundary**
    - Test that strings >20 chars are truncated with ellipsis, ≤20 chars displayed in full
    - **Validates: Requirements 3.3**

  - [ ]* 10.4 Write property test for footer text round-trip
    - **Property 6: Footer Text Binding Round-Trip**
    - Test that any string assigned to a footer zone property is exactly displayed
    - **Validates: Requirements 5.4**

  - [ ]* 10.5 Write property test for profile list display limit
    - **Property 9: Profile List Display Limit**
    - Test that for any N profiles, at most min(N, 20) are displayed
    - **Validates: Requirements 8.4**

  - [ ]* 10.6 Write property test for tab switching exclusivity
    - **Property 8: Tab Switching Exclusivity**
    - Test that for any valid tab index (0–7), exactly one tab shows active indicator
    - **Validates: Requirements 7.4**

  - [ ]* 10.7 Write static analysis test for no inline hex literals
    - **Property 7: No Inline Hex Literals in Component Files**
    - Scan ui/components/ and ui/pages/ for raw hex color codes or numeric pixel literals
    - **Validates: Requirements 6.6**

  - [ ]* 10.8 Write static analysis test for file size constraint
    - **Property 11: File Size Constraint**
    - Verify no .slint file in ui/components/ or ui/pages/ exceeds 200 lines
    - **Validates: Requirements 10.6**

- [x] 11. Final integration verification
  - [x] 11.1 Wire all components and verify full build
    - Ensure all imports are correct in `ui/main.slint`
    - Verify `cargo build` produces zero errors and zero warnings
    - Verify the application binary starts and creates a window
    - Confirm all .slint files compile without errors
    - Verify directory structure matches requirement 10 (components/ and pages/ organization, single-export-per-file, kebab-case filenames)
    - _Requirements: 1.5, 9.3, 9.4, 9.5, 9.6, 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using `proptest` crate
- Static analysis tests verify code quality constraints (no inline literals, file size limits)
- All `.slint` component files must source values from DesignTokens — no raw hex colors or numeric literals
- The application uses `no-frame: true` for the custom title bar with `resize-border-width: 8px` for resize affordance
- Page stack uses conditional visibility pattern (no dynamic loader) for instant page switching

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1"] },
    { "id": 3, "tasks": ["3.1", "3.2", "3.4"] },
    { "id": 4, "tasks": ["3.3", "3.5"] },
    { "id": 5, "tasks": ["5.1"] },
    { "id": 6, "tasks": ["5.2", "8.1", "8.2"] },
    { "id": 7, "tasks": ["6.1", "8.3"] },
    { "id": 8, "tasks": ["6.2", "8.4"] },
    { "id": 9, "tasks": ["10.1", "10.2", "10.3", "10.4", "10.5", "10.6", "10.7", "10.8"] },
    { "id": 10, "tasks": ["11.1"] }
  ]
}
```
