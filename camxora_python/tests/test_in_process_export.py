"""Unit tests for in-process export routing (REQ-2.2)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from features.video.lib.render_scene_request import (
    ManualRenderSceneRequest,
    RenderSceneAssets,
    RenderSceneContext,
    RenderSceneOutput,
)
from features.video.services.in_process_export import (
    in_process_export_enabled,
    preview_matches_export,
    resolve_manual_export_backend,
)
from features.video.workers.manual_export_worker import ManualExportRequest


def _scene(*, template: dict | None = None) -> ManualRenderSceneRequest:
    tpl = template or {"style": "orbit-spikes", "renderBaseHeight": 450.0}
    return ManualRenderSceneRequest(
        mode="manual",
        template=tpl,
        draft={},
        assets=RenderSceneAssets(
            background_path="/b/bg.jpg",
            logo_path="/b/logo.png",
            audio_path="/b/track.mp3",
        ),
        output=RenderSceneOutput(resolution="1920x1080", width=1920, height=1080, fps=24),
        context=RenderSceneContext(
            template_id="tpl",
            branch=None,
            batch_id=None,
            role=None,
            draft_source="local",
        ),
    )


def test_in_process_export_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAMXORA_INPROCESS_EXPORT", raising=False)
    assert in_process_export_enabled() is False


def test_in_process_export_enabled_with_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_INPROCESS_EXPORT", "1")
    assert in_process_export_enabled() is True


def test_resolve_backend_subprocess_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAMXORA_INPROCESS_EXPORT", raising=False)
    preview = SimpleNamespace(
        _gl_ready=True,
        audio_path="/b/track.mp3",
        bg_path="/b/bg.jpg",
        logo_path="/b/logo.png",
        analysis_loading=False,
        analyzer=object(),
        template={"style": "orbit-spikes", "renderBaseHeight": 450.0},
    )
    scene = _scene()
    assert (
        resolve_manual_export_backend(
            preview,
            scene=scene,
            background_path="/b/bg.jpg",
            logo_path="/b/logo.png",
            mp3_path="/b/track.mp3",
        )
        == "subprocess"
    )


def test_resolve_backend_in_process_when_warm_preview_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_INPROCESS_EXPORT", "1")
    tpl = {"style": "orbit-spikes", "renderBaseHeight": 450.0}
    preview = SimpleNamespace(
        _gl_ready=True,
        audio_path="/b/track.mp3",
        bg_path="/b/bg.jpg",
        logo_path="/b/logo.png",
        analysis_loading=False,
        analyzer=object(),
        template=tpl,
    )
    scene = _scene(template=tpl)
    assert (
        resolve_manual_export_backend(
            preview,
            scene=scene,
            background_path="/b/bg.jpg",
            logo_path="/b/logo.png",
            mp3_path="/b/track.mp3",
        )
        == "in-process"
    )


def test_preview_matches_export_false_when_analyzer_missing() -> None:
    preview = SimpleNamespace(
        _gl_ready=True,
        audio_path="/b/track.mp3",
        bg_path="/b/bg.jpg",
        logo_path="/b/logo.png",
        analysis_loading=False,
        analyzer=None,
        template={"style": "orbit-spikes"},
    )
    assert (
        preview_matches_export(
            preview,
            mp3_path="/b/track.mp3",
            template={"style": "orbit-spikes"},
            background_path="/b/bg.jpg",
            logo_path="/b/logo.png",
        )
        is False
    )


def test_manual_export_request_accepts_preview() -> None:
    preview = object()
    req = ManualExportRequest(
        scene=_scene(),
        settings={},
        preview=preview,
    )
    assert req.preview is preview
