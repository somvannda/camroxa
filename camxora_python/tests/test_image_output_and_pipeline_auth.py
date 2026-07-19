from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from features.video.services.pipeline_automation_service import PipelineAutomationService
from shared.lib.image_output_utils import ensure_image_output_local
from shared.services.file_service import open_path
from shared.services.platform_client import PlatformApiError


def test_ensure_image_output_local_returns_existing_path(tmp_path: Path) -> None:
    image_path = tmp_path / "thumbnail-16x9.png"
    image_path.write_bytes(b"png-bytes")
    api = MagicMock()

    result = ensure_image_output_local(api, str(image_path), "job-123")

    assert result == str(image_path)
    api.get_image_job_output.assert_not_called()


def test_ensure_image_output_local_downloads_when_missing(tmp_path: Path) -> None:
    image_path = tmp_path / "nested" / "background-16x9.png"
    api = MagicMock()
    api.get_image_job_output.return_value = b"downloaded-png"

    result = ensure_image_output_local(api, str(image_path), "job-456")

    assert result == str(image_path)
    assert image_path.read_bytes() == b"downloaded-png"
    api.get_image_job_output.assert_called_once_with("job-456")


def test_ensure_image_output_local_returns_none_without_api(tmp_path: Path) -> None:
    image_path = tmp_path / "missing.png"

    assert ensure_image_output_local(None, str(image_path), "job-789") is None


def test_open_path_missing_file_emits_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing.png"
    emitted: list[tuple[str, str]] = []
    logged: list[str] = []

    monkeypatch.setattr(
        "shared.services.shell_status.emit_shell_status",
        lambda message, *, tone="neutral": emitted.append((message, tone)),
    )
    monkeypatch.setattr(
        "shared.services.app_logger.log_warn",
        lambda message, *, category="app": logged.append(message),
    )
    monkeypatch.setattr("shared.services.file_service.os.startfile", lambda *_a, **_k: None)

    open_path(str(missing))

    assert emitted == [("File not found: missing.png", "warning")]
    assert logged
    assert "missing.png" in logged[0]


def test_pipeline_automation_service_uses_shared_api() -> None:
    api = MagicMock()
    service = PipelineAutomationService(api)
    assert service._api is api


def test_pipeline_automation_service_marks_auth_blocked_on_401(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from shared.models.desktop import Mp3ListItem, VideoWorkspaceState

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    bg_path = tmp_path / "bg.png"
    bg_path.write_bytes(b"x")
    mp3_path = run_dir / "track.mp3"
    mp3_path.write_bytes(b"mp3")

    api = MagicMock()
    api.consume_local_video.side_effect = PlatformApiError(401, "Unauthenticated")
    service = PipelineAutomationService(api)
    workspace = VideoWorkspaceState(template_id="tpl", template={"layers": []})

    candidate = MagicMock()
    candidate.branch = "long"
    candidate.run_dir = str(run_dir)
    candidate.background_path = str(bg_path)
    candidate.template_id = "tpl"
    candidate.batch_id = "batch"
    candidate.role = "role"
    candidate.output_resolution = None
    candidate.profile_id = None

    monkeypatch.setattr(service._store, "set_template", lambda _id: workspace)
    monkeypatch.setattr(
        service._store,
        "list_mp3_files",
        lambda _dir: [Mp3ListItem(name="track.mp3", path=str(mp3_path))],
    )
    monkeypatch.setattr(service, "_build_renderer_template", lambda *a, **k: {"layers": []})
    monkeypatch.setattr(
        "features.video.services.pipeline_automation_service.build_pipeline_render_scene_request",
        lambda **k: MagicMock(output=MagicMock(width=1920, height=1080, fps=30)),
    )
    monkeypatch.setattr(service, "_publish_workspace", lambda _ws: None)
    monkeypatch.setattr(
        "features.video.services.pipeline_automation_service.VideoPipelineExportWorker",
        MagicMock,
    )

    started = service.start(candidate, settings={})

    assert started is False
    assert service.auth_blocked() is True
