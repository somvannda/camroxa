"""Image generation provider adapters."""

from platform_api.ai.providers.image.gateway import ImageProviderGateway
from platform_api.ai.registry import FAL_MODEL_MAP, resolve_fal_api_model_id

# Backward-compatible name.
resolve_fal_model_id = resolve_fal_api_model_id

__all__ = [
    "FAL_MODEL_MAP",
    "ImageProviderGateway",
    "resolve_fal_api_model_id",
    "resolve_fal_model_id",
]
