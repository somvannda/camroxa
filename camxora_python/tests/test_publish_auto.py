"""Auto-publish decision after a merge completes."""

from __future__ import annotations

from shared.lib.publish_auto import auto_publish_plan, worker_context

CONTEXT = {
    "profile_id": "profile-1",
    "run_dir": r"bass-drive\2026-07-13_Neon-Nights",
    "batch_id": "batch-1",
    "role": "ok",
}


def test_requires_the_upload_toggle() -> None:
    assert auto_publish_plan({}, CONTEXT, "C:/media/merged.mp4") is None
    assert auto_publish_plan({"autoUploadYouTube": False}, CONTEXT, "C:/media/merged.mp4") is None


def test_returns_context_when_enabled() -> None:
    plan = auto_publish_plan(
        {"autoUploadYouTube": True},
        CONTEXT,
        "C:/media/merged.mp4",
    )

    assert plan is not None
    assert plan.profile_id == "profile-1"
    assert plan.merged_path == "C:/media/merged.mp4"
    assert plan.batch_id == "batch-1"
    assert plan.role == "OK"

    context = worker_context(plan)
    assert context["profile_id"] == "profile-1"
    assert context["merged_path"] == "C:/media/merged.mp4"
    assert context["run_dir"] == CONTEXT["run_dir"]
    assert context["batch_id"] == "batch-1"
    assert context["role"] == "OK"


def test_requires_a_merged_file_and_profile() -> None:
    enabled = {"autoUploadYouTube": True}
    assert auto_publish_plan(enabled, CONTEXT, "") is None
    assert auto_publish_plan(enabled, CONTEXT, None) is None
    assert auto_publish_plan(enabled, {"run_dir": "x"}, "C:/media/merged.mp4") is None


def test_accepts_string_flags_from_persisted_settings() -> None:
    for value in ("true", "TRUE", "1", "yes", "on"):
        assert auto_publish_plan({"autoUploadYouTube": value}, CONTEXT, "m.mp4") is not None
    for value in ("false", "0", "", None):
        assert auto_publish_plan({"autoUploadYouTube": value}, CONTEXT, "m.mp4") is None


def test_manual_context_needs_only_a_file_and_profile() -> None:
    from types import SimpleNamespace

    from shared.lib.publish_auto import manual_publish_context

    row = SimpleNamespace(
        meta=SimpleNamespace(
            profile_id="profile-1",
            batch_id="batch-1",
            run_dir="run/dir",
            role="ok",
        )
    )

    context = manual_publish_context(row, "C:/media/merged.mp4")

    assert context is not None
    assert context["merged_path"] == "C:/media/merged.mp4"
    assert context["profile_id"] == "profile-1"
    assert context["role"] == "OK"
    # No upload toggle involved: an explicit click is enough.
    assert manual_publish_context(row, "") is None
    assert manual_publish_context(SimpleNamespace(meta=SimpleNamespace(profile_id="")), "m.mp4") is None
