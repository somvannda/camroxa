# MusicGenerator Design System — Pattern Library

## Overview

The MusicGenerator Design System provides a centralized, scalable UI toolkit for the PyQt6 desktop application. It replaces ad-hoc inline styling with:

- **Design Tokens** — A single source of truth for colors, typography, spacing, and shape values
- **QSS Generator** — Automatic Qt stylesheet generation from tokens, applied globally
- **Widget Components** — Reusable, self-styling buttons, toggles, sliders, inputs, labels, and transport controls
- **Layout Components** — Structural containers (cards, panels, sidebar navigation, dividers) with consistent spacing
- **Theme Variant System** — Multi-theme support with runtime switching

The system is incrementally adoptable: global QSS styles all widgets automatically, while design system components deliver richer behavior. Existing views continue to function without modification during migration.

---

## Getting Started

### 1. Bootstrap the theme at application startup

```python
from PyQt6.QtWidgets import QApplication
from python_app.design_system.bootstrap import apply_theme

app = QApplication([])
apply_theme(app)
```

`apply_theme()` generates the full QSS from the active theme variant and applies it to `QApplication.setStyleSheet()`. All widgets — including unmigrated views — receive base theme styling automatically.

### 2. Use design system components in your views

```python
from python_app.design_system.widgets.buttons import PrimaryButton, SecondaryButton
from python_app.design_system.widgets.labels import TypedLabel
from python_app.design_system.layouts.card import Card

card = Card(title="Track Settings", padding=16)
card.addWidget(TypedLabel("Adjust playback parameters", level="body"))
card.addWidget(PrimaryButton("Apply"))
card.addWidget(SecondaryButton("Cancel"))
```

### 3. Switch themes at runtime

```python
from python_app.design_system.bootstrap import switch_theme

switch_theme("dark")  # or any registered variant name
```

---

## Design Tokens

All design values are defined as frozen Python dataclasses in `python_app/design_system/tokens.py`. Access tokens programmatically via the `TokenRegistry`:

```python
from python_app.design_system.bootstrap import get_registry

registry = get_registry()
accent = registry.get_token("colors.accent")  # "#00bcd4"
body_size = registry.get_token("typography.size_body")  # 12
```

### Colors

| Token | Hex Value | Purpose |
|-------|-----------|---------|
| `surface_base` | `#111a28` | Deepest application background |
| `surface_raised` | `#141d2c` | Sidebar, panel backgrounds |
| `surface_overlay` | `#162233` | Dropdowns, popups, overlays |
| `surface_sunken` | `#0e1623` | Input fields, inset areas |
| `text_primary` | `#eef4ff` | Main body text |
| `text_secondary` | `#d9e5fb` | Less prominent text |
| `text_muted` | `#8ea4c7` | Hints, disabled labels, captions |
| `accent` | `#00bcd4` | Primary accent / interactive highlight |
| `accent_hover` | `#26c6da` | Accent hover state |
| `accent_pressed` | `#0097a7` | Accent pressed state |
| `success` | `#198754` | Success / positive actions |
| `success_hover` | `#1ea765` | Success hover state |
| `warning` | `#b86917` | Warning / caution indicators |
| `warning_hover` | `#d1811f` | Warning hover state |
| `danger` | `#aa2e2e` | Danger / destructive actions |
| `danger_hover` | `#c23838` | Danger hover state |
| `border` | `#27354b` | Standard border color |
| `border_strong` | `#31435d` | Emphasized border color |
| `separator` | `#27354b` | Divider lines |
| `selection` | `#19479c` | Selection highlight background |
| `focus_ring` | `#00bcd4` | Focus border color |

### Typography

| Token | Value | Purpose |
|-------|-------|---------|
| `font_family` | `"Segoe UI"` | Application-wide font family |
| `size_title` | `18` | Page titles |
| `size_subtitle` | `14` | Section headings |
| `size_body` | `12` | Body text (default) |
| `size_caption` | `10` | Captions, timestamps |
| `weight_regular` | `400` | Normal text weight |
| `weight_medium` | `500` | Emphasized text weight |
| `weight_bold` | `700` | Strong emphasis / headings |

### Spacing

| Token | Value (px) | Purpose |
|-------|-----------|---------|
| `padding_sm` | `4` | Compact component padding |
| `padding_md` | `8` | Standard component padding |
| `padding_lg` | `16` | Generous component padding |
| `gap_sm` | `4` | Tight layout gaps |
| `gap_md` | `8` | Standard layout gaps |
| `gap_lg` | `16` | Spacious layout gaps |
| `margin_sm` | `4` | Tight margins |
| `margin_md` | `12` | Standard margins |
| `margin_lg` | `24` | Large section margins |

### Shape

| Token | Value (px) | Purpose |
|-------|-----------|---------|
| `radius_sm` | `4` | Subtle rounding (inputs, small buttons) |
| `radius_md` | `8` | Standard rounding (cards, panels) |
| `radius_lg` | `12` | Pronounced rounding (modals, large cards) |
| `border_width_thin` | `1` | Standard borders, separators |
| `border_width_medium` | `2` | Emphasized borders, focus rings |

---

## Widget Components

### DesignButton

**Purpose:** Base button that applies a Style_Role via the `uiRole` dynamic property. All specific button variants inherit from this class.

**Constructor:**
```python
DesignButton(text: str = "", variant: str = "primary", parent: QWidget | None = None)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | `""` | Button display text |
| `variant` | `str` | `"primary"` | Style role variant |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Valid variants:** `"primary"`, `"secondary"`, `"danger"`, `"success"`, `"toggle"`, `"transport"`, `"transportPrimary"`

**Usage:**
```python
from python_app.design_system.widgets.buttons import DesignButton

btn = DesignButton("Save Changes", variant="primary")
btn = DesignButton("Remove", variant="danger")
```

---

### PrimaryButton

**Purpose:** Button with cyan/teal accent background, white text, rounded corners, and hover/pressed states.

**Constructor:**
```python
PrimaryButton(text: str = "", parent: QWidget | None = None)
```

**Usage:**
```python
from python_app.design_system.widgets.buttons import PrimaryButton

save_btn = PrimaryButton("Save")
save_btn.clicked.connect(self.on_save)
```

---

### SecondaryButton

**Purpose:** Button with transparent/dark background, border, light text, and hover/pressed states. Used for non-primary actions.

**Constructor:**
```python
SecondaryButton(text: str = "", parent: QWidget | None = None)
```

**Usage:**
```python
from python_app.design_system.widgets.buttons import SecondaryButton

cancel_btn = SecondaryButton("Cancel")
```

---

### DangerButton

**Purpose:** Button with red background for destructive or irreversible actions.

**Constructor:**
```python
DangerButton(text: str = "", parent: QWidget | None = None)
```

**Usage:**
```python
from python_app.design_system.widgets.buttons import DangerButton

delete_btn = DangerButton("Delete Track")
```

---

### SuccessButton

**Purpose:** Button with green background for positive/confirming actions.

**Constructor:**
```python
SuccessButton(text: str = "", parent: QWidget | None = None)
```

**Usage:**
```python
from python_app.design_system.widgets.buttons import SuccessButton

confirm_btn = SuccessButton("Confirm Upload")
```

---

### IconButton

**Purpose:** Button that displays an SVG icon with optional tooltip. Uses the `"icon"` uiRole.

**Constructor:**
```python
IconButton(icon_name: str, tooltip: str = "", icon_size: int = 16, parent: QWidget | None = None)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `icon_name` | `str` | — | Path to SVG icon file or Qt resource path |
| `tooltip` | `str` | `""` | Tooltip text shown on hover |
| `icon_size` | `int` | `16` | Icon dimensions in pixels |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Usage:**
```python
from python_app.design_system.widgets.buttons import IconButton

settings_btn = IconButton("assets/icons/settings.svg", tooltip="Settings", icon_size=20)
```

---

### ToggleButton

**Purpose:** Checkable button with on/off visual states using Qt's built-in `:checked` pseudo-state.

**Constructor:**
```python
ToggleButton(text: str = "", parent: QWidget | None = None)
```

**Usage:**
```python
from python_app.design_system.widgets.buttons import ToggleButton

loop_btn = ToggleButton("Loop")
loop_btn.toggled.connect(self.on_loop_toggled)

# Check programmatically
loop_btn.setChecked(True)
```

---

### ToggleSwitch

**Purpose:** A modern toggle switch with animated knob transition, replacing native checkboxes with a polished on/off control.

**Constructor:**
```python
ToggleSwitch(label: str = "", label_position: str = "right", parent: QWidget | None = None)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | `""` | Optional text label beside the switch |
| `label_position` | `str` | `"right"` | Label position: `"left"` or `"right"` |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Signals:**
- `toggled(bool)` — Emitted when state changes

**Features:**
- 150ms animated knob slide transition
- Keyboard accessible (Space key toggles, Tab focuses)
- Custom paint: rounded track + circular knob using token colors

**Usage:**
```python
from python_app.design_system.widgets.toggle_switch import ToggleSwitch

auto_save = ToggleSwitch(label="Auto-save", label_position="right")
auto_save.toggled.connect(self.on_auto_save_changed)

# Programmatic control
auto_save.setChecked(True)
print(auto_save.isChecked())  # True
```

---

### CustomSlider

**Purpose:** Styled QSlider with configurable range, step, and orientation. Provides an accent-colored filled portion and themed handle via QSS.

**Constructor:**
```python
CustomSlider(
    orientation: Qt.Orientation = Qt.Orientation.Horizontal,
    minimum: int = 0,
    maximum: int = 100,
    step: int = 1,
    parent: QWidget | None = None,
)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `orientation` | `Qt.Orientation` | `Horizontal` | Slider orientation |
| `minimum` | `int` | `0` | Minimum value |
| `maximum` | `int` | `100` | Maximum value |
| `step` | `int` | `1` | Single step increment |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Raises:** `ValueError` if `minimum >= maximum`

**Usage:**
```python
from python_app.design_system.widgets.custom_slider import CustomSlider
from PyQt6.QtCore import Qt

volume = CustomSlider(orientation=Qt.Orientation.Horizontal, minimum=0, maximum=100, step=5)
volume.valueChanged.connect(self.on_volume_changed)
volume.setValue(75)
```

---

### StyledLineEdit

**Purpose:** Themed text input with dark background, rounded border, themed placeholder color, and focus highlight.

**Constructor:**
```python
StyledLineEdit(field_variant: str = "standalone", placeholder: str = "", parent=None)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `field_variant` | `str` | `"standalone"` | `"standalone"` (solid dark bg) or `"card"` (transparent bg) |
| `placeholder` | `str` | `""` | Placeholder text |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Usage:**
```python
from python_app.design_system.widgets.inputs import StyledLineEdit

search = StyledLineEdit(placeholder="Search tracks...", field_variant="standalone")
name_input = StyledLineEdit(placeholder="Track name", field_variant="card")
```

---

### StyledComboBox

**Purpose:** Themed combo box with dark dropdown background, styled arrow indicator, and selection highlighting.

**Constructor:**
```python
StyledComboBox(field_variant: str = "standalone", parent=None)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `field_variant` | `str` | `"standalone"` | `"standalone"` or `"card"` |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Usage:**
```python
from python_app.design_system.widgets.inputs import StyledComboBox

genre_selector = StyledComboBox(field_variant="card")
genre_selector.addItems(["Rock", "Pop", "Jazz", "Electronic"])
```

---

### StyledSpinBox

**Purpose:** Themed spin box with styled up/down arrows and consistent border treatment.

**Constructor:**
```python
StyledSpinBox(field_variant: str = "standalone", parent=None)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `field_variant` | `str` | `"standalone"` | `"standalone"` or `"card"` |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Usage:**
```python
from python_app.design_system.widgets.inputs import StyledSpinBox

bpm_input = StyledSpinBox(field_variant="standalone")
bpm_input.setRange(60, 200)
bpm_input.setValue(120)
```

---

### TypedLabel

**Purpose:** A QLabel that applies a typography level via the `uiRole` dynamic property for consistent font sizing, weight, and color.

**Constructor:**
```python
TypedLabel(text: str, level: str = "body", parent: QWidget | None = None)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | — | Display text |
| `level` | `str` | `"body"` | Typography level |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Valid levels:**

| Level | Font Size | Weight | Color | Use Case |
|-------|-----------|--------|-------|----------|
| `page_title` | 18px | Bold | Primary | Page headings |
| `section_title` | 14px | Medium | Primary | Section headings |
| `subtitle` | 14px | Regular | Secondary | Subtitles |
| `body` | 12px | Regular | Primary | Body text (default) |
| `caption` | 10px | Regular | Secondary | Timestamps, metadata |
| `muted` | 10px | Regular | Muted | Hints, disabled text |

**Usage:**
```python
from python_app.design_system.widgets.labels import TypedLabel

heading = TypedLabel("Library", level="page_title")
description = TypedLabel("Browse your music collection", level="body")
timestamp = TypedLabel("3:45", level="caption")

# Change level dynamically
heading.setLevel("section_title")
```

---

### TransportButton

**Purpose:** Circular button with an SVG icon for audio playback controls (play, pause, skip, stop).

**Constructor:**
```python
TransportButton(
    icon_name: str,
    size: str = "medium",
    variant: str = "default",
    tooltip: str = "",
    parent: QWidget | None = None,
)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `icon_name` | `str` | — | Path to SVG icon |
| `size` | `str` | `"medium"` | Size variant |
| `variant` | `str` | `"default"` | `"default"` or `"primary"` |
| `tooltip` | `str` | `""` | Tooltip text |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Size variants:**

| Variant | Pixel Size |
|---------|-----------|
| `small` | 28×28 px |
| `medium` | 36×36 px |
| `large` | 44×44 px |

**Usage:**
```python
from python_app.design_system.widgets.transport import TransportButton

play_btn = TransportButton("icons/play.svg", size="large", variant="primary", tooltip="Play")
skip_btn = TransportButton("icons/skip-forward.svg", size="medium", tooltip="Next Track")
```

---

### SeekBar

**Purpose:** Audio seek bar composing a slider with elapsed/total time labels formatted as MM:SS.

**Constructor:**
```python
SeekBar(parent: QWidget | None = None)
```

**Signals:**
- `valueChanged(int)` — Emitted when the slider position changes (value in milliseconds)

**Methods:**
| Method | Description |
|--------|-------------|
| `setRange(min, max)` | Set the slider min/max range |
| `setValue(value)` | Set current position and update elapsed label |
| `setDuration(total_ms)` | Set total duration, updates total label and slider max |

**Usage:**
```python
from python_app.design_system.widgets.transport import SeekBar

seek = SeekBar()
seek.setDuration(210000)  # 3:30 total
seek.setValue(45000)       # Elapsed: 00:45
seek.valueChanged.connect(self.on_seek)
```

---

### NowPlayingCard

**Purpose:** Composite widget displaying current track metadata (album art, title, artist, duration) with an accent-colored left border highlight.

**Constructor:**
```python
NowPlayingCard(parent: QWidget | None = None)
```

**Methods:**
| Method | Description |
|--------|-------------|
| `setTrackInfo(title, artist, duration, album_art_path)` | Update displayed track info |

**Parameters for `setTrackInfo`:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | `str` | — | Track title (section_title level) |
| `artist` | `str` | — | Artist name (caption level) |
| `duration` | `str` | `""` | Duration string e.g. "3:45" (muted level) |
| `album_art_path` | `str` | `""` | Path to album art image; shows placeholder if missing |

**Usage:**
```python
from python_app.design_system.widgets.now_playing_card import NowPlayingCard

card = NowPlayingCard()
card.setTrackInfo(
    title="Midnight Dreams",
    artist="The Synthwave Collective",
    duration="4:12",
    album_art_path="/path/to/cover.png",
)
```

---

## Layout Components

### Card

**Purpose:** A rounded-corner container with optional title, configurable padding, and subtle background differentiation from the page surface.

**Constructor:**
```python
Card(title: str = "", padding: int | None = None, parent: QWidget | None = None)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | `str` | `""` | Optional title (section_title style) |
| `padding` | `int \| None` | `None` (16px) | Padding on all sides, clamped to 0–64 |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Methods:**
| Method | Description |
|--------|-------------|
| `addWidget(widget)` | Add a child widget to the card content area |
| `setTitle(title)` | Set or update the card title |

**Composition example:**
```python
from python_app.design_system.layouts.card import Card
from python_app.design_system.widgets.buttons import PrimaryButton
from python_app.design_system.widgets.labels import TypedLabel
from python_app.design_system.widgets.inputs import StyledLineEdit

card = Card(title="Export Settings", padding=16)
card.addWidget(TypedLabel("Configure export format and quality", level="body"))
card.addWidget(StyledLineEdit(placeholder="Output filename", field_variant="card"))
card.addWidget(PrimaryButton("Export"))

# Add to your view layout
layout.addWidget(card)
```

---

### Panel

**Purpose:** A container with optional header area, content area, and configurable border/separator between them.

**Constructor:**
```python
Panel(header: str = "", show_border: bool = True, parent: QWidget | None = None)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `header` | `str` | `""` | Optional header text (section_title style) |
| `show_border` | `bool` | `True` | Whether to show a border around the panel |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Methods:**
| Method | Description |
|--------|-------------|
| `setHeaderWidget(widget)` | Replace the default header with a custom widget |
| `addContent(widget)` | Add a widget to the panel's content area |

**Composition example:**
```python
from python_app.design_system.layouts.panel import Panel
from python_app.design_system.widgets.labels import TypedLabel
from python_app.design_system.widgets.custom_slider import CustomSlider

panel = Panel(header="Volume Control", show_border=True)
panel.addContent(TypedLabel("Master Volume", level="body"))
panel.addContent(CustomSlider(minimum=0, maximum=100, step=1))

# Custom header widget
from python_app.design_system.widgets.buttons import IconButton
panel.setHeaderWidget(IconButton("icons/audio.svg", tooltip="Audio Settings"))
```

---

### SidebarNav

**Purpose:** Vertical navigation component with icon+text items, active/inactive states, and click signals.

**Constructor:**
```python
SidebarNav(items: list[dict], parent: QWidget | None = None)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `items` | `list[dict]` | — | Navigation item definitions (see format below) |
| `parent` | `QWidget \| None` | `None` | Parent widget |

**Item format:**
```python
{"key": "page_id", "icon": "path/to/icon.svg", "label": "Display Label"}
```

**Signals:**
- `navigation_requested(str)` — Emitted with the item's `key` when clicked

**Methods:**
| Method | Description |
|--------|-------------|
| `setActiveItem(page_key)` | Programmatically set the active item by key |

**Raises:** `ValueError` if any item is missing the required `"key"` field.

**Composition example:**
```python
from python_app.design_system.layouts.sidebar_nav import SidebarNav

nav = SidebarNav(items=[
    {"key": "music", "icon": "icons/music.svg", "label": "Music"},
    {"key": "playlists", "icon": "icons/playlist.svg", "label": "Playlists"},
    {"key": "generate", "icon": "icons/wand.svg", "label": "Generate"},
    {"key": "settings", "icon": "icons/settings.svg", "label": "Settings"},
])
nav.navigation_requested.connect(self.navigate_to_page)

# Programmatic selection
nav.setActiveItem("playlists")
```

---

### SectionDivider

**Purpose:** A thin horizontal separator line using the design system separator token color.

**Constructor:**
```python
SectionDivider(parent: QWidget | None = None)
```

**Usage:**
```python
from python_app.design_system.layouts.section_divider import SectionDivider

layout.addWidget(TypedLabel("Section A", level="section_title"))
layout.addWidget(SectionDivider())
layout.addWidget(TypedLabel("Section B", level="section_title"))
```

---

## Migration Guide

This guide explains how to convert an existing view from inline styling to design system components.

### Step 1: Apply global QSS via `apply_theme()`

Ensure `apply_theme(app)` is called in your application startup (e.g., `main.py` or `bootstrap.py`). This provides base theme styling to all widgets without any per-view changes.

```python
# In your app entry point
from python_app.design_system.bootstrap import apply_theme

app = QApplication(sys.argv)
apply_theme(app)
```

After this step, all standard Qt widgets (buttons, labels, inputs, etc.) receive the dark theme styling automatically.

### Step 2: Replace inline stylesheets with design system components

**Before (inline styling):**
```python
btn = QPushButton("Save")
btn.setStyleSheet("""
    QPushButton {
        background-color: #00bcd4;
        color: white;
        border-radius: 4px;
        padding: 8px 16px;
    }
    QPushButton:hover {
        background-color: #26c6da;
    }
""")
```

**After (design system component):**
```python
from python_app.design_system.widgets.buttons import PrimaryButton

btn = PrimaryButton("Save")
```

**Before (inline label styling):**
```python
title = QLabel("My Page")
title.setStyleSheet("font-size: 18px; font-weight: bold; color: #eef4ff;")
```

**After (design system component):**
```python
from python_app.design_system.widgets.labels import TypedLabel

title = TypedLabel("My Page", level="page_title")
```

**Before (inline input styling):**
```python
edit = QLineEdit()
edit.setStyleSheet("""
    QLineEdit {
        background: #162233;
        border: 1px solid #27354b;
        border-radius: 4px;
        color: #eef4ff;
        padding: 4px 8px;
    }
    QLineEdit:focus {
        border-color: #00bcd4;
    }
""")
```

**After (design system component):**
```python
from python_app.design_system.widgets.inputs import StyledLineEdit

edit = StyledLineEdit(placeholder="Enter value...")
```

### Step 3: Use `uiRole` and `uiField` properties for role-based styling

For widgets that cannot be replaced with design system components directly, apply Qt dynamic properties so the global QSS styles them:

```python
# Apply a button role
btn = QPushButton("Action")
btn.setProperty("uiRole", "primary")

# Apply an input field variant
edit = QLineEdit()
edit.setProperty("uiField", "card")
```

Available `uiRole` values: `"primary"`, `"secondary"`, `"danger"`, `"success"`, `"toggle"`, `"transport"`, `"transportPrimary"`, `"icon"`, `"page_title"`, `"section_title"`, `"subtitle"`, `"body"`, `"caption"`, `"muted"`

Available `uiField` values: `"standalone"`, `"card"`

### Step 4: Replace layout containers

**Before (manual container styling):**
```python
container = QWidget()
container.setStyleSheet("background: #141d2c; border-radius: 8px;")
layout = QVBoxLayout(container)
layout.setContentsMargins(16, 16, 16, 16)
```

**After (design system Card):**
```python
from python_app.design_system.layouts.card import Card

container = Card(title="My Section", padding=16)
container.addWidget(my_content_widget)
```

### Step 5: Remove inline stylesheets

Once a widget uses a design system component or has the appropriate `uiRole`/`uiField` property, remove any remaining `setStyleSheet()` calls. The design system will log deprecation warnings for widgets that have both an inline stylesheet and a design system role applied:

```
WARNING: Widget MyButton has both inline stylesheet and design system role 'primary'.
Consider removing the inline stylesheet for full design system control.
```

### Migration Checklist

- [ ] `apply_theme(app)` called at startup
- [ ] Replace `QPushButton` + inline CSS → `PrimaryButton`, `SecondaryButton`, etc.
- [ ] Replace `QLabel` + inline CSS → `TypedLabel` with appropriate level
- [ ] Replace `QLineEdit` / `QComboBox` / `QSpinBox` + inline CSS → `StyledLineEdit` / `StyledComboBox` / `StyledSpinBox`
- [ ] Replace manual container styling → `Card` or `Panel`
- [ ] Replace custom nav implementations → `SidebarNav`
- [ ] Remove all `setStyleSheet()` calls on migrated widgets
- [ ] Verify no deprecation warnings in application logs
