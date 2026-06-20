# Page Design Spec — Folder-based Image Samples Gallery (Desktop-first)

## Global Styles
- Layout system: Flexbox for toolbars + CSS Grid for thumbnail gallery.
- Spacing: 8px base unit; section gaps 12–16px.
- Typography: existing app scale; keep tab labels and toolbars compact.
- Colors: reuse existing slate/dark theme tokens already used by Manage dialog.
- Buttons: use existing variants (`primary`, `secondary`, `destructive`); hover = slightly lighter background + subtle border.

## Page: Manage (Dialog) — Image Samples (Tab)

### Meta Information
- Title: "Manage — Image Samples"
- Description: "Select a folder and browse image thumbnails."
- Open Graph: not applicable (desktop app), no change required.

### Page Structure
- Overall: stacked vertical layout.
  1) Folder toolbar
  2) Gallery area (scrollable)
  3) Action bar (Refresh / Save + status)

### Sections & Components

#### 1) Folder toolbar (top)
- Layout: horizontal flex row, align center, wrap disabled.
- Elements:
  - Label: “Folder” (small muted text)
  - Read-only text field showing current folder path (ellipsized with full path on hover tooltip)
  - Button: **Select Folder** (opens OS directory picker)
- States:
  - No folder selected: show placeholder “No folder selected”.
  - Invalid/missing folder: show inline error text under toolbar.

#### 2) Gallery area (middle)
- Layout: CSS Grid with fixed-size thumbnail cards.
  - Suggested: `grid-template-columns: repeat(auto-fill, minmax(140px, 1fr))`
  - Gap: 12px
  - Container: scrollable with max height based on dialog content.
- Thumbnail card:
  - Image: cover-fit, rounded corners.
  - Footer text: filename (single line, ellipsized).
  - Click: opens right-side (or modal) preview.
- Empty state:
  - Centered text: “No images found in this folder.”
  - Secondary hint: “Supported formats: PNG/JPG/WEBP.”

#### 3) Preview (inline modal or right-side panel)
- Default approach (simpler): modal preview using existing `Dialog` component.
- Elements:
  - Large image preview (contain-fit)
  - File name + full path (copyable optional; if not implemented, show as text only)
  - Close button

#### 4) Action bar (bottom)
- Layout: horizontal flex; left-aligned status, right-aligned buttons.
- Elements:
  - Button: **Refresh** (re-scan current folder)
  - Button: **Save** (persist folder path to settings.json)
  - Status text: “Saved”, “Saving…”, or error message.
- Button states:
  - Save disabled when folder path is empty or invalid.
  - Refresh disabled when no folder is selected.

### Responsive behavior
- Desktop-first: dialog content is fixed-size in this app; still handle narrow widths by reducing grid column count automatically.
- Thumbnail grid should remain usable at minimum width by collapsing to 1–2 columns.

### Motion / transitions
- Subtle: 150ms hover transition for thumbnail card border and background.
- Dialog preview uses existing dialog open/close behavior (no new animations required).