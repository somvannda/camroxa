"""Central registry for AI providers, models, and capabilities.

To add a new model under an existing provider, append a ``ModelSpec`` to the
provider's model map below. Purpose handlers and routers should not need changes.
"""

from __future__ import annotations

from types import MappingProxyType

from platform_api.ai.models import ModelSpec

from platform_api.ai.types import DEFAULT_PROVIDER, DEFAULT_SUB_MODEL, ServiceType

# ---------------------------------------------------------------------------
# Text model specs (provider → model id → spec)
# ---------------------------------------------------------------------------

OPENAI_TEXT_MODELS: dict[str, ModelSpec] = {
    "gpt-4o-mini": ModelSpec(
        api_id="gpt-4o-mini",
        supports_json_mode=True,
        cost_tier="~$0.0006/1K",
    ),
    "gpt-4o": ModelSpec(
        api_id="gpt-4o",
        supports_json_mode=True,
        cost_tier="~$0.01/1K",
    ),
    "gpt-4-turbo": ModelSpec(
        api_id="gpt-4-turbo",
        supports_json_mode=True,
        cost_tier="~$0.03/1K",
    ),
}

DEEPSEEK_TEXT_MODELS: dict[str, ModelSpec] = {
    # DeepSeek retired deepseek-chat / deepseek-reasoner on 2026-07-24.
    # Flash (non-thinking) replaces chat; Pro is the higher-tier sibling.
    "deepseek-v4-flash": ModelSpec(
        api_id="deepseek-v4-flash",
        aliases=("deepseek-chat",),
        supports_json_mode=True,
        extra_payload={"thinking": {"type": "disabled"}},
        cost_tier="~$0.0014/1K",
    ),
    "deepseek-v4-pro": ModelSpec(
        api_id="deepseek-v4-pro",
        aliases=("deepseek-reasoner",),
        supports_json_mode=True,
        extra_payload={"thinking": {"type": "disabled"}},
        cost_tier="~$0.0055/1K",
    ),
}

SLAI_TEXT_MODELS: dict[str, ModelSpec] = {
    "xiaomi/mimo-v2.5-pro": ModelSpec(
        api_id="xiaomi/mimo-v2.5-pro",
        aliases=("mimo-v2.5-pro",),
        supports_json_mode=False,
        extra_payload={
            "stream": True,
            "thinking": {"type": "disabled"},
        },
        # Observed SLAI usage: ~$0.0001414 / 1K tokens
        cost_tier="~$0.0001414/1K",
        request_timeout_seconds=180.0,
    ),
    "gpt-5.6-sol": ModelSpec(
        api_id="gpt-5.6-sol",
        supports_json_mode=False,
        extra_payload={
            "stream": True,
            "thinking": {"type": "disabled"},
        },
        cost_tier="~$0.0001033/1K",
        request_timeout_seconds=180.0,
    ),
    "gpt-5.6-terra": ModelSpec(
        api_id="gpt-5.6-terra",
        supports_json_mode=False,
        extra_payload={
            "stream": True,
            "thinking": {"type": "disabled"},
        },
        cost_tier="~$0.0000582/1K",
        request_timeout_seconds=180.0,
    ),
    "gpt-5.6-luna": ModelSpec(
        api_id="gpt-5.6-luna",
        supports_json_mode=False,
        extra_payload={
            "stream": True,
            "thinking": {"type": "disabled"},
        },
        cost_tier="~$0.0000307/1K",
        request_timeout_seconds=180.0,
    ),
}

SUNO_TEXT_MODELS: dict[str, ModelSpec] = {
    "lyrics": ModelSpec(
        api_id="lyrics",
        supports_json_mode=False,
        cost_tier="~0.4 credits (~$0.004)",
        request_timeout_seconds=120.0,
    ),
}

SUNO_MUSIC_MODELS: dict[str, ModelSpec] = {
    "V5": ModelSpec(api_id="V5", cost_tier="~12 Suno credits (~$0.06)"),
    "V5_5": ModelSpec(api_id="V5_5", cost_tier="~12 Suno credits (~$0.06)"),
}

OPENAI_IMAGE_MODELS: dict[str, ModelSpec] = {
    "gpt-image-1-mini": ModelSpec(api_id="gpt-image-1-mini", cost_tier="~$0.02/img"),
    "gpt-image-1": ModelSpec(api_id="gpt-image-1", cost_tier="~$0.04/img"),
    "gpt-image-1.5": ModelSpec(api_id="gpt-image-1.5", cost_tier="~$0.07/img"),
    "gpt-image-2": ModelSpec(api_id="gpt-image-2", cost_tier="~$0.19/img"),
}

FAL_IMAGE_MODELS: dict[str, ModelSpec] = {
    "flux-schnell": ModelSpec(api_id="fal-ai/flux/schnell", cost_tier="~$0.003/img"),
    "flux-dev": ModelSpec(api_id="fal-ai/flux/dev", cost_tier="~$0.025/img"),
    "flux-pro": ModelSpec(api_id="fal-ai/flux-pro/v1.1", cost_tier="~$0.05/img"),
}

SLAI_IMAGE_MODELS: dict[str, ModelSpec] = {
    # Provider charge: ~150 images / $1 ⇒ ~$0.0067 per image
    "slai/gpt-image-2": ModelSpec(api_id="slai/gpt-image-2", cost_tier="~$0.0067/img"),
}

KIE_IMAGE_MODELS: dict[str, ModelSpec] = {
    # kie.ai unified Market API: POST /api/v1/jobs/createTask, then poll
    # GET /api/v1/jobs/recordInfo?taskId=. Text-to-image only (no reference image).
    # Cost tier is a placeholder estimate — review the seeded draft pricing row
    # on the admin Credits page before approving.
    "grok-imagine-image-2-0/text-to-image": ModelSpec(
        api_id="grok-imagine-image-2-0/text-to-image",
        cost_tier="~$0.02/img",
    ),
}

TEXT_MODEL_REGISTRY: MappingProxyType[str, MappingProxyType[str, ModelSpec]] = MappingProxyType(
    {
        "openai": MappingProxyType(OPENAI_TEXT_MODELS),
        "deepseek": MappingProxyType(DEEPSEEK_TEXT_MODELS),
        "slai": MappingProxyType(SLAI_TEXT_MODELS),
        "suno": MappingProxyType(SUNO_TEXT_MODELS),
    }
)

IMAGE_MODEL_REGISTRY: MappingProxyType[str, MappingProxyType[str, ModelSpec]] = MappingProxyType(
    {
        "openai": MappingProxyType(OPENAI_IMAGE_MODELS),
        "fal": MappingProxyType(FAL_IMAGE_MODELS),
        "slai": MappingProxyType(SLAI_IMAGE_MODELS),
        "kie": MappingProxyType(KIE_IMAGE_MODELS),
    }
)

# Provider → service type → tuple of model ids (admin UI / routing validation).
PROVIDER_SUB_MODELS: MappingProxyType[str, MappingProxyType[ServiceType, tuple[str, ...]]] = (
    MappingProxyType(
        {
            "openai": MappingProxyType(
                {
                    ServiceType.TEXT_GENERATION: tuple(OPENAI_TEXT_MODELS.keys()),
                    ServiceType.IMAGE_GENERATION: tuple(OPENAI_IMAGE_MODELS.keys()),
                }
            ),
            "fal": MappingProxyType(
                {
                    ServiceType.IMAGE_GENERATION: tuple(FAL_IMAGE_MODELS.keys()),
                }
            ),
            "deepseek": MappingProxyType(
                {
                    ServiceType.TEXT_GENERATION: tuple(DEEPSEEK_TEXT_MODELS.keys()),
                }
            ),
            "slai": MappingProxyType(
                {
                    ServiceType.TEXT_GENERATION: tuple(SLAI_TEXT_MODELS.keys()),
                    ServiceType.IMAGE_GENERATION: tuple(SLAI_IMAGE_MODELS.keys()),
                }
            ),
            "kie": MappingProxyType(
                {
                    ServiceType.IMAGE_GENERATION: tuple(KIE_IMAGE_MODELS.keys()),
                }
            ),
            "cala": MappingProxyType({}),
            "suno": MappingProxyType(
                {
                    ServiceType.TEXT_GENERATION: tuple(SUNO_TEXT_MODELS.keys()),
                    ServiceType.MUSIC_GENERATION: tuple(SUNO_MUSIC_MODELS.keys()),
                }
            ),
        }
    )
)

_ALIAS_LOOKUP: dict[tuple[str, str], str] = {}


def _register_aliases() -> None:
    for provider, models in TEXT_MODEL_REGISTRY.items():
        for model_id, spec in models.items():
            _ALIAS_LOOKUP[(provider, model_id.lower())] = model_id
            _ALIAS_LOOKUP[(provider, spec.api_id.lower())] = model_id
            for alias in spec.aliases:
                _ALIAS_LOOKUP[(provider, alias.lower())] = model_id

    for provider, models in IMAGE_MODEL_REGISTRY.items():
        for model_id, spec in models.items():
            _ALIAS_LOOKUP[(provider, model_id.lower())] = model_id
            _ALIAS_LOOKUP[(provider, spec.api_id.lower())] = model_id
            for alias in spec.aliases:
                _ALIAS_LOOKUP[(provider, alias.lower())] = model_id


def _build_cost_tiers() -> MappingProxyType[str, str]:
    tiers: dict[str, str] = {}
    for models in (*TEXT_MODEL_REGISTRY.values(), *IMAGE_MODEL_REGISTRY.values()):
        for model_id, spec in models.items():
            if spec.cost_tier:
                tiers[model_id] = spec.cost_tier
    for model_id, spec in SUNO_MUSIC_MODELS.items():
        if spec.cost_tier:
            tiers[model_id] = spec.cost_tier
    return MappingProxyType(tiers)


_register_aliases()

SUB_MODEL_COST_TIERS = _build_cost_tiers()


def resolve_text_model_id(provider: str, model: str | None) -> str:
    """Normalize a text model id or alias to the canonical registry key."""
    key = str(model or "").strip()
    if not key:
        return DEFAULT_SUB_MODEL.get(provider, key)
    resolved = _ALIAS_LOOKUP.get((provider, key.lower()))
    return resolved or key


def get_text_model_spec(provider: str, model: str | None) -> ModelSpec | None:
    """Return the registry spec for a text model, if registered."""
    canonical = resolve_text_model_id(provider, model)
    provider_models = TEXT_MODEL_REGISTRY.get(provider)
    if provider_models is None:
        return None
    return provider_models.get(canonical)


def json_response_format(provider: str, model: str | None) -> dict[str, str] | None:
    """Return OpenAI-style json_object format when the model supports it."""
    spec = get_text_model_spec(provider, model)
    if spec is not None and spec.supports_json_mode:
        return {"type": "json_object"}
    if provider == "openai":
        return {"type": "json_object"}
    return None


def text_model_extra_payload(provider: str, model: str | None) -> dict:
    """Provider/model-specific chat payload fields (e.g. SLAI thinking flags)."""
    spec = get_text_model_spec(provider, model)
    if spec is None:
        return {}
    return dict(spec.extra_payload)


def resolve_text_request_timeout(
    provider: str,
    model: str | None,
    *,
    fallback: float,
    draft: bool = False,
) -> float:
    """Return HTTP read timeout for a text model (seconds)."""
    spec = get_text_model_spec(provider, model)
    if spec is not None and spec.request_timeout_seconds is not None:
        return float(spec.request_timeout_seconds)
    if draft:
        return max(float(fallback), 120.0)
    return float(fallback)


def resolve_image_model_id(provider: str, model: str | None, *, default: str = "") -> str:
    """Normalize an image model id or alias to the canonical registry key."""
    key = str(model or "").strip()
    if not key:
        return default or DEFAULT_SUB_MODEL.get(provider, key)
    resolved = _ALIAS_LOOKUP.get((provider, key.lower()))
    return resolved or key


def get_image_model_spec(provider: str, model: str | None) -> ModelSpec | None:
    """Return the registry spec for an image model, if registered."""
    canonical = resolve_image_model_id(provider, model)
    provider_models = IMAGE_MODEL_REGISTRY.get(provider)
    if provider_models is None:
        return None
    return provider_models.get(canonical)


def get_music_model_spec(provider: str, model: str | None) -> ModelSpec | None:
    """Return the registry spec for a music model, if registered."""
    if provider != "suno":
        return None
    key = str(model or "").strip()
    if not key:
        return None
    return SUNO_MUSIC_MODELS.get(key)


def resolve_fal_api_model_id(sub_model: str | None) -> str:
    """Map admin FAL sub-model names to fal.ai API endpoint ids."""
    key = str(sub_model or "").strip().lower()
    if not key:
        return FAL_IMAGE_MODELS["flux-schnell"].api_id
    if key in FAL_IMAGE_MODELS:
        return FAL_IMAGE_MODELS[key].api_id
    if key.startswith("fal-ai/"):
        return str(sub_model or "").strip()
    spec = get_image_model_spec("fal", sub_model)
    if spec is not None:
        return spec.api_id
    return FAL_IMAGE_MODELS["flux-schnell"].api_id


# Backward-compatible alias used by legacy imports.
FAL_MODEL_MAP: dict[str, str] = {
    model_id: spec.api_id for model_id, spec in FAL_IMAGE_MODELS.items()
}
