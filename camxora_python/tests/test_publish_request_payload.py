"""The hosted media URL must survive serialisation (it did not once)."""

from __future__ import annotations

from shared.models.publishing import CreatePublishJobRequest


def _request() -> CreatePublishJobRequest:
    return CreatePublishJobRequest(
        profile_id="profile-1",
        batch_id="batch-1",
        title="A song",
        file_name="merged.mp4",
        file_size_bytes=2_800_000_000,
        file_path="C:/media/merged.mp4",
    )


def test_media_url_is_a_real_field_not_an_extra_attribute() -> None:
    """model_copy(update=...) on an undeclared field is dropped by model_dump.

    That made the server open a second, presigned upload for a file we had
    already hosted; the duplicate transfer then expired and every job failed.
    """
    request = _request().model_copy(update={"media_url": "https://cdn.example/merged.mp4"})

    payload = request.model_dump(exclude_none=True)

    assert payload["media_url"] == "https://cdn.example/merged.mp4"


def test_payload_still_omits_absent_media() -> None:
    assert "media_url" not in _request().model_dump(exclude_none=True)
