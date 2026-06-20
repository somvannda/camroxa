"""Tests for design system bootstrap and runtime theme switching.

Validates:
- TokenRegistry singleton creation
- Global QSS application at startup
- Runtime theme switching regenerates and reapplies QSS
- Unmigrated views receive base theme styling from global QSS
- Design system widgets render correctly inside existing views
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from python_app.design_system.bootstrap import (
    get_registry,
    apply_theme,
    switch_theme,
    reset_registry,
)
from python_app.design_system.tokens import (
    TokenRegistry,
    ThemeTokens,
    ColorTokens,
    TypographyTokens,
    SpacingTokens,
    ShapeTokens,
    DEFAULT_DARK_THEME,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset the global registry before and after each test."""
    reset_registry()
    yield
    reset_registry()


class TestGetRegistry:
    """Tests for the get_registry() singleton function."""

    def test_returns_token_registry_instance(self):
        registry = get_registry()
        assert isinstance(registry, TokenRegistry)

    def test_returns_same_instance_on_multiple_calls(self):
        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2

    def test_default_variant_is_dark(self):
        registry = get_registry()
        tokens = registry.get_active()
        assert tokens.colors.accent == "#00d4ff"

    def test_reset_creates_new_instance(self):
        reg1 = get_registry()
        reset_registry()
        reg2 = get_registry()
        assert reg1 is not reg2


class TestApplyTheme:
    """Tests for apply_theme() global QSS application."""

    def test_applies_qss_to_provided_app(self):
        mock_app = MagicMock()
        apply_theme(app=mock_app)
        mock_app.setStyleSheet.assert_called_once()
        qss = mock_app.setStyleSheet.call_args[0][0]
        assert len(qss) > 0
        # QSS should contain base widget styling
        assert "QWidget" in qss
        assert "QPushButton" in qss

    def test_qss_contains_active_theme_colors(self):
        mock_app = MagicMock()
        apply_theme(app=mock_app)
        qss = mock_app.setStyleSheet.call_args[0][0]
        # Default dark theme accent color should be present
        assert "#00d4ff" in qss

    def test_uses_qapplication_instance_when_app_is_none(self):
        mock_app = MagicMock()
        with patch(
            "python_app.design_system.bootstrap.QApplication.instance",
            return_value=mock_app,
        ):
            apply_theme(app=None)
            mock_app.setStyleSheet.assert_called_once()

    def test_no_error_when_no_app_available(self):
        with patch(
            "python_app.design_system.bootstrap.QApplication.instance",
            return_value=None,
        ):
            # Should not raise when QApplication.instance() returns None
            apply_theme(app=None)

    def test_qss_covers_all_14_base_widget_types(self):
        mock_app = MagicMock()
        apply_theme(app=mock_app)
        qss = mock_app.setStyleSheet.call_args[0][0]
        required_widgets = [
            "QPushButton",
            "QLabel",
            "QLineEdit",
            "QComboBox",
            "QSlider",
            "QProgressBar",
            "QCheckBox",
            "QTabWidget",
            "QTableWidget",
            "QListWidget",
            "QScrollBar",
            "QSpinBox",
            "QTextEdit",
            "QMenu",
        ]
        for widget in required_widgets:
            assert widget in qss, f"Missing widget type in QSS: {widget}"


class TestSwitchTheme:
    """Tests for switch_theme() runtime variant switching."""

    def test_switch_updates_active_variant(self):
        # Register a second variant
        registry = get_registry()
        alt_colors = ColorTokens(
            surface_base="#ffffff",
            surface_raised="#f5f5f5",
            surface_overlay="#eeeeee",
            surface_sunken="#e0e0e0",
            surface_elevated="#d6d6d6",
            text_primary="#111111",
            text_secondary="#333333",
            text_muted="#666666",
            accent="#1976d2",
            accent_hover="#1e88e5",
            accent_pressed="#1565c0",
            accent_glow="#1976d266",
            secondary_accent="#7c3aed",
            secondary_accent_hover="#a855f7",
            success="#2e7d32",
            success_hover="#388e3c",
            warning="#f57c00",
            warning_hover="#fb8c00",
            danger="#c62828",
            danger_hover="#d32f2f",
            status_active="#10b981",
            status_inactive="#6b7280",
            status_premium="#a855f7",
            status_warning="#f59e0b",
            nav_active_gradient_start="#7c3aed",
            nav_active_gradient_end="#a855f7",
            brand_gradient_start="#4c1d95",
            brand_gradient_mid="#6d28d9",
            brand_gradient_end="#a855f7",
            title_bar_bg="#ffffff",
            border="#bdbdbd",
            border_strong="#9e9e9e",
            separator="#e0e0e0",
            border_glass="#0000001a",
            selection="#bbdefb",
            focus_ring="#1976d2",
        )
        light_theme = ThemeTokens(
            colors=alt_colors,
            typography=DEFAULT_DARK_THEME.typography,
            spacing=DEFAULT_DARK_THEME.spacing,
            shape=DEFAULT_DARK_THEME.shape,
        )
        registry.register_variant("light", light_theme)

        mock_app = MagicMock()
        switch_theme("light", app=mock_app)

        # Verify QSS was reapplied with the new theme colors
        qss = mock_app.setStyleSheet.call_args[0][0]
        assert "#1976d2" in qss  # Light theme accent color
        assert "#ffffff" in qss  # Light theme surface_base

    def test_switch_raises_for_unknown_variant(self):
        mock_app = MagicMock()
        with pytest.raises(KeyError, match="Unknown variant"):
            switch_theme("nonexistent", app=mock_app)

    def test_switch_reapplies_qss_to_app(self):
        mock_app = MagicMock()
        switch_theme("dark", app=mock_app)
        mock_app.setStyleSheet.assert_called_once()

    def test_multiple_switches_update_qss(self):
        """Each switch call regenerates and reapplies QSS."""
        registry = get_registry()
        alt_colors = ColorTokens(
            surface_base="#222222",
            surface_raised="#333333",
            surface_overlay="#444444",
            surface_sunken="#111111",
            surface_elevated="#555555",
            text_primary="#ffffff",
            text_secondary="#cccccc",
            text_muted="#888888",
            accent="#ff5722",
            accent_hover="#ff7043",
            accent_pressed="#e64a19",
            accent_glow="#ff572266",
            secondary_accent="#7c3aed",
            secondary_accent_hover="#a855f7",
            success="#4caf50",
            success_hover="#66bb6a",
            warning="#ff9800",
            warning_hover="#ffa726",
            danger="#f44336",
            danger_hover="#ef5350",
            status_active="#10b981",
            status_inactive="#6b7280",
            status_premium="#a855f7",
            status_warning="#f59e0b",
            nav_active_gradient_start="#7c3aed",
            nav_active_gradient_end="#a855f7",
            brand_gradient_start="#4c1d95",
            brand_gradient_mid="#6d28d9",
            brand_gradient_end="#a855f7",
            title_bar_bg="#222222",
            border="#555555",
            border_strong="#666666",
            separator="#444444",
            border_glass="#ffffff1a",
            selection="#ff572244",
            focus_ring="#ff5722",
        )
        orange_theme = ThemeTokens(
            colors=alt_colors,
            typography=DEFAULT_DARK_THEME.typography,
            spacing=DEFAULT_DARK_THEME.spacing,
            shape=DEFAULT_DARK_THEME.shape,
        )
        registry.register_variant("orange", orange_theme)

        mock_app = MagicMock()

        # Switch to dark
        switch_theme("dark", app=mock_app)
        qss_dark = mock_app.setStyleSheet.call_args[0][0]
        assert "#00d4ff" in qss_dark

        # Switch to orange
        switch_theme("orange", app=mock_app)
        qss_orange = mock_app.setStyleSheet.call_args[0][0]
        assert "#ff5722" in qss_orange
        assert qss_dark != qss_orange


class TestUnmigratedViewsStyling:
    """Tests ensuring unmigrated views receive base theme styling from global QSS."""

    def test_global_qss_styles_base_widgets(self):
        """The global QSS contains base widget rules that apply without explicit migration."""
        mock_app = MagicMock()
        apply_theme(app=mock_app)
        qss = mock_app.setStyleSheet.call_args[0][0]

        # Base QWidget rule provides font and color to all widgets
        assert "QWidget" in qss
        assert "color:" in qss
        assert "font-family:" in qss
        assert "font-size:" in qss

    def test_global_qss_includes_property_selectors(self):
        """Design system widgets inside existing views work via property selectors."""
        mock_app = MagicMock()
        apply_theme(app=mock_app)
        qss = mock_app.setStyleSheet.call_args[0][0]

        # Property selectors for design system widgets
        assert 'uiRole="primary"' in qss
        assert 'uiRole="secondary"' in qss
        assert 'uiRole="danger"' in qss
        assert 'uiField="card"' in qss
        assert 'uiField="standalone"' in qss
