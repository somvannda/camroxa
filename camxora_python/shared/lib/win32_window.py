"""Windows HWND helpers for taskbar branding and hidden tool windows."""

from __future__ import annotations

import sys


def exclude_hwnd_from_taskbar(hwnd: int) -> None:
    """Keep a helper HWND (e.g. GLFW offscreen) out of the Windows taskbar.

    Invisible GLFW windows still default to ``WS_EX_APPWINDOW``, which can make
    Windows treat them as the process' main taskbar surface and drop our branded
    icon for the real Qt window while video export / preview GL is running.
    """
    if sys.platform != "win32" or not hwnd:
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        SWP_FRAMECHANGED = 0x0020

        get_long = getattr(user32, "GetWindowLongPtrW", None)
        set_long = getattr(user32, "SetWindowLongPtrW", None)
        if not callable(get_long) or not callable(set_long):
            get_long = user32.GetWindowLongW
            set_long = user32.SetWindowLongW

        ex_style = int(get_long(ctypes.c_void_p(hwnd), GWL_EXSTYLE) or 0)
        ex_style = (ex_style & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
        set_long(ctypes.c_void_p(hwnd), GWL_EXSTYLE, ctypes.c_void_p(ex_style))
        user32.SetWindowPos(
            ctypes.c_void_p(hwnd),
            None,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )
    except Exception:
        return


def glfw_window_hwnd(win: object) -> int:
    """Return the Win32 HWND for a GLFW window, or 0 when unavailable."""
    if sys.platform != "win32" or win is None:
        return 0
    try:
        import glfw

        getter = getattr(glfw, "get_win32_window", None)
        if callable(getter):
            return int(getter(win) or 0)
    except Exception:
        return 0
    return 0


def exclude_glfw_window_from_taskbar(win: object) -> None:
    """Exclude a GLFW window from the taskbar when a Win32 HWND exists."""
    exclude_hwnd_from_taskbar(glfw_window_hwnd(win))
