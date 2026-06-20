"""Design system token definitions and registry.

Provides frozen dataclasses for color, typography, spacing, and shape tokens,
plus a TokenRegistry that manages theme variants with validation and dot-path access.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, asdict
from typing import Any

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")


@dataclass(frozen=True)
class ColorTokens:
    """Color palette tokens for a theme variant."""

    # Surfaces (5 levels)
    surface_base: str
    surface_raised: str
    surface_overlay: str
    surface_sunken: str
    surface_elevated: str  # Cards/elevated elements (#1e2548 range)

    # Text hierarchy (3 levels)
    text_primary: str
    text_secondary: str
    text_muted: str

    # Accent / semantic
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_glow: str  # Accent at ~40% opacity for glow/shadow effects

    # Secondary accent (purple)
    secondary_accent: str  # #7c3aed
    secondary_accent_hover: str  # #a855f7

    success: str
    success_hover: str
    warning: str
    warning_hover: str
    danger: str
    danger_hover: str

    # Status colors (distinct from semantic action colors)
    status_active: str  # Green (#10b981)
    status_inactive: str  # Gray (#6b7280)
    status_premium: str  # Purple (#a855f7)
    status_warning: str  # Orange (#f59e0b)

    # Navigation active state gradient
    nav_active_gradient_start: str  # #7c3aed
    nav_active_gradient_end: str  # #a855f7

    # Brand gradient (login + marketing)
    brand_gradient_start: str  # #4c1d95
    brand_gradient_mid: str  # #6d28d9
    brand_gradient_end: str  # #a855f7

    # Title bar
    title_bar_bg: str  # matches surface_base (#0a0e27)

    # Borders / separators
    border: str
    border_strong: str
    separator: str
    border_glass: str  # Semi-transparent for glass-morphism (#ffffff1a)

    # Interactive
    selection: str
    focus_ring: str


@dataclass(frozen=True)
class TypographyTokens:
    """Typography tokens for font sizing and weight."""

    font_family: str
    size_title: int
    size_subtitle: int
    size_body: int
    size_caption: int
    weight_regular: int
    weight_medium: int
    weight_bold: int


@dataclass(frozen=True)
class SpacingTokens:
    """Spacing tokens for padding, gaps, and margins."""

    # Component padding
    padding_sm: int
    padding_md: int
    padding_lg: int
    # Layout gaps
    gap_sm: int
    gap_md: int
    gap_lg: int
    # Margins
    margin_sm: int
    margin_md: int
    margin_lg: int


@dataclass(frozen=True)
class ShapeTokens:
    """Shape tokens for border-radius and border widths."""

    radius_sm: int
    radius_md: int
    radius_lg: int
    border_width_thin: int
    border_width_medium: int


@dataclass(frozen=True)
class ThemeTokens:
    """Complete token set for a theme variant."""

    colors: ColorTokens
    typography: TypographyTokens
    spacing: SpacingTokens
    shape: ShapeTokens


# ---------------------------------------------------------------------------
# Default dark theme
# ---------------------------------------------------------------------------

_DEFAULT_DARK_COLORS = ColorTokens(
    surface_base="#080e22",
    surface_raised="#0c1530",
    surface_overlay="#101a38",
    surface_sunken="#060b1a",
    surface_elevated="#14203e",
    text_primary="#eef4ff",
    text_secondary="#d9e5fb",
    text_muted="#7b8fb5",
    accent="#1ABCFE",
    accent_hover="#4cc8ff",
    accent_pressed="#0e9fd4",
    accent_glow="#1abCFE66",
    secondary_accent="#7466F1",
    secondary_accent_hover="#A259FF",
    success="#0ACF83",
    success_hover="#34d89a",
    warning="#F24E1E",
    warning_hover="#ff6a3d",
    danger="#FF7262",
    danger_hover="#ff8f82",
    status_active="#0ACF83",
    status_inactive="#6b7280",
    status_premium="#A259FF",
    status_warning="#F24E1E",
    nav_active_gradient_start="#7466F1",
    nav_active_gradient_end="#A259FF",
    brand_gradient_start="#4c1d95",
    brand_gradient_mid="#7c3aed",
    brand_gradient_end="#a855f7",
    title_bar_bg="#080e22",
    border="#152040",
    border_strong="#1c2a50",
    separator="#152040",
    border_glass="#ffffff1a",
    selection="#19479c",
    focus_ring="#1ABCFE",
)

_DEFAULT_DARK_TYPOGRAPHY = TypographyTokens(
    font_family="Open Sans",
    size_title=18,
    size_subtitle=14,
    size_body=14,
    size_caption=11,
    weight_regular=400,
    weight_medium=500,
    weight_bold=700,
)

_DEFAULT_DARK_SPACING = SpacingTokens(
    padding_sm=4,
    padding_md=8,
    padding_lg=16,
    gap_sm=4,
    gap_md=8,
    gap_lg=16,
    margin_sm=4,
    margin_md=12,
    margin_lg=24,
)

_DEFAULT_DARK_SHAPE = ShapeTokens(
    radius_sm=4,
    radius_md=8,
    radius_lg=12,
    border_width_thin=1,
    border_width_medium=2,
)

DEFAULT_DARK_THEME = ThemeTokens(
    colors=_DEFAULT_DARK_COLORS,
    typography=_DEFAULT_DARK_TYPOGRAPHY,
    spacing=_DEFAULT_DARK_SPACING,
    shape=_DEFAULT_DARK_SHAPE,
)


# ---------------------------------------------------------------------------
# Token Registry
# ---------------------------------------------------------------------------

class TokenRegistry:
    """Registry holding theme variants with validation and dot-path access."""

    def __init__(self) -> None:
        self._variants: dict[str, ThemeTokens] = {}
        self._active_variant: str = ""
        # Register the default dark variant
        self.register_variant("dark", DEFAULT_DARK_THEME)
        self.set_active("dark")

    def register_variant(self, name: str, tokens: ThemeTokens) -> None:
        """Register a theme variant after validating completeness and constraints.

        Raises ValueError listing all invalid tokens if any validation fails.
        """
        errors = self.validate_variant(tokens)
        if errors:
            raise ValueError(
                f"Theme variant '{name}' has invalid tokens:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )
        self._variants[name] = tokens

    def set_active(self, variant: str) -> None:
        """Set the active theme variant.

        Raises KeyError if the variant name is not registered.
        """
        if variant not in self._variants:
            available = ", ".join(sorted(self._variants.keys()))
            raise KeyError(
                f"Unknown variant '{variant}'. Available variants: {available}"
            )
        self._active_variant = variant

    def get_active(self) -> ThemeTokens:
        """Return the currently active ThemeTokens instance."""
        return self._variants[self._active_variant]

    def get_token(self, path: str) -> str | int:
        """Access a token value by dot-path (e.g. 'colors.accent').

        Raises KeyError if the path is invalid.
        """
        tokens = self.get_active()
        parts = path.split(".")

        if len(parts) != 2:
            raise KeyError(
                f"Invalid token path '{path}'. Expected format: 'category.field' "
                f"(e.g. 'colors.accent', 'typography.size_body')"
            )

        category, field = parts
        category_map = {
            "colors": tokens.colors,
            "typography": tokens.typography,
            "spacing": tokens.spacing,
            "shape": tokens.shape,
        }

        if category not in category_map:
            raise KeyError(
                f"Invalid token category '{category}'. "
                f"Available categories: {', '.join(sorted(category_map.keys()))}"
            )

        obj = category_map[category]
        field_names = {f.name for f in fields(obj)}

        if field not in field_names:
            raise KeyError(
                f"Invalid token field '{field}' in category '{category}'. "
                f"Available fields: {', '.join(sorted(field_names))}"
            )

        return getattr(obj, field)

    def as_dict(self) -> dict[str, str | int]:
        """Return a flat dictionary for backward compatibility with build_ui_tokens().

        Maps the structured token hierarchy to the flat key format used by the
        existing theme system.
        """
        tokens = self.get_active()
        c = tokens.colors
        t = tokens.typography
        s = tokens.spacing
        sh = tokens.shape

        return {
            # Surfaces
            "app_bg": c.surface_base,
            "sidebar_bg": c.surface_raised,
            "center_bg": c.surface_sunken,
            "section_bg": c.surface_raised,
            "section_soft_bg": c.surface_overlay,
            "panel_bg2": c.surface_overlay,
            "input_bg": c.surface_overlay,
            "dropdown_bg": c.surface_overlay,
            "slider_bg": c.border_strong,
            # Borders / lines
            "line": c.border,
            "line_soft": c.border_strong,
            # Text
            "text": c.text_primary,
            "text_soft": c.text_secondary,
            "text_muted": c.text_muted,
            "title": c.text_primary,
            # Accent / primary
            "primary": c.accent,
            "primary_hover": c.accent_hover,
            "primary_pressed": c.accent_pressed,
            "primary_strong": c.accent,
            "primary_strong_border": c.accent_hover,
            # Semantic colors
            "danger": c.danger,
            "danger_hover": c.danger_hover,
            "danger_border": c.danger_hover,
            "warning": c.warning,
            "warning_hover": c.warning_hover,
            "warning_border": c.warning_hover,
            "success": c.success,
            "success_hover": c.success_hover,
            "success_border": c.success_hover,
            # Secondary
            "secondary_bg": c.surface_overlay,
            "secondary_hover": c.surface_raised,
            "secondary_pressed": c.surface_sunken,
            "secondary_border": c.border_strong,
            # Scrollbar
            "scroll_bg": c.surface_sunken,
            "scroll_handle": c.border_strong,
            # Checkbox
            "checkbox_bg": c.surface_overlay,
            "checkbox_border": c.border_strong,
            # Selection
            "selection": c.selection,
            # Navigation active state gradient
            "nav_active_start": c.nav_active_gradient_start,
            "nav_active_end": c.nav_active_gradient_end,
            # Brand gradient
            "brand_gradient_start": c.brand_gradient_start,
            "brand_gradient_mid": c.brand_gradient_mid,
            "brand_gradient_end": c.brand_gradient_end,
            # Title bar
            "title_bar_bg": c.title_bar_bg,
        }

    def validate_variant(self, tokens: ThemeTokens) -> list[str]:
        """Validate that a ThemeTokens instance has all required fields populated
        and that values satisfy format/range constraints.

        Returns a list of missing/invalid field paths. Empty list means valid.
        Collects ALL errors (not fail-fast).
        """
        errors: list[str] = []

        # Check that tokens has all four category attributes
        categories = {
            "colors": ColorTokens,
            "typography": TypographyTokens,
            "spacing": SpacingTokens,
            "shape": ShapeTokens,
        }

        for cat_name, expected_cls in categories.items():
            cat_obj = getattr(tokens, cat_name, None)
            if cat_obj is None:
                # All fields in this category are missing
                for f in fields(expected_cls):
                    errors.append(f"{cat_name}.{f.name}")
                continue

            # Check each field exists and is not None
            for f in fields(expected_cls):
                value = getattr(cat_obj, f.name, None)
                if value is None:
                    errors.append(f"{cat_name}.{f.name}")

        # --- Value constraint validation ---

        # Color format validation: all color fields must match #RRGGBB or #RRGGBBAA
        if tokens.colors is not None:
            for f in fields(tokens.colors):
                val = getattr(tokens.colors, f.name)
                if val is not None and not _HEX_COLOR_RE.match(val):
                    errors.append(
                        f"colors.{f.name}: '{val}' is not a valid hex color"
                    )

        # Typography range validation: size_ fields must be in 8-72
        if tokens.typography is not None:
            for f in fields(tokens.typography):
                if f.name == "font_family":
                    continue
                val = getattr(tokens.typography, f.name)
                if val is not None and f.name.startswith("size_") and not (8 <= val <= 72):
                    errors.append(
                        f"typography.{f.name}: {val} not in range 8-72"
                    )

        # Spacing range validation: all spacing fields must be in 0-64
        if tokens.spacing is not None:
            for f in fields(tokens.spacing):
                val = getattr(tokens.spacing, f.name)
                if val is not None and not (0 <= val <= 64):
                    errors.append(
                        f"spacing.{f.name}: {val} not in range 0-64"
                    )

        # Shape range validation: radius_ fields must be in 0-32
        if tokens.shape is not None:
            for f in fields(tokens.shape):
                val = getattr(tokens.shape, f.name)
                if val is not None and f.name.startswith("radius_") and not (0 <= val <= 32):
                    errors.append(
                        f"shape.{f.name}: {val} not in range 0-32"
                    )

        return errors
