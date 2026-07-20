"""Tests for Win32 taskbar helpers used during GPU export."""

from __future__ import annotations

from shared.lib.win32_window import exclude_hwnd_from_taskbar, glfw_window_hwnd


def test_exclude_hwnd_from_taskbar_noop_for_zero() -> None:
    exclude_hwnd_from_taskbar(0)


def test_glfw_window_hwnd_none_is_zero() -> None:
    assert glfw_window_hwnd(None) == 0
