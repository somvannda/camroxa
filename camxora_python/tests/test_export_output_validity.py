"""Tests for post-export MP4 validity helpers."""

from __future__ import annotations

from pathlib import Path

from features.video.lib.export_output_validity import (
    export_media_looks_complete,
    is_usable_export_output,
    resolve_written_export_path,
)
from features.video.lib.render_scene_request import MIN_VALID_EXPORT_BYTES


def test_resolve_written_export_path_prefers_existing_preferred(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    preferred = tmp_path / "track.mp4"
    preferred.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 8))
    resolved = resolve_written_export_path(
        preferred_path=str(preferred),
        output_dir=str(tmp_path),
        audio_path=str(tmp_path / "track.mp3"),
        require_media=True,
    )
    assert resolved == str(preferred)


def test_resolve_written_export_path_falls_back_to_stem(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    stem = tmp_path / "track.mp4"
    stem.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 8))
    missing_stamp = tmp_path / "track_CAMXORA_stamp.mp4"
    resolved = resolve_written_export_path(
        preferred_path=str(missing_stamp),
        output_dir=str(tmp_path),
        audio_path=str(tmp_path / "track.mp3"),
        require_media=True,
    )
    assert resolved == str(stem)


def test_export_media_looks_complete_rejects_short_vs_audio(tmp_path: Path, monkeypatch) -> None:
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"id3")
    video = tmp_path / "video.mp4"
    video.write_bytes(b"ftyp")

    def _fake_duration(path: str, _probe: str) -> float:
        if path.endswith(".mp3"):
            return 100.0
        return 10.0

    monkeypatch.setattr(
        "features.video.lib.export_output_validity._probe_format_duration",
        _fake_duration,
    )
    monkeypatch.setattr(
        "features.video.lib.export_output_validity._has_video_stream",
        lambda *_args, **_kwargs: True,
    )
    assert (
        export_media_looks_complete(
            str(video),
            ffprobe_path="ffprobe",
            audio_path=str(audio),
        )
        is False
    )


def test_is_usable_export_output_size_only_when_no_ffprobe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    target = tmp_path / "out.mp4"
    target.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 1))
    assert is_usable_export_output(str(target), require_media=True) is True
    tiny = tmp_path / "tiny.mp4"
    tiny.write_bytes(b"x")
    assert is_usable_export_output(str(tiny), require_media=True) is False


def test_has_video_stream_treats_returncode_zero_as_success(tmp_path: Path, monkeypatch) -> None:
    """Regression: `returncode or 1` treated ffprobe success (0) as failure."""
    from features.video.lib import export_output_validity as mod

    class _Result:
        returncode = 0
        stdout = "video\n"
        stderr = ""

    probe = tmp_path / "ffprobe.exe"
    probe.write_bytes(b"x")
    video = tmp_path / "out.mp4"
    video.write_bytes(b"x")
    monkeypatch.setattr(mod, "run_hidden", lambda *_a, **_k: _Result())
    assert mod._has_video_stream(str(video), str(probe)) is True


def test_export_media_looks_complete_accepts_when_render_and_audio_agree(
    tmp_path: Path, monkeypatch
) -> None:
    """A small ffprobe over-estimate of the MP3 stays within tolerance."""
    from features.video.lib import export_output_validity as mod

    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"id3")
    video = tmp_path / "video.mp4"
    video.write_bytes(b"ftyp")

    # Real case: MP3 header reads 211.6s, actual audio 208.6s, MP4 208.6s.
    def _fake_duration(path: str, _probe: str) -> float:
        return 211.6 if path.endswith(".mp3") else 208.6

    monkeypatch.setattr(mod, "_probe_format_duration", _fake_duration)
    monkeypatch.setattr(mod, "_has_video_stream", lambda *_a, **_k: True)
    assert (
        mod.export_media_looks_complete(
            str(video),
            ffprobe_path="ffprobe",
            audio_path=str(audio),
            expected_duration_sec=208.6,
        )
        is True
    )


def test_export_media_looks_complete_rejects_short_vs_source_audio(
    tmp_path: Path, monkeypatch
) -> None:
    """A short decode makes the render AND the MP4 short; the source audio catches it."""
    from features.video.lib import export_output_validity as mod

    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"id3")
    video = tmp_path / "video.mp4"
    video.write_bytes(b"ftyp")

    def _fake_duration(path: str, _probe: str) -> float:
        return 208.6 if path.endswith(".mp3") else 117.6

    monkeypatch.setattr(mod, "_probe_format_duration", _fake_duration)
    monkeypatch.setattr(mod, "_has_video_stream", lambda *_a, **_k: True)
    # MP4 matches the (short) rendered length, but is far short of the source audio.
    assert (
        mod.export_media_looks_complete(
            str(video),
            ffprobe_path="ffprobe",
            audio_path=str(audio),
            expected_duration_sec=117.6,
        )
        is False
    )


def test_export_media_looks_complete_rejects_short_vs_rendered(
    tmp_path: Path, monkeypatch
) -> None:
    from features.video.lib import export_output_validity as mod

    video = tmp_path / "video.mp4"
    video.write_bytes(b"ftyp")

    monkeypatch.setattr(
        mod, "_probe_format_duration", lambda *_a, **_k: 40.0
    )
    monkeypatch.setattr(mod, "_has_video_stream", lambda *_a, **_k: True)
    assert (
        mod.export_media_looks_complete(
            str(video),
            ffprobe_path="ffprobe",
            expected_duration_sec=100.0,
        )
        is False
    )


def test_describe_export_output_failure_reports_reason(tmp_path: Path, monkeypatch) -> None:
    from features.video.lib import export_output_validity as mod

    video = tmp_path / "video.mp4"
    video.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 8))

    monkeypatch.setattr(mod, "resolve_ffprobe_path", lambda *_a, **_k: "ffprobe")
    monkeypatch.setattr(mod, "_has_video_stream", lambda *_a, **_k: True)
    monkeypatch.setattr(mod, "_probe_format_duration", lambda *_a, **_k: 40.0)
    reason = mod.describe_export_output_failure(
        str(video), expected_duration_sec=100.0
    )
    assert "40.0s" in reason and "100.0s" in reason
