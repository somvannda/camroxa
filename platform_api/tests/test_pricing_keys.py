"""Tests for pricing key normalization helpers."""

from platform_api.services.pricing_keys import normalize_suno_pricing_sub_model


class TestNormalizeSunoPricingSubModel:
    def test_v5_5_stays_distinct_from_v5(self) -> None:
        assert normalize_suno_pricing_sub_model("V5_5") == "V5_5"
        assert normalize_suno_pricing_sub_model("v5.5") == "V5_5"
        assert normalize_suno_pricing_sub_model("V55") == "V5_5"

    def test_v5_unchanged(self) -> None:
        assert normalize_suno_pricing_sub_model("V5") == "V5"
        assert normalize_suno_pricing_sub_model("v5") == "V5"

    def test_empty_returns_empty(self) -> None:
        assert normalize_suno_pricing_sub_model(None) == ""
        assert normalize_suno_pricing_sub_model("") == ""
