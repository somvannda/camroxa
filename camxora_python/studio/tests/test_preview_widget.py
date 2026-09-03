import time
from pathlib import Path

import pytest

from studio.core.models import MediaAsset
from studio.core.project_state import ProjectState
from studio.ui.preview_widget import PlaybackController, PreviewWidget


@pytest.fixture
def state() -> ProjectState:
    return ProjectState()


def _add_audio_clip(state: ProjectState, sample_audio: Path) -> None:
    media = MediaAsset(
        id="m-play",
        name="sample.wav",
        type="audio",
        path=str(sample_audio),
        duration=1.5,
        sample_rate=22050,
    )
    state.add_media(media)
    track = state.add_track("audio")
    state.add_clip_from_media(media, track, drop_time=0.0)


def _stub_mixer_start_stop(controller: PlaybackController):
    """Replace the mixer's start/stop with fakes that just flip `_stream`
    (so the real `is_running` property still works) — avoids touching real
    audio hardware while still exercising PlaybackController's own
    open-once-stay-open logic."""
    start_calls: list[int] = []
    stop_calls: list[int] = []

    def _fake_start() -> bool:
        controller.mixer._stream = object()
        start_calls.append(1)
        return True

    def _fake_stop() -> None:
        controller.mixer._stream = None
        stop_calls.append(1)

    controller.mixer._stream = None
    controller.mixer.start = _fake_start
    controller.mixer.stop = _fake_stop
    return start_calls, stop_calls


def test_pause_does_not_close_the_audio_stream(qtbot, state: ProjectState, sample_audio: Path):
    _add_audio_clip(state, sample_audio)
    preview = PreviewWidget()
    qtbot.addWidget(preview)
    controller = PlaybackController(state, preview)
    start_calls, stop_calls = _stub_mixer_start_stop(controller)

    controller.set_playing(True)
    assert start_calls == [1]

    controller.set_playing(False)  # pause — must NOT tear down the stream
    assert stop_calls == []
    assert controller.mixer.is_running is True

    controller.shutdown()


def test_repeated_play_pause_toggles_never_reopen_the_stream(
    qtbot, state: ProjectState, sample_audio: Path
):
    _add_audio_clip(state, sample_audio)
    preview = PreviewWidget()
    qtbot.addWidget(preview)
    controller = PlaybackController(state, preview)
    start_calls, stop_calls = _stub_mixer_start_stop(controller)

    for _ in range(3):
        controller.set_playing(True)
        controller.set_playing(False)

    assert start_calls == [1]  # opened exactly once across every toggle
    assert stop_calls == []  # never closed just from pausing

    controller.shutdown()
    assert stop_calls == [1]  # only shutdown() actually tears it down


def test_prewarm_audio_decodes_and_precomputes_bands_in_background(
    qtbot, state: ProjectState, sample_audio: Path
):
    preview = PreviewWidget()
    qtbot.addWidget(preview)
    controller = PlaybackController(state, preview)
    media = MediaAsset(
        id="m1", name="sample.wav", type="audio", path=str(sample_audio), duration=1.5, sample_rate=22050
    )

    controller.prewarm_audio([media])

    # Generous timeout: librosa's numba-jitted STFT path has a one-time JIT
    # warmup cost (several seconds) the first time it's ever called in a
    # process — this test only cares that prewarming completes off the
    # main thread, not how long that warmup takes.
    deadline = time.monotonic() + 30.0
    source = None
    while time.monotonic() < deadline:
        source = controller.audio_cache._sources.get("m1")
        if source is not None and source._band_grid is not None:
            break
        time.sleep(0.05)

    assert source is not None
    assert source._band_grid is not None  # STFT precompute already ran, not deferred to first playback

    controller.shutdown()


def test_render_skips_repeated_full_composite_for_audio_only_playback(
    qtbot, state: ProjectState, sample_audio: Path, monkeypatch
):
    """Regression test: plain audio-only playback (no visualizer) used to
    re-run the full numpy composite + QImage conversion + QLabel repaint on
    every single ~16ms timer tick even though the picture never changes —
    pure wasted CPU that holds the GIL long enough to starve the real-time
    sounddevice callback thread, heard as audio stutter."""
    media = MediaAsset(id="m1", name="sample.wav", type="audio", path=str(sample_audio), duration=5.0)
    state.add_media(media)
    track = state.add_track("audio")
    state.add_clip_from_media(media, track, drop_time=0.0)  # viz_enabled defaults to False

    preview = PreviewWidget()
    qtbot.addWidget(preview)
    controller = PlaybackController(state, preview)

    import ui.preview_widget as preview_widget_module

    original_render_frame = preview_widget_module.render_frame
    render_calls: list[int] = []

    def _counting_render_frame(*args, **kwargs):
        render_calls.append(1)
        return original_render_frame(*args, **kwargs)

    monkeypatch.setattr(preview_widget_module, "render_frame", _counting_render_frame)

    controller.render_now()
    assert len(render_calls) == 1  # first render after entering the "blank" (no-viz) state

    for _ in range(5):
        controller._render_and_update()
    assert len(render_calls) == 1  # nothing visually changes — repeat ticks must not re-render

    # Turning the visualizer on makes the picture change every tick again.
    ref = state.get_clip(state.selected_clip_id)
    assert ref is not None
    ref[1].viz_enabled = True
    for _ in range(3):
        controller._render_and_update()
    assert len(render_calls) == 4

    controller.shutdown()


def test_playlist_preview_renders_at_full_canvas_resolution(qtbot, state: ProjectState):
    """Playlist layout must not re-flow when the preview widget is resized."""
    state.playlist_preview_active = True
    preview = PreviewWidget()
    qtbot.addWidget(preview)
    preview.resize(400, 225)
    controller = PlaybackController(state, preview)

    canvas_w, canvas_h = state.canvas_size()
    assert controller._render_dimensions(interactive=False) == (canvas_w, canvas_h)

    preview.resize(1600, 900)
    assert controller._render_dimensions(interactive=False) == (canvas_w, canvas_h)
    controller.shutdown()


def test_playlist_preview_skips_interactive_async_render(qtbot, state: ProjectState, monkeypatch):
    """Template/style changes must not show a blurry half-res frame first."""
    state.playlist_preview_active = True
    preview = PreviewWidget()
    qtbot.addWidget(preview)
    preview.resize(960, 540)
    controller = PlaybackController(state, preview)

    async_starts: list[int] = []
    sync_renders: list[tuple[int, int]] = []

    def _track_async(*_args, **_kwargs):
        async_starts.append(1)

    def _track_render(*_args, **kwargs):
        sync_renders.append((kwargs.get("width"), kwargs.get("height")))
        import numpy as np

        w = kwargs.get("width") or 640
        h = kwargs.get("height") or 360
        return np.zeros((h, w, 3), dtype=np.uint8)

    monkeypatch.setattr(controller, "_start_async_render", _track_async)
    monkeypatch.setattr("ui.preview_widget.render_frame", _track_render)

    controller.render_now(interactive=True)

    assert async_starts == []
    assert len(sync_renders) == 1
    render_w, render_h = sync_renders[0]
    canvas_w, canvas_h = state.canvas_size()
    assert (render_w, render_h) == (canvas_w, canvas_h)

    controller.shutdown()


def test_prewarm_audio_skips_image_assets_and_empty_lists(qtbot, state: ProjectState):
    preview = PreviewWidget()
    qtbot.addWidget(preview)
    controller = PlaybackController(state, preview)
    image_media = MediaAsset(id="img1", name="pic.png", type="image", path="/pic.png")

    controller.prewarm_audio([])
    controller.prewarm_audio([image_media])
    time.sleep(0.1)

    assert controller.audio_cache._sources == {}
    controller.shutdown()


def test_set_playing_ignored_when_timeline_empty(qtbot, state: ProjectState):
    preview = PreviewWidget()
    qtbot.addWidget(preview)
    controller = PlaybackController(state, preview)
    start_calls, _ = _stub_mixer_start_stop(controller)

    controller.set_playing(True)

    assert state.is_playing is False
    assert preview.transport._playing is False
    assert start_calls == []

    controller.shutdown()


def test_toggle_play_ignored_when_timeline_empty(qtbot, state: ProjectState):
    preview = PreviewWidget()
    qtbot.addWidget(preview)
    controller = PlaybackController(state, preview)
    _stub_mixer_start_stop(controller)

    controller.toggle_play()

    assert state.is_playing is False
    controller.shutdown()


def test_playback_prewarms_mixer_rate_before_start(qtbot, state: ProjectState, sample_audio: Path):
    _add_audio_clip(state, sample_audio)
    preview = PreviewWidget()
    qtbot.addWidget(preview)
    controller = PlaybackController(state, preview)
    _stub_mixer_start_stop(controller)

    controller.set_playing(True)

    source = controller.audio_cache._sources.get("m-play")
    assert source is not None
    assert controller.mixer.sample_rate in source._mono_resampled
    controller.shutdown()
