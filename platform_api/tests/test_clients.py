"""Unit tests for external HTTP clients — error classification and timeout handling."""

from __future__ import annotations

import pytest
import httpx

from platform_api.clients.suno_client import _classify_error as suno_classify
from platform_api.clients.fal_client import _classify_error as fal_classify
from platform_api.clients.slai_client import _classify_error as slai_classify
from platform_api.clients.llm_client import _classify_error as llm_classify
from platform_api.exceptions import ExternalServiceError


# ---------------------------------------------------------------------------
# Shared error classification tests (same logic across all providers)
# ---------------------------------------------------------------------------


class TestErrorClassification:
    """Test that error classification correctly identifies retryable vs permanent errors."""

    @pytest.mark.parametrize("classify_fn,provider", [
        (suno_classify, "suno"),
        (fal_classify, "fal"),
        (slai_classify, "slai"),
        (llm_classify, "llm"),
    ])
    def test_timeout_is_retryable(self, classify_fn, provider):
        exc = httpx.ReadTimeout("read timed out")
        result = classify_fn(exc, context="test")
        assert isinstance(result, ExternalServiceError)
        assert result.is_retryable is True
        assert result.details["provider"] == provider
        assert result.details["reason"] == "timeout"

    @pytest.mark.parametrize("classify_fn,provider", [
        (suno_classify, "suno"),
        (fal_classify, "fal"),
        (slai_classify, "slai"),
        (llm_classify, "llm"),
    ])
    def test_connect_timeout_is_retryable(self, classify_fn, provider):
        exc = httpx.ConnectTimeout("connect timed out")
        result = classify_fn(exc, context="test")
        assert isinstance(result, ExternalServiceError)
        assert result.is_retryable is True

    @pytest.mark.parametrize("classify_fn,provider", [
        (suno_classify, "suno"),
        (fal_classify, "fal"),
        (slai_classify, "slai"),
        (llm_classify, "llm"),
    ])
    def test_429_rate_limit_is_retryable(self, classify_fn, provider):
        request = httpx.Request("POST", "https://example.com/api")
        response = httpx.Response(429, request=request, text="rate limited")
        exc = httpx.HTTPStatusError("rate limited", request=request, response=response)
        result = classify_fn(exc, context="test")
        assert isinstance(result, ExternalServiceError)
        assert result.is_retryable is True
        assert result.details["status_code"] == 429

    @pytest.mark.parametrize("status_code", [500, 502, 503, 504])
    @pytest.mark.parametrize("classify_fn,provider", [
        (suno_classify, "suno"),
        (fal_classify, "fal"),
        (slai_classify, "slai"),
        (llm_classify, "llm"),
    ])
    def test_5xx_is_retryable(self, classify_fn, provider, status_code):
        request = httpx.Request("POST", "https://example.com/api")
        response = httpx.Response(status_code, request=request, text="server error")
        exc = httpx.HTTPStatusError("server error", request=request, response=response)
        result = classify_fn(exc, context="test")
        assert isinstance(result, ExternalServiceError)
        assert result.is_retryable is True
        assert result.details["status_code"] == status_code

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
    @pytest.mark.parametrize("classify_fn,provider", [
        (suno_classify, "suno"),
        (fal_classify, "fal"),
        (slai_classify, "slai"),
        (llm_classify, "llm"),
    ])
    def test_4xx_not_429_is_permanent(self, classify_fn, provider, status_code):
        request = httpx.Request("POST", "https://example.com/api")
        response = httpx.Response(status_code, request=request, text="client error")
        exc = httpx.HTTPStatusError("client error", request=request, response=response)
        result = classify_fn(exc, context="test")
        assert isinstance(result, ExternalServiceError)
        assert result.is_retryable is False
        assert result.details["status_code"] == status_code

    @pytest.mark.parametrize("classify_fn,provider", [
        (suno_classify, "suno"),
        (fal_classify, "fal"),
        (slai_classify, "slai"),
        (llm_classify, "llm"),
    ])
    def test_connection_error_is_retryable(self, classify_fn, provider):
        exc = httpx.ConnectError("connection refused")
        result = classify_fn(exc, context="test")
        assert isinstance(result, ExternalServiceError)
        assert result.is_retryable is True
        assert result.details["reason"] == "connection_error"


# ---------------------------------------------------------------------------
# Client instantiation tests
# ---------------------------------------------------------------------------


class TestClientInstantiation:
    """Test that clients can be instantiated with settings."""

    def _make_settings(self):
        """Create a minimal Settings object for testing."""
        from platform_api.config import Settings
        return Settings(
            suno_api_key="test-suno-key",
            suno_api_base_url="https://suno.example.com",
            suno_callback_base_url="https://callback.example.com",
            fal_api_key="test-fal-key",
            fal_api_base_url="https://fal.example.com",
            slai_api_key="test-slai-key",
            slai_api_base_url="https://slai.example.com",
            deepseek_api_key="test-deepseek-key",
            deepseek_api_base_url="https://deepseek.example.com",
        )

    def test_suno_client_init(self):
        from platform_api.clients.suno_client import SunoClient
        settings = self._make_settings()
        client = SunoClient(settings)
        assert client._base_url == "https://suno.example.com"
        assert client._api_key == "test-suno-key"
        # Default suno_timeout_seconds is 30
        assert client._timeout.read == 30.0

    def test_fal_client_init(self):
        from platform_api.clients.fal_client import FalClient
        settings = self._make_settings()
        client = FalClient(settings)
        assert client._base_url == "https://fal.example.com"
        assert client._api_key == "test-fal-key"
        # Default image_timeout_seconds is 60
        assert client._timeout.read == 60.0

    def test_slai_client_init(self):
        from platform_api.clients.slai_client import SlaiClient
        settings = self._make_settings()
        client = SlaiClient(settings)
        assert client._base_url == "https://slai.example.com"
        assert client._api_key == "test-slai-key"
        # Default image_timeout_seconds is 60
        assert client._timeout.read == 60.0

    def test_llm_client_init(self):
        from platform_api.clients.llm_client import LlmClient
        settings = self._make_settings()
        client = LlmClient(settings)
        assert client._base_url == "https://deepseek.example.com"
        assert client._api_key == "test-deepseek-key"
        # Default llm_timeout_seconds is 30
        assert client._timeout.read == 30.0


# ---------------------------------------------------------------------------
# ExternalServiceError attribute test
# ---------------------------------------------------------------------------


class TestExternalServiceError:
    """Test the updated ExternalServiceError with is_retryable flag."""

    def test_default_not_retryable(self):
        err = ExternalServiceError("something failed")
        assert err.is_retryable is False
        assert err.status_code == 502

    def test_retryable_flag(self):
        err = ExternalServiceError("timeout", is_retryable=True)
        assert err.is_retryable is True

    def test_details_preserved(self):
        err = ExternalServiceError(
            "test",
            is_retryable=True,
            details={"provider": "suno", "status_code": 503},
        )
        assert err.details == {"provider": "suno", "status_code": 503}
