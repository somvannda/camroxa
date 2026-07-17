"""AI capability catalog and routing/pricing audit helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from platform_api.ai.registry import (
    IMAGE_MODEL_REGISTRY,
    PROVIDER_SUB_MODELS,
    TEXT_MODEL_REGISTRY,
    get_image_model_spec,
    get_text_model_spec,
)
from platform_api.ai.types import (
    IMAGE_OPERATIONS,
    IMAGE_PROVIDERS,
    OPERATION_SERVICE_TYPE,
    PROVIDER_CAPABILITIES,
    TEXT_LLM_PROVIDERS,
    TEXT_OPERATIONS,
    Operation,
    ServiceType,
    is_suno_lyric_routing,
)
from platform_api.services.pricing_keys import pricing_lookup_key


def _routing_entry_active(item: dict[str, Any]) -> bool:
    value = item.get("is_active", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "0", "no", "off"}
    return bool(value)


@dataclass(frozen=True)
class CapabilityIssue:
    severity: str  # "error" | "warning"
    code: str
    message: str
    operation: str | None = None
    provider: str | None = None
    sub_model: str | None = None
    pricing_ai_service: str | None = None
    pricing_operation_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "operation": self.operation,
            "provider": self.provider,
            "sub_model": self.sub_model,
            "pricing_ai_service": self.pricing_ai_service,
            "pricing_operation_type": self.pricing_operation_type,
        }


def pricing_operation_type(operation: str) -> str:
    """Map a routing operation to the credit_pricing.operation_type key."""
    return operation


def pricing_ai_service(provider: str, *, operation: str) -> str:
    """Map routing provider to credit_pricing.ai_service key."""
    _ = operation
    return provider


def build_capability_catalog() -> dict[str, Any]:
    """Return the registry-backed catalog of providers, models, and purposes."""
    providers: list[dict[str, Any]] = []
    for provider, capabilities in PROVIDER_CAPABILITIES.items():
        service_types = sorted(st.value for st in capabilities)
        text_models = list(PROVIDER_SUB_MODELS.get(provider, {}).get(ServiceType.TEXT_GENERATION, ()))
        image_models = list(PROVIDER_SUB_MODELS.get(provider, {}).get(ServiceType.IMAGE_GENERATION, ()))
        music_models = list(PROVIDER_SUB_MODELS.get(provider, {}).get(ServiceType.MUSIC_GENERATION, ()))
        providers.append(
            {
                "provider": provider,
                "service_types": service_types,
                "text_llm": provider in TEXT_LLM_PROVIDERS,
                "text_models": text_models,
                "image_models": image_models,
                "music_models": music_models,
                "scale_via_key_pool": provider in {"suno", "deepseek", "openai", "slai", "fal"},
                "routing_note": (
                    "Music uses Suno; users pick v5 / v5.5 in app settings. "
                    "Lyrics-only API (~2 Suno credits/job) uses model 'lyrics' on the lyric slot. "
                    "Add multiple Suno API keys in the Key Pool to distribute load across accounts."
                    if provider == "suno"
                    else None
                ),
            }
        )

    operations: list[dict[str, Any]] = []
    for op, service_type in OPERATION_SERVICE_TYPE.items():
        operations.append(
            {
                "operation": op.value,
                "service_type": service_type.value,
                "pricing_operation_type": pricing_operation_type(op.value),
            }
        )

    return {
        "providers": providers,
        "operations": operations,
        "text_llm_providers": sorted(TEXT_LLM_PROVIDERS),
        "text_operations": list(TEXT_OPERATIONS),
        "image_providers": sorted(IMAGE_PROVIDERS),
        "image_operations": list(IMAGE_OPERATIONS),
    }


def _pricing_key_set(pricing_entries: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for entry in pricing_entries:
        key = pricing_lookup_key(
            str(entry.get("ai_service") or ""),
            str(entry.get("operation_type") or ""),
            str(entry.get("sub_model") or ""),
        )
        if key[0] and key[1]:
            keys.add(key)
    return keys


def _pricing_coverage(
    pricing_entries: list[dict[str, Any]],
) -> tuple[set[tuple[str, str, str]], set[tuple[str, str, str]]]:
    """Return (all_configured_keys, draft_keys)."""
    configured: set[tuple[str, str, str]] = set()
    draft: set[tuple[str, str, str]] = set()
    for entry in pricing_entries:
        key = pricing_lookup_key(
            str(entry.get("ai_service") or ""),
            str(entry.get("operation_type") or ""),
            str(entry.get("sub_model") or ""),
        )
        if not key[0] or not key[1]:
            continue
        configured.add(key)
        if bool(entry.get("needs_review")):
            draft.add(key)
    return configured, draft


def _validate_model_registered(
    *,
    provider: str,
    sub_model: str | None,
    service_type: ServiceType,
) -> CapabilityIssue | None:
    if not sub_model:
        if service_type == ServiceType.MUSIC_GENERATION:
            return None
        models = PROVIDER_SUB_MODELS.get(provider, {}).get(service_type, ())
        if models:
            return CapabilityIssue(
                severity="warning",
                code="missing_sub_model",
                message=f"Provider '{provider}' requires a model selection for {service_type.value}.",
                provider=provider,
            )
        return None

    if service_type == ServiceType.TEXT_GENERATION:
        if get_text_model_spec(provider, sub_model) is None:
            return CapabilityIssue(
                severity="error",
                code="unknown_model",
                message=f"Text model '{sub_model}' is not registered for provider '{provider}'.",
                provider=provider,
                sub_model=sub_model,
            )
    elif service_type == ServiceType.IMAGE_GENERATION:
        if get_image_model_spec(provider, sub_model) is None:
            return CapabilityIssue(
                severity="error",
                code="unknown_model",
                message=f"Image model '{sub_model}' is not registered for provider '{provider}'.",
                provider=provider,
                sub_model=sub_model,
            )
    return None


def _check_assignment_pricing(
    *,
    operation: str,
    provider: str,
    sub_model: str | None,
    pricing_keys: set[tuple[str, str]],
    draft_pricing_keys: set[tuple[str, str]],
    label: str,
    check_capability: bool = True,
) -> list[CapabilityIssue]:
    issues: list[CapabilityIssue] = []
    try:
        op = Operation(operation)
    except ValueError:
        return [
            CapabilityIssue(
                severity="error",
                code="unknown_operation",
                message=f"Unknown operation '{operation}'.",
                operation=operation,
            )
        ]

    service_type = OPERATION_SERVICE_TYPE[op]
    if check_capability:
        capabilities = PROVIDER_CAPABILITIES.get(provider, frozenset())
        if service_type not in capabilities:
            issues.append(
                CapabilityIssue(
                    severity="error",
                    code="invalid_capability",
                    message=(
                        f"{label}: provider '{provider}' cannot perform "
                        f"'{operation}' ({service_type.value})."
                    ),
                    operation=operation,
                    provider=provider,
                    sub_model=sub_model,
                )
            )
            return issues

        if service_type == ServiceType.TEXT_GENERATION and provider not in TEXT_LLM_PROVIDERS:
            issues.append(
                CapabilityIssue(
                    severity="error",
                    code="invalid_capability",
                    message=(
                        f"{label}: '{provider}' is not a text LLM provider. "
                        "Use deepseek, slai, openai, or suno (lyric only)."
                    ),
                    operation=operation,
                    provider=provider,
                    sub_model=sub_model,
                )
            )

        if (
            provider == "suno"
            and service_type == ServiceType.TEXT_GENERATION
            and not is_suno_lyric_routing(provider=provider, operation=operation)
        ):
            issues.append(
                CapabilityIssue(
                    severity="error",
                    code="invalid_capability",
                    message=(
                        f"{label}: provider 'suno' only supports the lyric operation, "
                        f"not '{operation}'."
                    ),
                    operation=operation,
                    provider=provider,
                    sub_model=sub_model,
                )
            )
            return issues

        if service_type == ServiceType.IMAGE_GENERATION and provider not in IMAGE_PROVIDERS:
            issues.append(
                CapabilityIssue(
                    severity="error",
                    code="invalid_capability",
                    message=(
                        f"{label}: '{provider}' is not an image provider. "
                        "Use fal, slai, openai, or cala."
                    ),
                    operation=operation,
                    provider=provider,
                    sub_model=sub_model,
                )
            )

        model_issue = _validate_model_registered(
            provider=provider,
            sub_model=sub_model,
            service_type=service_type,
        )
        if model_issue is not None:
            issues.append(
                CapabilityIssue(
                    severity=model_issue.severity,
                    code=model_issue.code,
                    message=f"{label}: {model_issue.message}",
                    operation=operation,
                    provider=provider,
                    sub_model=sub_model,
                )
            )

    ai_service = pricing_ai_service(provider, operation=operation)
    op_type = pricing_operation_type(operation)
    if operation == Operation.MUSIC.value and not str(sub_model or "").strip():
        has_music_pricing = any(
            key[0] == ai_service and key[1] == op_type for key in pricing_keys
        )
        if not has_music_pricing:
            issues.append(
                CapabilityIssue(
                    severity="error",
                    code="missing_pricing",
                    message=(
                        f"{label}: no credit pricing for ai_service='{ai_service}' "
                        f"operation_type='{op_type}'. Add rows for each Suno model "
                        "(V5, V5_5) users can select."
                    ),
                    operation=operation,
                    provider=provider,
                    sub_model=sub_model,
                    pricing_ai_service=ai_service,
                    pricing_operation_type=op_type,
                )
            )
        return issues

    pricing_key = pricing_lookup_key(ai_service, op_type, sub_model)
    if pricing_key not in pricing_keys:
        model_label = str(sub_model).strip() if sub_model else "default"
        issues.append(
            CapabilityIssue(
                severity="error",
                code="missing_pricing",
                message=(
                    f"{label}: no credit pricing for ai_service='{ai_service}' "
                    f"operation_type='{op_type}' model='{model_label}'."
                ),
                operation=operation,
                provider=provider,
                sub_model=sub_model,
                pricing_ai_service=ai_service,
                pricing_operation_type=op_type,
            )
        )
    elif pricing_key in draft_pricing_keys:
        model_label = str(sub_model).strip() if sub_model else "default"
        issues.append(
            CapabilityIssue(
                severity="warning",
                code="draft_pricing",
                message=(
                    f"{label}: draft pricing for ai_service='{ai_service}' "
                    f"operation_type='{op_type}' model='{model_label}' "
                    "needs review on the Credits page."
                ),
                operation=operation,
                provider=provider,
                sub_model=sub_model,
                pricing_ai_service=ai_service,
                pricing_operation_type=op_type,
            )
        )
    return issues


def audit_routing_configuration(
    *,
    assignments: dict[str, dict[str, Any]],
    text_fallback_chain: list[dict[str, Any]],
    image_fallback_chain: list[dict[str, Any]] | None = None,
    pricing_entries: list[dict[str, Any]],
    active_key_providers: set[str] | None = None,
) -> dict[str, Any]:
    """Validate assignments against capabilities registry and pricing table."""
    pricing_keys, draft_pricing_keys = _pricing_coverage(pricing_entries)
    issues: list[CapabilityIssue] = []

    for operation, assignment in assignments.items():
        if not _routing_entry_active(assignment):
            continue
        provider = str(assignment.get("provider") or "").strip()
        sub_model = assignment.get("sub_model")
        if not provider:
            continue
        issues.extend(
            _check_assignment_pricing(
                operation=operation,
                provider=provider,
                sub_model=str(sub_model).strip() if sub_model else None,
                pricing_keys=pricing_keys,
                draft_pricing_keys=draft_pricing_keys,
                label="Primary assignment",
            )
        )

    for index, item in enumerate(text_fallback_chain):
        if not _routing_entry_active(item):
            continue
        provider = str(item.get("provider") or "").strip()
        sub_model = item.get("sub_model")
        if not provider:
            continue
        normalized_sub_model = str(sub_model).strip() if sub_model else None
        for op_index, text_operation in enumerate(TEXT_OPERATIONS):
            issues.extend(
                _check_assignment_pricing(
                    operation=text_operation,
                    provider=provider,
                    sub_model=normalized_sub_model,
                    pricing_keys=pricing_keys,
                    draft_pricing_keys=draft_pricing_keys,
                    label=f"Text fallback #{index + 1}",
                    check_capability=op_index == 0,
                )
            )

    image_fallback_chain = image_fallback_chain or []
    for index, item in enumerate(image_fallback_chain):
        if not _routing_entry_active(item):
            continue
        provider = str(item.get("provider") or "").strip()
        sub_model = item.get("sub_model")
        if not provider:
            continue
        normalized_sub_model = str(sub_model).strip() if sub_model else None
        for op_index, image_operation in enumerate(IMAGE_OPERATIONS):
            issues.extend(
                _check_assignment_pricing(
                    operation=image_operation,
                    provider=provider,
                    sub_model=normalized_sub_model,
                    pricing_keys=pricing_keys,
                    draft_pricing_keys=draft_pricing_keys,
                    label=f"Image fallback #{index + 1}",
                    check_capability=op_index == 0,
                )
            )

    if active_key_providers is not None:
        seen_providers = {
            str(a.get("provider") or "").strip()
            for a in assignments.values()
            if isinstance(a, dict)
        }
        seen_providers.update(
            str(item.get("provider") or "").strip() for item in text_fallback_chain
        )
        seen_providers.update(
            str(item.get("provider") or "").strip() for item in image_fallback_chain
        )
        for provider in sorted(p for p in seen_providers if p):
            if provider not in active_key_providers:
                issues.append(
                    CapabilityIssue(
                        severity="warning",
                        code="no_active_keys",
                        message=f"Provider '{provider}' has no active API keys in the key pool.",
                        provider=provider,
                    )
                )

    errors = [issue.to_dict() for issue in issues if issue.severity == "error"]
    warnings = [issue.to_dict() for issue in issues if issue.severity == "warning"]
    draft_count = sum(1 for issue in issues if issue.code == "draft_pricing")
    return {
        "catalog": build_capability_catalog(),
        "issues": [issue.to_dict() for issue in issues],
        "error_count": len(errors),
        "warning_count": len(warnings),
        "draft_pricing_count": draft_count,
        "ready": len(errors) == 0,
    }
