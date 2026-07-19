from shared.services.file_service import open_path, sanitize_local_path


def test_sanitize_local_path_strips_linux_prefix() -> None:
    polluted = (
        "/opt/camxora/repo/C:\\Users\\demo\\AppData\\Local\\Camxora\\Media\\run\\background-16x9.png"
    )
    assert sanitize_local_path(polluted).startswith("C:\\Users\\demo")


def test_open_path_noop_for_empty_string(monkeypatch) -> None:
    called = {"startfile": False}

    def _startfile(_path: str) -> None:
        called["startfile"] = True

    monkeypatch.setattr("shared.services.file_service.os.startfile", _startfile)
    open_path("")
    assert called["startfile"] is False
