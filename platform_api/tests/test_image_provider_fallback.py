"""Tests for SLAI-first image provider retry behavior."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from platform_api.exceptions import ExternalServiceError
from platform_api.ports.generation_port import ImageRequest
from platform_api.services.slai_image_config_service import SlaiImageProviderConfig
from platform_api.tests.test_generation_service import (
    FakeCreditService,
    FakePricingRepo,
    FakeTaskRepo,
    _make_service,
)


@pytest.mark.asyncio
async def test_submit_image_outcome_retries_slai_before_fallback() -> None:
    service = _make_service(
        credit_service=FakeCreditService(),
        pricing_repo=FakePricingRepo(),
        task_repo=FakeTaskRepo(),
    )
    calls: list[str] = []

    async def fake_generate(request: ImageRequest, width: int, height: int) -> bytes:
        calls.append(request.provider)
        if request.provider == "slai":
            raise ExternalServiceError("SLAI error 429", is_retryable=True)
        return b"png"

    service._generate_image_for_provider = fake_generate  # type: ignore[method-assign]

    test_config = SlaiImageProviderConfig(
        min_interval_seconds=0.0,
        max_concurrent=8,
        provider_retries=3,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
        fallback_provider_retries=1,
    )

    with patch(
        "platform_api.services.slai_image_config_service.get_cached_slai_image_provider_config",
        return_value=test_config,
    ):
        outcome = await service.submit_image_outcome(
            "user-1",
            ImageRequest(
                prompt="test prompt",
                provider="slai",
                model_id="slai/gpt-image-2",
                resolution="1920x1080",
            ),
            provider_chain=[("slai", "slai/gpt-image-2"), ("fal", "flux-pro")],
            skip_pricing=True,
        )

    assert outcome.provider == "fal"
    assert calls == ["slai", "slai", "slai", "fal"]
