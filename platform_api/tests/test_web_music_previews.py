"""Free-tier premium preview rules for music.camxora.com."""

from __future__ import annotations

from platform_api.services.web_music_previews import (
    PREVIEW_PER_MODEL_LIMIT,
    PREVIEW_SECONDS,
    is_preview_model,
    model_label,
    preview_quota_payload,
    should_preview,
)


def test_is_preview_model_accepts_only_premium_v6_models() -> None:
    assert is_preview_model("V6") is True
    assert is_preview_model("v6") is True
    assert is_preview_model(" V6_WILD ") is True
    assert is_preview_model("V6_MINI") is False
    assert is_preview_model("V5") is False
    assert is_preview_model(None) is False


def test_should_preview_only_for_free_users() -> None:
    assert should_preview("V6", is_paid=False, has_pack_credits=False) is True
    assert should_preview("V6_WILD", is_paid=False, has_pack_credits=False) is True
    # Paid subscribers and anyone with purchased credits get the full track.
    assert should_preview("V6", is_paid=True, has_pack_credits=False) is False
    assert should_preview("V6", is_paid=False, has_pack_credits=True) is False
    # V6 Mini is the everyday free model and stays full length.
    assert should_preview("V6_MINI", is_paid=False, has_pack_credits=False) is False


def test_preview_quota_payload_has_one_per_model() -> None:
    payload = preview_quota_payload({"V6": 1}, eligible=True)
    assert payload["eligible"] is True
    assert payload["seconds"] == PREVIEW_SECONDS
    by_model = {item["model"]: item for item in payload["models"]}
    assert by_model["V6"]["label"] == "V6 Pro"
    assert by_model["V6"]["limit"] == PREVIEW_PER_MODEL_LIMIT
    assert by_model["V6"]["used"] == 1
    assert by_model["V6"]["remaining"] == 0
    assert by_model["V6_WILD"]["remaining"] == 1
    assert by_model["V6_WILD"]["label"] == "V6 Wild"


def test_model_labels_use_product_names() -> None:
    assert model_label("V6") == "V6 Pro"
    assert model_label("V6_MINI") == "V6 Mini"
    assert model_label("V6_WILD") == "V6 Wild"
