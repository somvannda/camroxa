"""User-visible feedback for desktop actions (shell footer + log)."""

from __future__ import annotations

from shared.services.shell_status import ShellStatusBus, emit_shell_status


def notify_action(
    message: str,
    *,
    tone: str = "neutral",
    duration_ms: int = 5000,
) -> None:
    """Publish action feedback to the shell footer and floating badge."""
    text = str(message or "").strip()
    if not text:
        return
    safe_tone = tone if tone in {"neutral", "success", "error", "warning"} else "neutral"
    emit_shell_status(text, tone=safe_tone)
    ShellStatusBus.instance().flash_action.emit(text, safe_tone, max(int(duration_ms), 1500))
