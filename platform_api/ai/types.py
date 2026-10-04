"""AI routing types and operation registry."""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType


class ServiceType(StrEnum):
    """Categories of AI work."""

    TEXT_GENERATION = "text_generation"
    IMAGE_GENERATION = "image_generation"
    MUSIC_GENERATION = "music_generation"


class Operation(StrEnum):
    """Specific platform operations, each belonging to one ServiceType."""

    CHANNEL_NAME = "channel_name"
    CHANNEL_DESCRIPTION = "channel_description"
    CHANNEL_KEYWORDS = "channel_keywords"
    CHANNEL_TAGS = "channel_tags"
    LYRIC = "lyric"
    TITLE = "title"
    ALBUM = "album"
    CHANNEL_LOGO = "channel_logo"
    CHANNEL_COVER = "channel_cover"
    BACKGROUND_IMAGE = "background_image"
    THUMBNAIL_IMAGE = "thumbnail_image"
    WEB_MUSIC_STYLE = "web_music_style"
    WEB_MUSIC_LYRICS = "web_music_lyrics"
    MUSIC = "music"


OPERATION_SERVICE_TYPE: MappingProxyType[Operation, ServiceType] = MappingProxyType(
    {
        Operation.CHANNEL_NAME: ServiceType.TEXT_GENERATION,
        Operation.CHANNEL_DESCRIPTION: ServiceType.TEXT_GENERATION,
        Operation.CHANNEL_KEYWORDS: ServiceType.TEXT_GENERATION,
        Operation.CHANNEL_TAGS: ServiceType.TEXT_GENERATION,
        Operation.LYRIC: ServiceType.TEXT_GENERATION,
        Operation.TITLE: ServiceType.TEXT_GENERATION,
        Operation.ALBUM: ServiceType.TEXT_GENERATION,
        Operation.WEB_MUSIC_STYLE: ServiceType.TEXT_GENERATION,
        Operation.WEB_MUSIC_LYRICS: ServiceType.TEXT_GENERATION,
        Operation.CHANNEL_LOGO: ServiceType.IMAGE_GENERATION,
        Operation.CHANNEL_COVER: ServiceType.IMAGE_GENERATION,
        Operation.BACKGROUND_IMAGE: ServiceType.IMAGE_GENERATION,
        Operation.THUMBNAIL_IMAGE: ServiceType.IMAGE_GENERATION,
        Operation.MUSIC: ServiceType.MUSIC_GENERATION,
    }
)

PROVIDER_CAPABILITIES: MappingProxyType[str, frozenset[ServiceType]] = MappingProxyType(
    {
        "deepseek": frozenset({ServiceType.TEXT_GENERATION}),
        "openai": frozenset({ServiceType.TEXT_GENERATION, ServiceType.IMAGE_GENERATION}),
        "fal": frozenset({ServiceType.IMAGE_GENERATION}),
        "slai": frozenset({ServiceType.TEXT_GENERATION, ServiceType.IMAGE_GENERATION}),
        "cala": frozenset({ServiceType.IMAGE_GENERATION}),
        "kie": frozenset({ServiceType.IMAGE_GENERATION}),
        "suno": frozenset({ServiceType.MUSIC_GENERATION, ServiceType.TEXT_GENERATION}),
        "camxora_music_api": frozenset({ServiceType.MUSIC_GENERATION}),
    }
)

# Suno text API is lyrics-only (POST /api/v1/lyrics); not for title/album/channel text.
SUNO_LYRIC_SUB_MODEL = "lyrics"
SUNO_LYRIC_ONLY_OPERATIONS: frozenset[str] = frozenset({Operation.LYRIC.value})

# Providers that can execute text LLM calls through TextProviderGateway.
TEXT_LLM_PROVIDERS: frozenset[str] = frozenset({"deepseek", "openai", "slai", "suno"})


def is_suno_lyric_routing(*, provider: str, operation: str) -> bool:
    """Return True when routing should use Suno's lyrics API instead of chat LLMs."""
    return provider == "suno" and operation in SUNO_LYRIC_ONLY_OPERATIONS

# Providers that can execute image generation through ImageProviderGateway.
IMAGE_PROVIDERS: frozenset[str] = frozenset(
    provider
    for provider, capabilities in PROVIDER_CAPABILITIES.items()
    if ServiceType.IMAGE_GENERATION in capabilities
)

DEFAULT_PROVIDER: MappingProxyType[ServiceType, str] = MappingProxyType(
    {
        ServiceType.TEXT_GENERATION: "deepseek",
        ServiceType.IMAGE_GENERATION: "fal",
        ServiceType.MUSIC_GENERATION: "suno",
    }
)

DEFAULT_SUB_MODEL: MappingProxyType[str, str] = MappingProxyType(
    {
        "deepseek": "deepseek-v4-flash",
        "fal": "flux-pro",
        "openai": "gpt-4o-mini",
        "slai": "xiaomi/mimo-v2.5-pro",
        "kie": "grok-imagine-image-2-0/text-to-image",
    }
)

TEXT_OPERATIONS: tuple[str, ...] = tuple(
    op.value
    for op, service_type in OPERATION_SERVICE_TYPE.items()
    if service_type == ServiceType.TEXT_GENERATION
)

IMAGE_OPERATIONS: tuple[str, ...] = tuple(
    op.value
    for op, service_type in OPERATION_SERVICE_TYPE.items()
    if service_type == ServiceType.IMAGE_GENERATION
)
