from shared.services.action_feedback import notify_action
from shared.services.shell_status import ShellStatusBus


def test_notify_action_calls_shell_status(monkeypatch) -> None:
    captured: list[tuple[str, str]] = []

    def _emit(message: str, *, tone: str = "neutral") -> None:
        captured.append((message, tone))

    monkeypatch.setattr("shared.services.action_feedback.emit_shell_status", _emit)
    flashed: list[tuple[str, str, int]] = []
    ShellStatusBus.instance().flash_action.connect(
        lambda message, tone, duration_ms: flashed.append((message, tone, duration_ms))
    )
    notify_action("Retrying Suno…", tone="neutral", duration_ms=4000)
    assert captured == [("Retrying Suno…", "neutral")]
    assert flashed == [("Retrying Suno…", "neutral", 4000)]


def test_notify_action_clamps_flash_duration(monkeypatch) -> None:
    monkeypatch.setattr("shared.services.action_feedback.emit_shell_status", lambda *_a, **_k: None)
    flashed: list[int] = []
    ShellStatusBus.instance().flash_action.connect(
        lambda _message, _tone, duration_ms: flashed.append(duration_ms)
    )
    notify_action("Done.", tone="success", duration_ms=500)
    assert flashed == [1500]
