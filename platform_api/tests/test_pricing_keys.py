"""Tests for pricing key normalization helpers."""

from platform_api.services.pricing_keys import normalize_suno_pricing_sub_model


class TestNormalizeSunoPricingSubModel:


    def test_empty_returns_empty(self) -> None:
        assert normalize_suno_pricing_sub_model(None) == ""
        assert normalize_suno_pricing_sub_model("") == ""
