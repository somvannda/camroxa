"""AI Routing service — registry constants and routing resolution.

Defines service types, operations, provider capabilities, and the core
routing logic that maps operations to AI providers based on stored
assignments in system_settings.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 4.1, 4.2, 4.3, 4.4, 3.3, 3.4
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from platform_api.ai.types import IMAGE_PROVIDERS, TEXT_LLM_PROVIDERS, is_suno_lyric_routing
from platform_api.exceptions import NoAvailableKeysError, ValidationError
from platform_api.ports.key_pool_service_port import KeyPoolServicePort
from platform_api.services.settings_service import SettingsRepositoryPort

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Service Type & Operation Enums
# ---------------------------------------------------------------------------


from platform_api.ai.registry import PROVIDER_SUB_MODELS, SUB_MODEL_COST_TIERS
from platform_api.ai.types import (
    DEFAULT_PROVIDER,
    DEFAULT_SUB_MODEL,
    OPERATION_SERVICE_TYPE,
    PROVIDER_CAPABILITIES,
    Operation,
    ServiceType,
)


# ---------------------------------------------------------------------------
# Routing Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoutingResult:
    """Result of resolving an operation to a specific provider.

    Attributes:
        provider: Provider identifier, e.g. "deepseek", "openai", "fal".
        sub_model: Optional sub-model, e.g. "gpt-4o-mini", "flux-pro", None.
        service_type: The service type string, e.g. "text_generation".
    """

    provider: str
    sub_model: str | None
    service_type: str


# ---------------------------------------------------------------------------
# Settings key for stored assignments
# ---------------------------------------------------------------------------

_ASSIGNMENTS_KEY = "ai_routing_assignments"
_TEXT_FALLBACK_CHAIN_KEY = "ai_routing_text_fallback_chain"
_IMAGE_FALLBACK_CHAIN_KEY = "ai_routing_image_fallback_chain"

# Used when no custom fallback chain is stored. Primary assignment is tried first,
# then each entry below (deduped) on retryable provider failures.
DEFAULT_TEXT_FALLBACK_CHAIN: tuple[dict[str, str | None | bool], ...] = (
    {"provider": "slai", "sub_model": "xiaomi/mimo-v2.5-pro", "is_active": True},
    {"provider": "deepseek", "sub_model": "deepseek-chat", "is_active": True},
    {"provider": "openai", "sub_model": "gpt-4o-mini", "is_active": True},
)

DEFAULT_IMAGE_FALLBACK_CHAIN: tuple[dict[str, str | None | bool], ...] = (
    {"provider": "slai", "sub_model": "slai/gpt-image-2", "is_active": True},
    {"provider": "fal", "sub_model": "flux-pro", "is_active": True},
    {"provider": "openai", "sub_model": "gpt-image-1", "is_active": True},
)


def _routing_entry_active(item: dict[str, Any]) -> bool:
    """Return True when a routing/fallback entry should participate in resolution."""
    value = item.get("is_active", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "0", "no", "off"}
    return bool(value)


# ---------------------------------------------------------------------------
# AI Routing Service
# ---------------------------------------------------------------------------


class AIRoutingService:
    """Resolves operations to AI providers based on stored assignments.

    Reads assignments from system_settings, validates provider capabilities,
    checks the key pool for active keys, and returns a RoutingResult.

    Requirements: 4.1, 4.2, 4.3, 4.4, 3.3, 3.4
    """

    def __init__(
        self,
        settings_repo: SettingsRepositoryPort,
        key_pool_service: KeyPoolServicePort,
    ) -> None:
        self._settings_repo = settings_repo
        self._key_pool = key_pool_service

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    async def resolve(self, operation: str) -> RoutingResult:
        """Resolve an operation to its assigned provider and sub-model.

        Falls back to the default provider if no assignment exists or if
        the stored assignment's provider no longer supports the service type.
        Raises NoAvailableKeysError (503) if the resolved provider has no
        active keys in the Key Pool.

        Args:
            operation: The operation string (must be a valid Operation enum value).

        Returns:
            A RoutingResult with provider, sub_model, and service_type.

        Raises:
            ValueError: If operation is not a valid Operation enum member.
            NoAvailableKeysError: If the resolved provider has no active keys.
        """
        op = Operation(operation)
        service_type = OPERATION_SERVICE_TYPE[op]

        # Load assignments from system_settings
        assignments = await self._load_assignments()
        assignment = assignments.get(operation)

        if assignment:
            provider = assignment["provider"]
            sub_model = assignment.get("sub_model") or DEFAULT_SUB_MODEL.get(provider)
        else:
            # Use default
            provider = DEFAULT_PROVIDER[service_type]
            sub_model = DEFAULT_SUB_MODEL.get(provider)

        # Validate provider still supports this service type
        if service_type not in PROVIDER_CAPABILITIES.get(provider, frozenset()):
            provider = DEFAULT_PROVIDER[service_type]
            sub_model = DEFAULT_SUB_MODEL.get(provider)

        # Check Key Pool has active keys
        pool_status = await self._key_pool.get_pool_status(provider)
        active_keys = pool_status.get("active_keys", 0)

        if active_keys <= 0:
            # Build status_counts from pool_status for the error
            status_counts: dict[str, int] = {
                k: v
                for k, v in pool_status.items()
                if k.endswith("_keys") and isinstance(v, int)
            }
            raise NoAvailableKeysError(provider, status_counts)

        return RoutingResult(
            provider=provider,
            sub_model=sub_model,
            service_type=service_type,
        )

    async def resolve_text_chain(self, operation: str) -> list[RoutingResult]:
        """Resolve primary assignment plus configured text fallback providers.

        Order: operation primary (if text-capable) → stored fallback chain → defaults.
        Only includes providers with active keys in the key pool.
        """
        try:
            primary = await self.resolve(operation)
        except NoAvailableKeysError:
            primary = None
        if primary is None or primary.provider not in TEXT_LLM_PROVIDERS:
            provider = DEFAULT_PROVIDER[ServiceType.TEXT_GENERATION]
            sub_model = DEFAULT_SUB_MODEL.get(provider)
            primary = RoutingResult(
                provider=provider,
                sub_model=sub_model,
                service_type=ServiceType.TEXT_GENERATION.value,
            )

        assignments = await self._load_assignments()
        stored = assignments.get(operation)
        primary_active = (
            _routing_entry_active(stored) if isinstance(stored, dict) else True
        )

        chain: list[RoutingResult] = []
        seen: set[tuple[str, str | None]] = set()

        def _append(provider: str, sub_model: str | None) -> None:
            if provider not in TEXT_LLM_PROVIDERS:
                return
            if provider == "suno" and not is_suno_lyric_routing(
                provider=provider, operation=operation
            ):
                return
            key = (provider, sub_model)
            if key in seen:
                return
            seen.add(key)
            chain.append(
                RoutingResult(
                    provider=provider,
                    sub_model=sub_model,
                    service_type=ServiceType.TEXT_GENERATION.value,
                )
            )

        if primary_active:
            _append(primary.provider, primary.sub_model)
        for item in await self.get_text_fallback_chain():
            if not _routing_entry_active(item):
                continue
            _append(item["provider"], item.get("sub_model"))

        filtered: list[RoutingResult] = []
        for item in chain:
            pool_status = await self._key_pool.get_pool_status(item.provider)
            if pool_status.get("active_keys", 0) > 0:
                filtered.append(item)
        if not filtered:
            raise NoAvailableKeysError(
                primary.provider,
                {"reason": "no_text_providers_with_active_keys"},
            )
        return filtered

    async def get_text_fallback_chain(self) -> list[dict[str, str | None]]:
        """Return the configured global text fallback chain."""
        raw = await self._settings_repo.get_system_setting(_TEXT_FALLBACK_CHAIN_KEY)
        if raw is None:
            return [dict(item) for item in DEFAULT_TEXT_FALLBACK_CHAIN]
        if isinstance(raw, str):
            parsed = json.loads(raw)
        else:
            parsed = raw
        if not isinstance(parsed, list):
            return [dict(item) for item in DEFAULT_TEXT_FALLBACK_CHAIN]
        normalized: list[dict[str, str | None]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            provider = str(item.get("provider") or "").strip()
            if provider not in TEXT_LLM_PROVIDERS:
                continue
            sub_model = item.get("sub_model")
            normalized.append(
                {
                    "provider": provider,
                    "sub_model": str(sub_model).strip() if sub_model else None,
                    "is_active": _routing_entry_active(item),
                }
            )
        return normalized or [dict(item) for item in DEFAULT_TEXT_FALLBACK_CHAIN]

    async def get_image_fallback_chain(self) -> list[dict[str, str | None]]:
        """Return the configured global image fallback chain."""
        raw = await self._settings_repo.get_system_setting(_IMAGE_FALLBACK_CHAIN_KEY)
        if raw is None:
            return [dict(item) for item in DEFAULT_IMAGE_FALLBACK_CHAIN]
        if isinstance(raw, str):
            parsed = json.loads(raw)
        else:
            parsed = raw
        if not isinstance(parsed, list):
            return [dict(item) for item in DEFAULT_IMAGE_FALLBACK_CHAIN]
        normalized: list[dict[str, str | None]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            provider = str(item.get("provider") or "").strip()
            if provider not in IMAGE_PROVIDERS:
                continue
            sub_model = item.get("sub_model")
            normalized.append(
                {
                    "provider": provider,
                    "sub_model": str(sub_model).strip() if sub_model else None,
                    "is_active": _routing_entry_active(item),
                }
            )
        return normalized or [dict(item) for item in DEFAULT_IMAGE_FALLBACK_CHAIN]

    async def resolve_image_chain(self, operation: str) -> list[RoutingResult]:
        """Resolve primary assignment plus configured image fallback providers."""
        try:
            primary = await self.resolve(operation)
        except NoAvailableKeysError:
            primary = None
        if primary is None or primary.provider not in IMAGE_PROVIDERS:
            provider = DEFAULT_PROVIDER[ServiceType.IMAGE_GENERATION]
            sub_model = DEFAULT_SUB_MODEL.get(provider)
            primary = RoutingResult(
                provider=provider,
                sub_model=sub_model,
                service_type=ServiceType.IMAGE_GENERATION.value,
            )

        assignments = await self._load_assignments()
        stored = assignments.get(operation)
        primary_active = (
            _routing_entry_active(stored) if isinstance(stored, dict) else True
        )

        chain: list[RoutingResult] = []
        seen: set[tuple[str, str | None]] = set()

        def _append(provider: str, sub_model: str | None) -> None:
            if provider not in IMAGE_PROVIDERS:
                return
            key = (provider, sub_model)
            if key in seen:
                return
            seen.add(key)
            chain.append(
                RoutingResult(
                    provider=provider,
                    sub_model=sub_model,
                    service_type=ServiceType.IMAGE_GENERATION.value,
                )
            )

        if primary_active:
            _append(primary.provider, primary.sub_model)
        for item in await self.get_image_fallback_chain():
            if not _routing_entry_active(item):
                continue
            _append(item["provider"], item.get("sub_model"))

        filtered: list[RoutingResult] = []
        for item in chain:
            pool_status = await self._key_pool.get_pool_status(item.provider)
            if pool_status.get("active_keys", 0) > 0:
                filtered.append(item)
        if not filtered:
            raise NoAvailableKeysError(
                primary.provider,
                {"reason": "no_image_providers_with_active_keys"},
            )
        return filtered

    async def audit_configuration(
        self,
        pricing_entries: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Validate assignments against registry capabilities and credit pricing."""
        from platform_api.ai.capability_catalog import audit_routing_configuration

        assignments = await self._load_assignments()
        text_fallback = await self.get_text_fallback_chain()
        image_fallback = await self.get_image_fallback_chain()
        active_providers: set[str] = set()
        for provider in PROVIDER_CAPABILITIES:
            pool_status = await self._key_pool.get_pool_status(provider)
            if pool_status.get("active_keys", 0) > 0:
                active_providers.add(provider)
        return audit_routing_configuration(
            assignments=assignments,
            text_fallback_chain=text_fallback,
            image_fallback_chain=image_fallback,
            pricing_entries=pricing_entries,
            active_key_providers=active_providers,
        )

    async def save_text_fallback_chain(
        self,
        chain: list[dict[str, Any]],
    ) -> None:
        """Persist the global text fallback provider priority list."""
        normalized: list[dict[str, str | None]] = []
        for index, item in enumerate(chain):
            provider = str(item.get("provider") or "").strip()
            if not provider:
                raise ValidationError(
                    f"Missing provider for fallback entry #{index + 1}.",
                    details={"index": index},
                )
            if provider not in TEXT_LLM_PROVIDERS:
                raise ValidationError(
                    f"Provider '{provider}' cannot be used for text fallback.",
                    details={"provider": provider, "index": index},
                )
            sub_model = item.get("sub_model")
            normalized.append(
                {
                    "provider": provider,
                    "sub_model": str(sub_model).strip() if sub_model else None,
                    "is_active": _routing_entry_active(item),
                }
            )
        await self._settings_repo.upsert_system_settings(
            {_TEXT_FALLBACK_CHAIN_KEY: normalized}
        )

    async def save_image_fallback_chain(
        self,
        chain: list[dict[str, Any]],
    ) -> None:
        """Persist the global image fallback provider priority list."""
        normalized: list[dict[str, str | None]] = []
        for index, item in enumerate(chain):
            provider = str(item.get("provider") or "").strip()
            if not provider:
                raise ValidationError(
                    f"Missing provider for image fallback entry #{index + 1}.",
                    details={"index": index},
                )
            if provider not in IMAGE_PROVIDERS:
                raise ValidationError(
                    f"Provider '{provider}' cannot be used for image fallback.",
                    details={"provider": provider, "index": index},
                )
            sub_model = item.get("sub_model")
            normalized.append(
                {
                    "provider": provider,
                    "sub_model": str(sub_model).strip() if sub_model else None,
                    "is_active": _routing_entry_active(item),
                }
            )
        await self._settings_repo.upsert_system_settings(
            {_IMAGE_FALLBACK_CHAIN_KEY: normalized}
        )

    async def get_all_assignments(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Return all current assignments grouped by service type.

        For every operation in the registry, returns its current assignment
        (from stored settings) or the default assignment if none is stored.

        Returns:
            A dict keyed by service type, each containing a dict of operations
            mapped to their assignment (provider + sub_model).
            Example:
            {
                "text_generation": {
                    "channel_name": {"provider": "deepseek", "sub_model": "deepseek-chat"},
                    ...
                },
                "image_generation": { ... },
                "music_generation": { ... },
            }
        """
        assignments = await self._load_assignments()

        result: dict[str, dict[str, dict[str, Any]]] = {
            st.value: {} for st in ServiceType
        }

        for op, st in OPERATION_SERVICE_TYPE.items():
            stored = assignments.get(op.value)
            if stored:
                provider = stored["provider"]
                sub_model = stored.get("sub_model")
            else:
                provider = DEFAULT_PROVIDER[st]
                sub_model = DEFAULT_SUB_MODEL.get(provider)

            result[st.value][op.value] = {
                "provider": provider,
                "sub_model": sub_model,
                "is_active": (
                    _routing_entry_active(stored)
                    if stored
                    else True
                ),
            }

        result["text_fallback_chain"] = await self.get_text_fallback_chain()
        result["image_fallback_chain"] = await self.get_image_fallback_chain()
        return result

    async def save_assignments(self, assignments: dict[str, dict[str, Any]]) -> None:
        """Persist all assignments atomically to system_settings.

        Validates that each assignment's provider supports the operation's
        service type before persisting. Rejects the entire batch if any
        assignment is invalid.

        Args:
            assignments: A flat dict of operation → {"provider": str, "sub_model": str|None}.

        Raises:
            ValidationError: If any operation is invalid or its assigned provider
                does not support the operation's service type.
        """
        # Validate all assignments before persisting
        for operation_str, assignment in assignments.items():
            # Validate operation is known
            try:
                op = Operation(operation_str)
            except ValueError:
                raise ValidationError(
                    f"Unknown operation: '{operation_str}'.",
                    details={"operation": operation_str},
                )

            provider = assignment.get("provider")
            if not provider:
                raise ValidationError(
                    f"Missing provider for operation '{operation_str}'.",
                    details={"operation": operation_str},
                )

            # Validate provider supports the operation's service type
            service_type = OPERATION_SERVICE_TYPE[op]
            capabilities = PROVIDER_CAPABILITIES.get(provider, frozenset())
            if service_type not in capabilities:
                raise ValidationError(
                    f"Provider '{provider}' does not support service type "
                    f"'{service_type}' required by operation '{operation_str}'.",
                    details={
                        "operation": operation_str,
                        "provider": provider,
                        "service_type": service_type,
                        "provider_capabilities": [c.value for c in capabilities],
                    },
                )
            if service_type == ServiceType.TEXT_GENERATION and provider not in TEXT_LLM_PROVIDERS:
                raise ValidationError(
                    f"Provider '{provider}' cannot generate text for operation '{operation_str}'. "
                    "Use deepseek, slai, openai, or suno (lyric only).",
                    details={"operation": operation_str, "provider": provider},
                )
            if provider == "suno":
                if operation_str == Operation.MUSIC.value:
                    assignment["sub_model"] = None
                elif is_suno_lyric_routing(provider=provider, operation=operation_str):
                    from platform_api.ai.registry import get_text_model_spec

                    sub_model = assignment.get("sub_model")
                    if sub_model and get_text_model_spec("suno", sub_model) is None:
                        raise ValidationError(
                            f"Suno lyric model '{sub_model}' is not registered. Use 'lyrics'.",
                            details={
                                "operation": operation_str,
                                "provider": provider,
                                "sub_model": sub_model,
                            },
                        )
                elif service_type == ServiceType.TEXT_GENERATION:
                    raise ValidationError(
                        f"Provider 'suno' only supports the lyric operation, not '{operation_str}'.",
                        details={"operation": operation_str, "provider": provider},
                    )

        # Persist atomically
        await self._settings_repo.upsert_system_settings(
            {_ASSIGNMENTS_KEY: assignments}
        )

    async def get_available_providers(self) -> dict[str, list[dict[str, Any]]]:
        """Return providers per service type filtered by active Key Pool keys.

        Only includes providers that:
        (a) have the service type in their PROVIDER_CAPABILITIES, AND
        (b) have at least one active key in the Key Pool.

        Returns:
            A dict keyed by service type, each containing a list of provider
            dicts with "provider" and "sub_models" fields.
            Example:
            {
                "text_generation": [
                    {"provider": "deepseek", "sub_models": ["deepseek-chat", "deepseek-reasoner"]},
                    {"provider": "openai", "sub_models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]},
                ],
                ...
            }
        """
        result: dict[str, list[dict[str, Any]]] = {
            st.value: [] for st in ServiceType
        }

        for provider, capabilities in PROVIDER_CAPABILITIES.items():
            # Check if provider has active keys
            pool_status = await self._key_pool.get_pool_status(provider)
            active_keys = pool_status.get("active_keys", 0)

            if active_keys <= 0:
                continue

            # Add provider to each service type it supports
            for st in capabilities:
                sub_models_map = PROVIDER_SUB_MODELS.get(provider, {})
                sub_models = list(sub_models_map.get(st, ()))
                if st == ServiceType.MUSIC_GENERATION:
                    sub_models = []

                # Include cost tier annotations for each sub-model
                sub_models_with_tiers = [
                    {
                        "name": model,
                        "cost_tier": SUB_MODEL_COST_TIERS.get(model, ""),
                    }
                    for model in sub_models
                ]

                result[st.value].append({
                    "provider": provider,
                    "sub_models": sub_models,
                    "sub_models_detail": sub_models_with_tiers,
                })

        return result

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    async def _load_assignments(self) -> dict[str, dict[str, Any]]:
        """Load the flat operation→assignment map from system_settings.

        Returns:
            A dict mapping operation strings to assignment dicts, or an empty
            dict if no assignments have been stored yet.
        """
        raw = await self._settings_repo.get_system_setting(_ASSIGNMENTS_KEY)
        if raw is None:
            return {}
        if isinstance(raw, str):
            assignments = json.loads(raw)
        else:
            assignments = raw
        return self._sanitize_assignments(assignments)

    def _sanitize_assignments(self, assignments: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Drop invalid text assignments (e.g. Suno saved before capability fix)."""
        cleaned: dict[str, dict[str, Any]] = {}
        for operation_str, assignment in assignments.items():
            if not isinstance(assignment, dict):
                continue
            try:
                op = Operation(operation_str)
            except ValueError:
                continue
            provider = str(assignment.get("provider") or "").strip()
            if not provider:
                continue
            service_type = OPERATION_SERVICE_TYPE[op]
            if service_type == ServiceType.TEXT_GENERATION and provider not in TEXT_LLM_PROVIDERS:
                logger.warning(
                    "Removing invalid text assignment for %s: provider=%s",
                    operation_str,
                    provider,
                )
                continue
            if (
                service_type == ServiceType.TEXT_GENERATION
                and provider == "suno"
                and not is_suno_lyric_routing(
                    provider=provider, operation=operation_str
                )
            ):
                logger.warning(
                    "Removing invalid Suno text assignment for %s (lyric-only provider).",
                    operation_str,
                )
                continue
            if operation_str == Operation.MUSIC.value:
                assignment = {**assignment, "sub_model": None}
            cleaned[operation_str] = {
                **assignment,
                "is_active": _routing_entry_active(assignment),
            }
        return cleaned
