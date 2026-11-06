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


def test_the_batch_choice_wins_over_live_settings() -> None:
    stored_on = dict(CONTEXT, auto_upload_youtube=True)
    stored_off = dict(CONTEXT, auto_upload_youtube=False)

    # The run was created with the toggle on: it still publishes after the
    # toggle is turned off in settings.
    assert auto_publish_plan({"autoUploadYouTube": False}, stored_on, "m.mp4") is not None
    # And a run created without it stays unpublished even if the toggle is on.
    assert auto_publish_plan({"autoUploadYouTube": True}, stored_off, "m.mp4") is None


def test_runs_without_a_stored_choice_fall_back_to_settings() -> None:
    assert auto_publish_plan({"autoUploadYouTube": True}, CONTEXT, "m.mp4") is not None
    assert auto_publish_plan({"autoUploadYouTube": False}, CONTEXT, "m.mp4") is None


def test_the_batch_column_spelling_is_honoured() -> None:
    # Producers may send the database column name instead of the settings key.
    context = dict(CONTEXT, auto_upload_youtube=True)
    assert auto_publish_plan({"autoUploadYouTube": False}, context, "m.mp4") is not None
    assert auto_publish_plan({"autoUploadYouTube": True}, dict(CONTEXT, auto_upload_youtube=False), "m.mp4") is None


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


def test_claim_prevents_publishing_the_same_file_twice() -> None:
    from shared.lib.publish_auto import claim_publish, release_publish

    path = "C:/media/BATCH_MERGED_OK.mp4"
    assert claim_publish(path) is True
    # Same file, different separators/case must not publish again.
    assert claim_publish("c:\\media\\batch_merged_ok.mp4") is False

    release_publish(path)
    assert claim_publish(path) is True
    assert claim_publish("") is False
