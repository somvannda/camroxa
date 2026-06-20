# Page Design — Profile Management (Desktop-first)

## Global Styles (applies to all pages)
- Layout system: Tailwind utility classes; primary layout with CSS Grid for main columns and Flexbox for toolbars.
- Spacing scale: 4/8/12/16/24 px rhythm (Tailwind `gap-1/2/3/4/6`).
- Typography: `text-sm` default, `text-base` for primary inputs, `text-lg` section headings.
- Colors (theme-consistent with existing app):
  - Background: neutral dark or light (follow current theme)
  - Surface cards/dialogs: elevated panel with subtle border
  - Accent: primary button color already used by your `Button` component
- Buttons:
  - Primary: used for Generate / Create Profile / Set Active
  - Secondary: used for Manage Profiles / Cancel
  - Disabled: visibly disabled + tooltip/inline message when Generate is blocked

---

## Page: Generator (Home)

### Layout
- Primary layout: existing dashboard shell.
- Place the profile selector in the top toolbar row (preferred) so it is always visible.
- Use a left-to-right toolbar layout:
  - Left: app title / current workflow
  - Center: profile selector + manage button
  - Right: generate actions

### Meta Information
- Title: "MusicGenerator — Generate"
- Description: "Generate content and save outputs under a selected profile."

### Page Structure
1. **Top Toolbar (sticky)**
2. **Main workspace (existing generate/edit panels)**
3. **Footer (existing)**

### Sections & Components
#### 1) Active Profile Block (Top Toolbar)
- Components:
  - `Select` dropdown labeled "Profile" (required)
  - Inline status pill showing "Active" when selected
  - "Manage" button opens Profile Management dialog
- States:
  - Empty state: dropdown shows "Select a profile…" and an inline helper text: "Select or create a profile to enable Generate."

#### 2) Output Prefix (Optional)
- Placement: near the Generate controls (same visual group as Suno options).
- Component: `Input` labeled "Run prefix (optional)".
- Helper text: "Prefix is added to the run folder name (e.g. chorus_0007)."

#### 3) Output Path Preview
- Placement: directly under prefix input.
- Component: read-only mono text line (small):
  - "Next output folder: D:\...\suno\{profile}\{prefix_}0007\"
- Behavior:
  - Updates when profile changes or prefix changes.
  - If no profile selected: show "Next output folder: (select a profile)".

#### 4) Generate Gating UX
- Behavior:
  - Generate button disabled when no profile selected.
  - Clicking Generate while disabled should not open errors; instead guide the user to select/create a profile.
- Error handling:
  - If IPC returns "no active profile" (defensive check), show a concise dialog: "Select a profile before generating."

---

## Page: Profile Management (Dialog)

### Layout
- Dialog layout (desktop-first): 2-column grid.
  - Left column: profile list
  - Right column: profile details + actions

### Meta Information
- Title (dialog header): "Manage Profiles"
- Description (subheader): "Profiles group your Suno outputs into separate folders."

### Page Structure
1. **Dialog Header**: title + close button
2. **Body Grid**: list (left) + details (right)
3. **Dialog Footer**: primary/secondary actions as needed

### Sections & Components
#### 1) Profile List (Left)
- List rows show:
  - Profile name
  - Folder name (secondary text)
  - Active badge if it matches active profile
- Actions:
  - "New Profile" button above list

#### 2) Profile Details (Right)
- Fields:
  - Name (editable)
  - Folder name (read-only or editable with strong warning; recommended read-only after creation)
  - "Set Active" primary button
- Delete:
  - "Delete" secondary/destructive button
  - Confirmation dialog: "This removes the profile from the app but does not delete files on disk."

#### 3) Create Profile Flow
- Minimal form in a sub-dialog or inline panel:
  - Name (required)
  - Folder name preview auto-generated from name (sanitized)
  - Create button (sets active after creation)

### Responsive behavior
- Desktop (default): 2-column layout with comfortable spacing.
- Narrow widths: stack list above details; keep primary actions pinned at bottom of dialog.
