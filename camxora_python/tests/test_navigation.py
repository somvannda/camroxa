"""Tests for shell navigation constants."""

from shared.constants.navigation import (
    SHELL_ROUTES,
    diagnostics_ui_enabled,
    get_route_by_key,
    get_utility_routes,
    get_workspace_routes,
)


def test_shell_route_count() -> None:
    assert len(SHELL_ROUTES) == 12


def test_workspace_routes_exclude_system() -> None:
    keys = {route.key for route in get_workspace_routes()}
    assert "settings" not in keys
    assert "log" not in keys
    assert "merger" not in keys
    assert "music" in keys
    assert "video" in keys
    assert "studio" in keys


def test_utility_routes_hide_log_by_default(monkeypatch) -> None:
    monkeypatch.delenv("CAMXORA_SHOW_DIAGNOSTICS", raising=False)
    keys = {route.key for route in get_utility_routes()}
    assert keys == {"settings"}
    assert diagnostics_ui_enabled() is False


def test_utility_routes_include_log_when_diagnostics_enabled(monkeypatch) -> None:
    monkeypatch.setenv("CAMXORA_SHOW_DIAGNOSTICS", "1")
    keys = {route.key for route in get_utility_routes()}
    assert keys == {"settings", "log"}
    assert diagnostics_ui_enabled() is True


def test_get_route_by_key() -> None:
    route = get_route_by_key("music")
    assert route.label == "Music"
    assert route.path == "/app/music"


def test_studio_route_meta() -> None:
    route = get_route_by_key("studio")
    assert route.label == "Studio"
    assert route.path == "/app/studio"
