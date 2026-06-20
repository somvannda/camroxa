"""Design system bootstrap and runtime theme switching.

Provides module-level functions to initialize the design system, apply global
QSS to QApplication at startup, and switch themes at runtime. The global QSS
ensures unmigrated views receive base theme styling automatically, and design
system widgets render correctly inside existing views without full migration.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from python_app.design_system.tokens import TokenRegistry
from python_app.design_system.qss_generator import QSSGenerator


# Module-level singleton registry
_registry: TokenRegistry | None = None


def get_registry() -> TokenRegistry:
    """Get or create the global TokenRegistry singleton.

    Returns the shared TokenRegistry instance used across the application.
    On first call, creates the registry with the default "dark" variant active.
    """
    global _registry
    if _registry is None:
        _registry = TokenRegistry()
    return _registry


def apply_theme(app: QApplication | None = None) -> None:
    """Generate QSS from the active theme variant and apply to QApplication.

    This function regenerates the full application-wide QSS string from the
    currently active theme variant in the registry, then applies it via
    QApplication.setStyleSheet(). This ensures all widgets (including unmigrated
    views) receive base theme styling.

    Args:
        app: Optional QApplication instance. If None, uses QApplication.instance().
    """
    from pathlib import Path

    registry = get_registry()

    # Resolve arrow icon URLs for combo/spin box dropdowns
    arrow_urls: dict[str, str] = {}
    try:
        from python_app.app.resources import assets_dir
        a = assets_dir()
        arrow_urls["combo"] = (a / "combo-arrow.svg").as_posix()
        arrow_urls["spin_up"] = (a / "spin-up-arrow.svg").as_posix()
        arrow_urls["spin_down"] = (a / "spin-down-arrow.svg").as_posix()
    except Exception:
        pass

    generator = QSSGenerator(registry.get_active(), arrow_urls=arrow_urls)
    qss = generator.generate()
    if app is None:
        app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(qss)


def switch_theme(variant: str, app: QApplication | None = None) -> None:
    """Switch the active theme variant and reapply QSS globally.

    Changes the active variant in the TokenRegistry, regenerates the full QSS
    string, and reapplies it to QApplication. All widgets styled via the global
    QSS will immediately reflect the new theme.

    Args:
        variant: The name of the registered theme variant to activate.
        app: Optional QApplication instance. If None, uses QApplication.instance().

    Raises:
        KeyError: If the variant name is not registered in the TokenRegistry.
    """
    registry = get_registry()
    registry.set_active(variant)
    apply_theme(app)


def reset_registry() -> None:
    """Reset the global registry singleton (primarily for testing).

    Clears the module-level singleton so the next call to get_registry()
    creates a fresh instance.
    """
    global _registry
    _registry = None
