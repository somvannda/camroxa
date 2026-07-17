"""Tests for user control-panel router dependency wiring."""

from __future__ import annotations

import typing

from platform_api.routers import control_panel


def test_security_overview_auth_hint_resolves() -> None:
    """Annotated must be imported so FastAPI treats ctx as Depends(), not query input."""
    hints = typing.get_type_hints(control_panel.get_security_overview)
    assert hints["ctx"].__name__ == "AuthContext"
    assert hasattr(control_panel, "Annotated")
