"""Tests for shell navigation constants."""

from shared.constants.navigation import (
    SHELL_ROUTES,
    get_route_by_key,
    get_utility_routes,
    get_workspace_routes,
)


def test_shell_route_count() -> None:
    assert len(SHELL_ROUTES) == 10


def test_workspace_routes_exclude_system() -> None:
    keys = {route.key for route in get_workspace_routes()}
    assert "settings" not in keys
    assert "log" not in keys
    assert "merger" not in keys
    assert "music" in keys
    assert "video" in keys


def test_utility_routes() -> None:
    keys = {route.key for route in get_utility_routes()}
    assert keys == {"settings", "log"}


def test_get_route_by_key() -> None:
    route = get_route_by_key("music")
    assert route.label == "Music"
    assert route.path == "/app/music"
