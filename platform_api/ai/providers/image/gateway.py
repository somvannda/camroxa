"""Image generation gateway — routes calls through provider adapters."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from platform_api.ai.providers.image.openai import request_openai_image
from platform_api.ai.registry import resolve_fal_api_model_id, resolve_image_model_id
from platform_api.exceptions import ExternalServiceError, NoAvailableKeysError

logger = logging.getLogger(__name__)

ImageProviderChain = list[tuple[str, str | None]]


class FalImageClient(Protocol):
    async def generate_image(
        self,
        *,
        prompt: str,
        model_id: str,
        width: int,
        height: int,
        num_images: int,
        extra_params: dict[str, Any] | None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        ...


class SlaiImageClient(Protocol):
    async def generate_image(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        style_strength: float,
        reference_image_base64: str | None,
        extra_params: dict[str, Any] | None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        ...


class CalaImageClient(Protocol):
    async def generate_image(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        reference_image_base64: str | None = None,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        ...


class PoolWrapper(Protocol):
    async def execute(self, fn: Any) -> Any:
        ...


class KeyPoolService(Protocol):
    async def get_key(self, provider: str) -> str:
        ...


class ImageProviderGateway:
    """Provider-aware image generation without purpose-specific logic."""

    def __init__(
        self,
        *,
        fal_client: FalImageClient | None = None,
        slai_client: SlaiImageClient | None = None,
        fal_pool: PoolWrapper | None = None,
        slai_pool: PoolWrapper | None = None,
        openai_pool: PoolWrapper | None = None,
        key_pool_service: KeyPoolService | None = None,
        cala_client: CalaImageClient | None = None,
    ) -> None:
        self._fal_client = fal_client
        self._slai_client = slai_client
        self._fal_pool = fal_pool
        self._slai_pool = slai_pool
        self._openai_pool = openai_pool
        self._key_pool_service = key_pool_service
        self._cala_client = cala_client

    async def generate_fal(
        self,
        *,
        prompt: str,
        model_id: str | None,
        width: int,
        height: int,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._fal_client is None:
            raise ExternalServiceError(
                "FAL client not available for image generation.",
                details={"provider": "fal"},
            )
        wrapper = self._require_pool(self._fal_pool, "fal")
        endpoint = resolve_fal_api_model_id(model_id)
        return await wrapper.execute(
            lambda api_key: self._fal_client.generate_image(
                prompt=prompt,
                model_id=endpoint,
                width=width,
                height=height,
                num_images=1,
                extra_params=extra_params,
                api_key=api_key,
            )
        )

    async def generate_slai(
        self,
        *,
        prompt: str,
        model_id: str | None,
        width: int,
        height: int,
        style_strength: float,
        reference_image_base64: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._slai_client is None:
            raise ExternalServiceError(
                "SLAI client not available for image generation.",
                details={"provider": "slai"},
            )
        wrapper = self._require_pool(self._slai_pool, "slai")
        canonical = resolve_image_model_id("slai", model_id) if model_id else None
        merged_extra = dict(extra_params or {})
        if canonical and "model" not in merged_extra:
            merged_extra["model"] = canonical
        return await wrapper.execute(
            lambda api_key: self._slai_client.generate_image(
                prompt=prompt,
                width=width,
                height=height,
                style_strength=style_strength,
                reference_image_base64=reference_image_base64,
                extra_params=merged_extra or None,
                api_key=api_key,
            )
        )

    async def generate_openai(
        self,
        *,
        prompt: str,
        model_id: str | None,
        width: int,
        height: int,
    ) -> dict[str, Any]:
        wrapper = self._require_pool(self._openai_pool, "openai")
        return await wrapper.execute(
            lambda api_key: request_openai_image(
                prompt=prompt,
                model=model_id or "gpt-image-1",
                width=width,
                height=height,
                api_key=api_key,
            )
        )

    async def generate_cala(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        reference_image_base64: str | None = None,
    ) -> dict[str, Any]:
        if self._cala_client is None:
            raise ExternalServiceError(
                "CALA client not available for image generation.",
                details={"provider": "cala"},
            )
        if self._key_pool_service is None:
            raise NoAvailableKeysError("cala", {})
        api_key = await self._key_pool_service.get_key("cala")
        return await self._cala_client.generate_image(
            prompt=prompt,
            width=width,
            height=height,
            reference_image_base64=reference_image_base64,
            api_key=api_key,
        )

    async def dispatch_routing(
        self,
        *,
        provider: str,
        sub_model: str | None,
        prompt: str,
        width: int,
        height: int,
        style_strength: float = 0.6,
        reference_image_base64: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Dispatch by provider name (used by image_dispatch and routers)."""
        if provider == "openai":
            return await self.generate_openai(
                prompt=prompt,
                model_id=sub_model,
                width=width,
                height=height,
            )
        if provider == "fal":
            return await self.generate_fal(
                prompt=prompt,
                model_id=sub_model,
                width=width,
                height=height,
                extra_params=extra_params,
            )
        if provider == "slai":
            return await self.generate_slai(
                prompt=prompt,
                model_id=sub_model,
                width=width,
                height=height,
                style_strength=style_strength,
                reference_image_base64=reference_image_base64,
                extra_params=extra_params,
            )
        if provider == "cala":
            return await self.generate_cala(
                prompt=prompt,
                width=width,
                height=height,
                reference_image_base64=reference_image_base64,
            )
        raise ExternalServiceError(
            f"Unsupported image provider: '{provider}'",
            details={"provider": provider, "sub_model": sub_model},
        )

    async def dispatch_with_fallback(
        self,
        *,
        provider_chain: ImageProviderChain,
        prompt: str,
        width: int,
        height: int,
        style_strength: float = 0.6,
        reference_image_base64: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str, str | None]:
        """Try image providers in order; advance on retryable failures."""
        if not provider_chain:
            raise ExternalServiceError(
                "No image providers configured for fallback chain.",
                is_retryable=False,
                details={"reason": "empty_chain"},
            )

        last_error: ExternalServiceError | None = None
        for index, (provider, sub_model) in enumerate(provider_chain):
            try:
                response = await self.dispatch_routing(
                    provider=provider,
                    sub_model=sub_model,
                    prompt=prompt,
                    width=width,
                    height=height,
                    style_strength=style_strength,
                    reference_image_base64=reference_image_base64,
                    extra_params=extra_params,
                )
                return response, provider, sub_model
            except ExternalServiceError as exc:
                last_error = exc
                if index >= len(provider_chain) - 1:
                    raise
                logger.warning(
                    "Image provider %s/%s failed (%s); trying next fallback provider.",
                    provider,
                    sub_model,
                    exc,
                )
        if last_error is not None:
            raise last_error
        raise ExternalServiceError(
            "All image providers in the fallback chain failed.",
            is_retryable=False,
            details={"providers": [p for p, _ in provider_chain]},
        )

    @staticmethod
    def _require_pool(wrapper: PoolWrapper | None, provider: str) -> PoolWrapper:
        if wrapper is None:
            raise NoAvailableKeysError(provider, {})
        return wrapper
