"""Upload-copy planning for very large merged videos."""

from __future__ import annotations

from pathlib import Path

from shared.lib.upload_copy import (
    UPLOAD_COPY_THRESHOLD_BYTES,
    build_upload_copy_command,
    make_upload_copy_plan,
    should_make_upload_copy,
    upload_copy_target,
)


def test_threshold_is_two_gib() -> None:
    assert UPLOAD_COPY_THRESHOLD_BYTES == 2 * 1024**3
    assert should_make_upload_copy(UPLOAD_COPY_THRESHOLD_BYTES - 1) is False
    assert should_make_upload_copy(UPLOAD_COPY_THRESHOLD_BYTES) is True
    assert should_make_upload_copy(6 * 1024**3) is True
    assert should_make_upload_copy(None) is False
    assert should_make_upload_copy("n/a") is False


def test_plan_only_for_large_existing_files(tmp_path: Path) -> None:
    small = tmp_path / "small.mp4"
    small.write_bytes(b"x" * 16)
    assert make_upload_copy_plan(small) is None

    big = tmp_path / "big.mp4"
    big.write_bytes(b"x" * 16)
    plan = make_upload_copy_plan(big, size_bytes=5 * 1024**3)

    assert plan is not None
    assert plan.source == big
    assert plan.target == tmp_path / "big.uploadcopy.mp4"
    assert plan.source_bytes == 5 * 1024**3


def test_missing_file_has_no_plan(tmp_path: Path) -> None:
    assert make_upload_copy_plan(tmp_path / "missing.mp4") is None


def test_copy_target_naming() -> None:
    assert upload_copy_target("C:/media/MERGED_OK_abc.mp4").name == "MERGED_OK_abc.uploadcopy.mp4"


def test_command_is_upload_friendly() -> None:
    command = build_upload_copy_command("ffmpeg", "in.mp4", "out.mp4")

    assert command[0] == "ffmpeg"
    assert "-vf" in command
    scale = command[command.index("-vf") + 1]
    assert "min(1080,ih)" in scale
    assert command[command.index("-b:v") + 1] == "6M"
    assert command[-1] == "out.mp4"
    assert "+faststart" in command[command.index("-movflags") + 1]
