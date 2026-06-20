"""MusicGenerator Design System.

A comprehensive, modular UI design system providing centralized theme tokens,
QSS stylesheet generation, reusable widget and layout components, theme variant
support, and backward compatibility utilities.

Usage::

    from python_app.design_system import (
        TokenRegistry, QSSGenerator, apply_theme, switch_theme,
        PrimaryButton, Card, TypedLabel,
    )
"""

from python_app.design_system.tokens import (
    TokenRegistry,
    ThemeTokens,
    ColorTokens,
    TypographyTokens,
    SpacingTokens,
    ShapeTokens,
    DEFAULT_DARK_THEME,
)
from python_app.design_system.qss_generator import QSSGenerator
from python_app.design_system.bootstrap import (
    get_registry,
    apply_theme,
    switch_theme,
)
from python_app.design_system._compat import check_inline_stylesheet_conflict
from python_app.design_system.widgets import (
    DesignButton,
    PrimaryButton,
    SecondaryButton,
    DangerButton,
    SuccessButton,
    IconButton,
    ToggleButton,
    GhostButton,
    OutlinedButton,
    ToggleSwitch,
    CustomSlider,
    StyledLineEdit,
    StyledComboBox,
    StyledSpinBox,
    TypedLabel,
    TransportButton,
    SeekBar,
    NowPlayingCard,
    Icon,
    StatusBadge,
    GradientButton,
    TableActionButton,
    IndeterminateProgress,
)
from python_app.design_system.layouts import (
    Card,
    GlassCard,
    Panel,
    PromoCard,
    QuickActionCard,
    QuickActionGrid,
    SectionDivider,
    SidebarNav,
    StatCard,
    StatCardGroup,
)

__all__ = [
    # Token system
    "TokenRegistry",
    "ThemeTokens",
    "ColorTokens",
    "TypographyTokens",
    "SpacingTokens",
    "ShapeTokens",
    "DEFAULT_DARK_THEME",
    # QSS generation
    "QSSGenerator",
    # Bootstrap / theme switching
    "get_registry",
    "apply_theme",
    "switch_theme",
    # Backward compatibility
    "check_inline_stylesheet_conflict",
    # Widget components
    "DesignButton",
    "PrimaryButton",
    "SecondaryButton",
    "DangerButton",
    "SuccessButton",
    "IconButton",
    "ToggleButton",
    "GhostButton",
    "OutlinedButton",
    "ToggleSwitch",
    "CustomSlider",
    "StyledLineEdit",
    "StyledComboBox",
    "StyledSpinBox",
    "TypedLabel",
    "TransportButton",
    "SeekBar",
    "NowPlayingCard",
    "Icon",
    "StatusBadge",
    "GradientButton",
    "TableActionButton",
    "IndeterminateProgress",
    # Layout components
    "Card",
    "GlassCard",
    "Panel",
    "PromoCard",
    "QuickActionCard",
    "QuickActionGrid",
    "SectionDivider",
    "SidebarNav",
    "StatCard",
    "StatCardGroup",
]
