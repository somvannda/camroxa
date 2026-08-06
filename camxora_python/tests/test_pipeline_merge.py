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
