"""Tests for pipeline export merge helpers."""

from __future__ import annotations

from pathlib import Path

from features.video.lib.pipeline_merge import (
    build_merged_output_path,
    is_auto_merge_enabled_for_branch,
    list_branch_export_outputs,
    normalize_merge_role,
    safe_batch_suffix,
)
from features.video.lib.render_scene_request import MIN_VALID_EXPORT_BYTES


def test_safe_batch_suffix_parses_standard_batch_id() -> None:
    assert safe_batch_suffix("batch-2026-07-08-12-34") == "2026-07-08_12_34"


def test_safe_batch_suffix_sanitizes_freeform_text() -> None:
    assert safe_batch_suffix("run #1") == "run_1"


def test_normalize_merge_role() -> None:
    assert normalize_merge_role("primary") == "PRIMARY"
    assert normalize_merge_role("alt") == "SECONDARY"
    assert normalize_merge_role("secondary") == "SECONDARY"


def test_is_auto_merge_enabled_for_branch() -> None:
    settings = {"autoMergeAfterVideo": True, "autoReelAfterVideo": True}
    assert is_auto_merge_enabled_for_branch(settings, "long") is True
    assert is_auto_merge_enabled_for_branch(settings, "reel") is True
    assert is_auto_merge_enabled_for_branch({"autoMergeAfterVideo": True}, "reel") is False
    assert is_auto_merge_enabled_for_branch({}, "long") is False


def test_is_auto_merge_reads_truthy_string_settings() -> None:
    """Live API settings may stringify booleans; must still enable long merge."""
    settings = {"autoMergeAfterVideo": "true", "autoReelAfterVideo": "true"}
    assert is_auto_merge_enabled_for_branch(settings, "long") is True
    assert is_auto_merge_enabled_for_branch(settings, "reel") is True


def test_build_merged_output_path() -> None:
    long_path = build_merged_output_path(
        output_dir="/tmp/run",
        batch_id="batch-2026-07-08-1-2",
        role="primary",
        branch="long",
    )
    reel_path = build_merged_output_path(
        output_dir="/tmp/run",
        batch_id="batch-2026-07-08-1-2",
        role="alt",
        branch="reel",
    )
    assert long_path.endswith("MERGED_PRIMARY_2026-07-08_1_2.mp4")
    assert reel_path.endswith("MERGED_REEL_SECONDARY_2026-07-08_1_2.mp4")


def test_resolve_merge_encode_settings_matches_export_tier() -> None:
    from features.video.lib.pipeline_merge import resolve_merge_encode_settings

    settings = {
        "videoExportTier": "standard",
        "outputResolution": "1920x1080",
        "videoExportFps": 60,
        "videoExportSpeedMode": "fast",
    }
    encode = resolve_merge_encode_settings(settings, branch="long", pipeline=False)
    assert encode.width == 1920
    assert encode.height == 1080
    assert encode.fps == 60
    assert encode.speed_mode == "fast"


def test_resolve_merge_encode_settings_reel_uses_9x16() -> None:
    from features.video.lib.pipeline_merge import resolve_merge_encode_settings

    encode = resolve_merge_encode_settings(
        {"outputResolution": "1920x1080", "videoExportFps": 30, "videoExportSpeedMode": "balanced"},
        branch="reel",
        pipeline=True,
    )
    assert encode.width == 1080
    assert encode.height == 1920


def test_build_merge_reencode_args_matches_fast_export(monkeypatch) -> None:
    from features.video.lib.pipeline_merge import MergeEncodeSettings, build_merge_reencode_args

    monkeypatch.setattr(
        "visualizer.nvenc_capability.probe_h264_nvenc",
        lambda *_a, **_k: False,
    )
    args, label = build_merge_reencode_args(
        ffmpeg_path="ffmpeg",
        encode=MergeEncodeSettings(width=1920, height=1080, fps=60, speed_mode="fast"),
    )
    assert label == "CPU x264"
    assert "-vf" in args
    assert any("fps=60" in str(part) for part in args)
    assert "libx264" in args
    assert "superfast" in args
    # 1080p @ 60fps · fast = 8 Mbps * 2 * 0.70 = 11200 kbps
    assert args[args.index("-b:v") + 1] == "11200k"
    assert "-crf" not in args
    assert "192k" in args
    assert args[args.index("-vf") + 1].startswith("scale=1920:1080")


def test_merge_video_outputs_copy_only_fails_without_reencode(tmp_path: Path, monkeypatch) -> None:
    from features.video.lib.pipeline_merge import MergeEncodeSettings, merge_video_outputs

    paths: list[str] = []
    for index in range(2):
        target = tmp_path / f"track-{index}.mp4"
        target.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 64))
        paths.append(str(target))

    monkeypatch.setattr("features.video.lib.pipeline_merge._is_file_stable", lambda _path: True)
    monkeypatch.setattr("features.video.lib.pipeline_merge.find_ffmpeg_from_path_hint", lambda _hint: "ffmpeg")
    monkeypatch.setattr("features.video.lib.pipeline_merge.find_ffprobe_from_path_hint", lambda _hint: "")
    monkeypatch.setattr(
        "features.video.lib.pipeline_merge.assert_concat_copy_compatible",
        lambda *_a, **_k: None,
    )

    calls: list[list[str]] = []

    def _fake_run_ffmpeg_with_progress(*, ffmpeg_path, args, total_duration_sec, emit, cancel):
        calls.append([ffmpeg_path, *list(args)])
        raise RuntimeError("copy failed")

    monkeypatch.setattr(
        "features.video.lib.pipeline_merge._run_ffmpeg_with_progress",
        _fake_run_ffmpeg_with_progress,
    )

    merged_target = tmp_path / "MERGED_PRIMARY_batch.mp4"
    try:
        merge_video_outputs(
            ffmpeg_path="ffmpeg",
            mp4_paths=paths,
            target_path=str(merged_target),
            shuffle=False,
            encode=MergeEncodeSettings(width=1920, height=1080, fps=60, speed_mode="fast"),
        )
        raise AssertionError("expected merge to fail")
    except RuntimeError as exc:
        assert "Lossless merge failed" in str(exc)
    assert len(calls) == 1
    assert "copy" in calls[0]


def test_identities_concat_compatible_flags_resolution_mismatch() -> None:
    from features.video.lib.export_output_validity import ExportStreamIdentity, identities_concat_compatible

    left = ExportStreamIdentity(1920, 1080, 60.0, "h264", "pc", 48000, 2)
    right = ExportStreamIdentity(1280, 720, 60.0, "h264", "pc", 48000, 2)
    reasons = identities_concat_compatible(left, right)
    assert any("resolution" in reason for reason in reasons)


def test_list_branch_export_outputs_filters_reel_and_long(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    valid = tmp_path / "track.mp4"
    valid.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 1))
    reel = tmp_path / "track_REEL.mp4"
    reel.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 1))
    merged = tmp_path / "MERGED_PRIMARY_batch.mp4"
    merged.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 1))
    tiny = tmp_path / "tiny.mp4"
    tiny.write_bytes(b"x")

    long_outputs = list_branch_export_outputs(str(tmp_path), "long")
    reel_outputs = list_branch_export_outputs(str(tmp_path), "reel")

    assert long_outputs == [str(valid)]
    assert reel_outputs == [str(reel)]


def test_collect_verified_merge_inputs_skips_missing_and_scans_fallback(tmp_path: Path, monkeypatch) -> None:
    from features.video.lib.pipeline_merge import collect_verified_merge_inputs

    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    real = tmp_path / "song-a.mp4"
    real.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 1))
    other = tmp_path / "song-b.mp4"
    other.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 1))
    missing = str(tmp_path / "missing_CAMXORA_stamp.mp4")

    verified = collect_verified_merge_inputs(
        [missing, str(real)],
        run_dir=str(tmp_path),
        branch="long",
        ffmpeg_path="ffmpeg",
    )
    assert verified == [str(real), str(other)]


def test_merge_video_outputs_validates_paths_without_stat_is_file(tmp_path: Path, monkeypatch) -> None:
    """Regression: os.stat_result has no is_file(); merge must use Path.is_file()."""
    from features.video.lib.pipeline_merge import merge_video_outputs

    paths: list[str] = []
    for index in range(2):
        target = tmp_path / f"track-{index}.mp4"
        target.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 64))
        paths.append(str(target))

    monkeypatch.setattr("features.video.lib.pipeline_merge._is_file_stable", lambda _path: True)
    monkeypatch.setattr("features.video.lib.pipeline_merge.find_ffmpeg_from_path_hint", lambda _hint: "ffmpeg")
    monkeypatch.setattr("features.video.lib.pipeline_merge.find_ffprobe_from_path_hint", lambda _hint: "")
    monkeypatch.setattr(
        "features.video.lib.pipeline_merge.assert_concat_copy_compatible",
        lambda *_a, **_k: None,
    )

    merged_target = tmp_path / "MERGED_PRIMARY_batch.mp4"

    def _fake_run_ffmpeg_with_progress(*, ffmpeg_path, args, total_duration_sec, emit, cancel):
        output_path = Path(args[-1])
        output_path.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 64))
        emit("Merging… 100%", 100)

    monkeypatch.setattr(
        "features.video.lib.pipeline_merge._run_ffmpeg_with_progress",
        _fake_run_ffmpeg_with_progress,
    )

    result = merge_video_outputs(
        ffmpeg_path="ffmpeg",
        mp4_paths=paths,
        target_path=str(merged_target),
        shuffle=False,
    )

    assert result == str(merged_target)


def test_merge_video_outputs_raises_when_usable_inputs_drop_below_two(
    tmp_path: Path, monkeypatch
) -> None:
    from features.video.lib.pipeline_merge import merge_video_outputs

    paths: list[str] = []
    for index in range(2):
        target = tmp_path / f"track-{index}.mp4"
        target.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 64))
        paths.append(str(target))

    monkeypatch.setattr("features.video.lib.pipeline_merge._is_file_stable", lambda _path: False)
    monkeypatch.setattr("features.video.lib.pipeline_merge.find_ffmpeg_from_path_hint", lambda _hint: "ffmpeg")
    monkeypatch.setattr("features.video.lib.pipeline_merge.find_ffprobe_from_path_hint", lambda _hint: "")

    try:
        merge_video_outputs(
            ffmpeg_path="ffmpeg",
            mp4_paths=paths,
            target_path=str(tmp_path / "MERGED_PRIMARY_batch.mp4"),
            shuffle=False,
        )
        raise AssertionError("expected merge to fail instead of returning None")
    except RuntimeError as exc:
        assert "did not produce a file" in str(exc)


def test_merge_video_outputs_does_not_require_current_export_specs(
    tmp_path: Path, monkeypatch
) -> None:
    from features.video.lib.pipeline_merge import MergeEncodeSettings, merge_video_outputs

    paths: list[str] = []
    for index in range(2):
        target = tmp_path / f"track-{index}.mp4"
        target.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 64))
        paths.append(str(target))

    monkeypatch.setattr("features.video.lib.pipeline_merge._is_file_stable", lambda _path: True)
    monkeypatch.setattr("features.video.lib.pipeline_merge.find_ffmpeg_from_path_hint", lambda _hint: "ffmpeg")
    monkeypatch.setattr("features.video.lib.pipeline_merge.find_ffprobe_from_path_hint", lambda _hint: "")
    seen: dict[str, object] = {}

    def _capture_compat(*_args, **kwargs):
        seen["expected_width"] = kwargs.get("expected_width")
        seen["expected_fps"] = kwargs.get("expected_fps")
        return None

    monkeypatch.setattr(
        "features.video.lib.pipeline_merge.assert_concat_copy_compatible",
        _capture_compat,
    )

    def _fake_run_ffmpeg_with_progress(*, ffmpeg_path, args, total_duration_sec, emit, cancel):
        Path(args[-1]).write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 64))
        emit("Merging… 100%", 100)

    monkeypatch.setattr(
        "features.video.lib.pipeline_merge._run_ffmpeg_with_progress",
        _fake_run_ffmpeg_with_progress,
    )

    result = merge_video_outputs(
        ffmpeg_path="ffmpeg",
        mp4_paths=paths,
        target_path=str(tmp_path / "MERGED_PRIMARY_batch.mp4"),
        shuffle=False,
        encode=MergeEncodeSettings(width=1920, height=1080, fps=30),
        match_export_specs=False,
    )
    assert result is not None
    assert seen["expected_width"] is None
    assert seen["expected_fps"] is None


def test_is_file_stable_accepts_unchanged_size(tmp_path: Path, monkeypatch) -> None:
    from features.video.lib.pipeline_merge import _is_file_stable

    target = tmp_path / "track.mp4"
    target.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 64))
    monkeypatch.setattr("features.video.lib.pipeline_merge.time.sleep", lambda _seconds: None)
    assert _is_file_stable(str(target)) is True


def test_resolve_merge_run_dir_prefers_nested_duplicate_album(tmp_path: Path, monkeypatch) -> None:
    from features.video.lib.pipeline_merge import resolve_merge_run_dir

    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    outer = tmp_path / "trendrush-audio" / "2026-08-11_album"
    nested = outer / "trendrush-audio" / "2026-08-11_album"
    nested.mkdir(parents=True)
    for name in ("a.mp4", "b.mp4"):
        (nested / name).write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 1))
    (outer / "leftover.mp4").write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 1))

    assert resolve_merge_run_dir(str(outer), "long") == str(nested)


def test_collect_verified_falls_back_when_export_specs_mismatch(tmp_path: Path, monkeypatch) -> None:
    from features.video.lib.pipeline_merge import collect_verified_merge_inputs

    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        "features.video.lib.export_output_validity.export_matches_batch_specs",
        lambda *_args, **_kwargs: False,
    )
    paths = []
    for name in ("a.mp4", "b.mp4"):
        target = tmp_path / name
        target.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 1))
        paths.append(str(target))

    verified = collect_verified_merge_inputs(
        paths,
        run_dir=str(tmp_path),
        branch="long",
        ffmpeg_path="ffmpeg",
        expected_width=1920,
        expected_height=1080,
        expected_fps=30,
    )
    assert verified == paths


def test_merge_video_outputs_raises_when_fewer_than_two_requested(tmp_path: Path) -> None:
    from features.video.lib.pipeline_merge import merge_video_outputs

    try:
        merge_video_outputs(
            ffmpeg_path="ffmpeg",
            mp4_paths=[str(tmp_path / "only.mp4")],
            target_path=str(tmp_path / "MERGED_PRIMARY_batch.mp4"),
            shuffle=False,
        )
        raise AssertionError("expected merge to fail")
    except RuntimeError as exc:
        assert "did not produce a file" in str(exc)


def test_merge_video_outputs_does_not_reuse_stale_merged_file(tmp_path: Path, monkeypatch) -> None:
    from features.video.lib.pipeline_merge import merge_video_outputs

    merged_target = tmp_path / "MERGED_PRIMARY_batch.mp4"
    merged_target.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 64))
    paths: list[str] = []
    for index in range(2):
        target = tmp_path / f"track-{index}.mp4"
        target.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 64))
        paths.append(str(target))
    older = merged_target.stat().st_mtime - 120
    os_utime = __import__("os").utime
    os_utime(merged_target, (older, older))

    monkeypatch.setattr("features.video.lib.pipeline_merge._is_file_stable", lambda _path: True)
    monkeypatch.setattr("features.video.lib.pipeline_merge.find_ffmpeg_from_path_hint", lambda _hint: "ffmpeg")
    monkeypatch.setattr("features.video.lib.pipeline_merge.find_ffprobe_from_path_hint", lambda _hint: "")
    monkeypatch.setattr(
        "features.video.lib.pipeline_merge.assert_concat_copy_compatible",
        lambda *_a, **_k: None,
    )
    calls: list[str] = []

    def _fake_run_ffmpeg_with_progress(*, ffmpeg_path, args, total_duration_sec, emit, cancel):
        calls.append("ran")
        Path(args[-1]).write_bytes(b"y" * (MIN_VALID_EXPORT_BYTES + 64))
        emit("Merging… 100%", 100)

    monkeypatch.setattr(
        "features.video.lib.pipeline_merge._run_ffmpeg_with_progress",
        _fake_run_ffmpeg_with_progress,
    )

    result = merge_video_outputs(
        ffmpeg_path="ffmpeg",
        mp4_paths=paths,
        target_path=str(merged_target),
        shuffle=False,
    )
    assert result == str(merged_target)
    assert calls == ["ran"]


def test_merge_video_outputs_reuses_current_merged_file(tmp_path: Path, monkeypatch) -> None:
    from features.video.lib.pipeline_merge import merge_video_outputs

    paths: list[str] = []
    for index in range(2):
        target = tmp_path / f"track-{index}.mp4"
        target.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 64))
        paths.append(str(target))
    merged_target = tmp_path / "MERGED_PRIMARY_batch.mp4"
    merged_target.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 64))

    def _should_not_run(**_kwargs):
        raise AssertionError("should reuse existing merged file")

    monkeypatch.setattr(
        "features.video.lib.pipeline_merge._run_ffmpeg_with_progress",
        _should_not_run,
    )
    result = merge_video_outputs(
        ffmpeg_path="ffmpeg",
        mp4_paths=paths,
        target_path=str(merged_target),
        shuffle=False,
    )
    assert result == str(merged_target)


def test_merged_output_ready_rejects_missing_and_tiny(tmp_path: Path) -> None:
    from features.video.lib.pipeline_merge import merged_output_ready

    missing = tmp_path / "MERGED_PRIMARY.mp4"
    tiny = tmp_path / "tiny.mp4"
    tiny.write_bytes(b"x")
    ready = tmp_path / "ready.mp4"
    ready.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 1))
    assert merged_output_ready(str(missing)) is False
    assert merged_output_ready(str(tiny)) is False
    assert merged_output_ready(str(ready)) is True
    assert merged_output_ready("") is False

