"""Export spectrum analysis rate / gain must match live preview."""

from __future__ import annotations

from visualizer.gpu_render import resolve_export_analysis_fps, resolve_template_react_gain


def test_export_analysis_fps_defaults_to_preview_60() -> None:
    assert resolve_export_analysis_fps(env={}) == 60
    assert resolve_export_analysis_fps(env={"CAMXORA_EXPORT_ANALYSIS_FPS": ""}) == 60


def test_export_analysis_fps_env_override_clamped() -> None:
    assert resolve_export_analysis_fps(env={"CAMXORA_EXPORT_ANALYSIS_FPS": "30"}) == 30
    assert resolve_export_analysis_fps(env={"CAMXORA_EXPORT_ANALYSIS_FPS": "120"}) == 60
    assert resolve_export_analysis_fps(env={"CAMXORA_EXPORT_ANALYSIS_FPS": "1"}) == 15


def test_export_analysis_fps_follows_existing_analyzer() -> None:
    assert resolve_export_analysis_fps(existing_analyzer_fps=60) == 60
    assert resolve_export_analysis_fps(
        env={"CAMXORA_EXPORT_ANALYSIS_FPS": "30"},
        existing_analyzer_fps=60,
    ) == 60


def test_template_react_gain_prefers_input_gain() -> None:
    assert resolve_template_react_gain({"inputGain": 1.2, "sensitivity": 4.0}) == 1.2
    assert resolve_template_react_gain({"sensitivity": 2.5}) == 2.5
    assert resolve_template_react_gain({}) == 1.0
    assert resolve_template_react_gain({"inputGain": 0, "sensitivity": 3.0}) == 1.0
