"""Unit tests for plan limit validation.

Tests validate_plan_limits() against the boundary rules defined in Requirement 1.2.
"""

import pytest

from platform_api.exceptions import ValidationError
from platform_api.services.plan_validation import validate_plan_limits


class TestValidatePlanLimits:
    """Tests for validate_plan_limits."""

    # --- Happy path: valid inputs ---

    def test_all_valid_with_none_monthly_limits(self) -> None:
        """None monthly limits (unlimited) should pass validation."""
        validate_plan_limits(
            monthly_song_limit=None,
            monthly_image_limit=None,
            daily_song_limit_per_channel=7,
            daily_image_limit_per_channel=7,
        )

    def test_all_valid_with_zero_monthly_limits(self) -> None:
        """Zero monthly limits (disabled) should pass validation."""
        validate_plan_limits(
            monthly_song_limit=0,
            monthly_image_limit=0,
            daily_song_limit_per_channel=1,
            daily_image_limit_per_channel=1,
        )

    def test_all_valid_at_upper_bounds(self) -> None:
        """Maximum allowed values should pass."""
        validate_plan_limits(
            monthly_song_limit=100_000,
            monthly_image_limit=100_000,
            daily_song_limit_per_channel=1_000,
            daily_image_limit_per_channel=1_000,
        )

    def test_valid_mid_range_values(self) -> None:
        """Typical mid-range values should pass."""
        validate_plan_limits(
            monthly_song_limit=500,
            monthly_image_limit=1_000,
            daily_song_limit_per_channel=50,
            daily_image_limit_per_channel=25,
        )

    # --- Invalid monthly_song_limit ---

    def test_monthly_song_limit_negative(self) -> None:
        """Negative monthly_song_limit should fail."""
        with pytest.raises(ValidationError) as exc_info:
            validate_plan_limits(
                monthly_song_limit=-1,
                monthly_image_limit=None,
                daily_song_limit_per_channel=7,
                daily_image_limit_per_channel=7,
            )
        assert exc_info.value.details is not None
        assert "monthly_song_limit" in exc_info.value.details

    def test_monthly_song_limit_exceeds_max(self) -> None:
        """monthly_song_limit > 100,000 should fail."""
        with pytest.raises(ValidationError) as exc_info:
            validate_plan_limits(
                monthly_song_limit=100_001,
                monthly_image_limit=None,
                daily_song_limit_per_channel=7,
                daily_image_limit_per_channel=7,
            )
        assert exc_info.value.details is not None
        assert "monthly_song_limit" in exc_info.value.details

    # --- Invalid monthly_image_limit ---

    def test_monthly_image_limit_negative(self) -> None:
        """Negative monthly_image_limit should fail."""
        with pytest.raises(ValidationError) as exc_info:
            validate_plan_limits(
                monthly_song_limit=None,
                monthly_image_limit=-1,
                daily_song_limit_per_channel=7,
                daily_image_limit_per_channel=7,
            )
        assert exc_info.value.details is not None
        assert "monthly_image_limit" in exc_info.value.details

    def test_monthly_image_limit_exceeds_max(self) -> None:
        """monthly_image_limit > 100,000 should fail."""
        with pytest.raises(ValidationError) as exc_info:
            validate_plan_limits(
                monthly_song_limit=None,
                monthly_image_limit=100_001,
                daily_song_limit_per_channel=7,
                daily_image_limit_per_channel=7,
            )
        assert exc_info.value.details is not None
        assert "monthly_image_limit" in exc_info.value.details

    # --- Invalid daily_song_limit_per_channel ---

    def test_daily_song_limit_zero(self) -> None:
        """daily_song_limit_per_channel = 0 should fail (minimum is 1)."""
        with pytest.raises(ValidationError) as exc_info:
            validate_plan_limits(
                monthly_song_limit=None,
                monthly_image_limit=None,
                daily_song_limit_per_channel=0,
                daily_image_limit_per_channel=7,
            )
        assert exc_info.value.details is not None
        assert "daily_song_limit_per_channel" in exc_info.value.details

    def test_daily_song_limit_exceeds_max(self) -> None:
        """daily_song_limit_per_channel > 1,000 should fail."""
        with pytest.raises(ValidationError) as exc_info:
            validate_plan_limits(
                monthly_song_limit=None,
                monthly_image_limit=None,
                daily_song_limit_per_channel=1_001,
                daily_image_limit_per_channel=7,
            )
        assert exc_info.value.details is not None
        assert "daily_song_limit_per_channel" in exc_info.value.details

    # --- Invalid daily_image_limit_per_channel ---

    def test_daily_image_limit_zero(self) -> None:
        """daily_image_limit_per_channel = 0 should fail (minimum is 1)."""
        with pytest.raises(ValidationError) as exc_info:
            validate_plan_limits(
                monthly_song_limit=None,
                monthly_image_limit=None,
                daily_song_limit_per_channel=7,
                daily_image_limit_per_channel=0,
            )
        assert exc_info.value.details is not None
        assert "daily_image_limit_per_channel" in exc_info.value.details

    def test_daily_image_limit_exceeds_max(self) -> None:
        """daily_image_limit_per_channel > 1,000 should fail."""
        with pytest.raises(ValidationError) as exc_info:
            validate_plan_limits(
                monthly_song_limit=None,
                monthly_image_limit=None,
                daily_song_limit_per_channel=7,
                daily_image_limit_per_channel=1_001,
            )
        assert exc_info.value.details is not None
        assert "daily_image_limit_per_channel" in exc_info.value.details

    # --- Multiple errors ---

    def test_multiple_invalid_fields_reports_all(self) -> None:
        """All invalid fields should be reported in a single ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_plan_limits(
                monthly_song_limit=-5,
                monthly_image_limit=200_000,
                daily_song_limit_per_channel=0,
                daily_image_limit_per_channel=2_000,
            )
        details = exc_info.value.details
        assert details is not None
        assert "monthly_song_limit" in details
        assert "monthly_image_limit" in details
        assert "daily_song_limit_per_channel" in details
        assert "daily_image_limit_per_channel" in details
