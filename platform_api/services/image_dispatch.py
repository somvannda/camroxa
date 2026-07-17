"""Image generation dispatch — routes to the correct provider client.

Thin compatibility layer over ``platform_api.ai.providers.image``.
"""

from __future__ import annotations

from typing import Any

from platform_api.ai.providers.image.gateway import ImageProviderGateway
from platform_api.ai.registry import FAL_MODEL_MAP, resolve_fal_api_model_id
from platform_api.exceptions import NoAvailableKeysError
from platform_api.services.ai_routing_service import RoutingResult

# Backward-compatible exports.
resolve_fal_model_id = resolve_fal_api_model_id


class _KeyPoolWrapper:
    def __init__(self, key_pool_service: Any, provider: str) -> None:
        self._key_pool_service = key_pool_service
        self._provider = provider

    async def execute(self, fn: Any) -> Any:
        api_key = await _get_key_safe(self._key_pool_service, self._provider)
        if not api_key:
            raise NoAvailableKeysError(self._provider, {})
        return await fn(api_key)


async def dispatch_image_generation(
    *,
    routing: RoutingResult,
    prompt: str,
    width: int = 512,
    height: int = 512,
    key_pool_service: Any,
    fal_client: Any | None = None,
    slai_client: Any | None = None,
    cala_client: Any | None = None,
) -> dict[str, Any]:
    """Dispatch image generation to the provider specified by routing."""
    gateway = ImageProviderGateway(
        fal_client=fal_client,
        slai_client=slai_client,
        fal_pool=_KeyPoolWrapper(key_pool_service, "fal") if fal_client else None,
        slai_pool=_KeyPoolWrapper(key_pool_service, "slai") if slai_client else None,
        openai_pool=_KeyPoolWrapper(key_pool_service, "openai"),
        key_pool_service=key_pool_service,
        cala_client=cala_client,
    )
    return await gateway.dispatch_routing(
        provider=routing.provider,
        sub_model=routing.sub_model,
        prompt=prompt,
        width=width,
        height=height,
    )


async def _get_key_safe(key_pool_service: Any, provider: str) -> str | None:
    if key_pool_service is None:
        return None
    try:
        return await key_pool_service.get_key(provider)
    except Exception:
        return None
