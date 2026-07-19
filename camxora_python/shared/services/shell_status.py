"""App shell footer status — mirrors camxora shared/lib/shellStatus.ts."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class ShellStatusBus(QObject):
    show_message = Signal(str, str)
    restore_default = Signal()
    flash_action = Signal(str, str, int)

    _instance: ShellStatusBus | None = None

    @classmethod
    def instance(cls) -> ShellStatusBus:
        if cls._instance is None:
            cls._instance = ShellStatusBus()
        return cls._instance


def emit_shell_status(message: str, *, tone: str = "neutral") -> None:
    text = str(message or "").strip()
    if text:
        # Mirror user-visible actions into the Log page without blocking UI.
        try:
            from shared.services.app_logger import log_info

            log_info(text, category="ui")
        except Exception:
            pass
    safe_tone = tone if tone in {"neutral", "success", "error", "warning"} else "neutral"
    ShellStatusBus.instance().show_message.emit(message, safe_tone)


def restore_shell_status() -> None:
    ShellStatusBus.instance().restore_default.emit()
