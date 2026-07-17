"""AI Routing admin router for managing operation-to-provider assignments.

Provides Admin-only endpoints for:
  - Viewing all operation assignments grouped by service type
  - Saving (full replace) all operation assignments
  - Listing available providers per service type (filtered by active keys)

All endpoints require Admin role authentication.

Requirements: 6.1, 6.2, 6.3
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.models.ai_routing_schemas import (
    AssignmentResponse,
    ProvidersResponse,
    SaveAssignmentsRequest,
)
from platform_api.services.ai_routing_service import AIRoutingService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/admin/ai-routing", tags=["ai-routing"])


# ---------------------------------------------------------------------------
# Dependency Stubs
# ---------------------------------------------------------------------------


async def _get_ai_routing_service() -> AIRoutingService:
    """Placeholder dependency for AIRoutingService — override via app.dependency_overrides."""
    raise NotImplementedError(
        "AIRoutingService dependency not configured. Wire via app.dependency_overrides."
    )


# ---------------------------------------------------------------------------
# Type aliases for dependency injection
# ---------------------------------------------------------------------------

AdminDep = Annotated[AuthContext, Depends(require_admin)]
AIRoutingServiceDep = Annotated[AIRoutingService, Depends(_get_ai_routing_service)]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=AssignmentResponse)
async def get_assignments(
    routing_service: AIRoutingServiceDep,
    _: AdminDep,
) -> dict:
    """Return all operation assignments grouped by service type."""
    return await routing_service.get_all_assignments()


@router.put("")
async def save_assignments(
    request: SaveAssignmentsRequest,
    routing_service: AIRoutingServiceDep,
    _: AdminDep,
) -> dict:
    """Persist all assignments atomically."""
    assignments_dict = {
        op: assgn.model_dump() for op, assgn in request.assignments.items()
    }
    await routing_service.save_assignments(assignments_dict)
    if request.text_fallback_chain is not None:
        await routing_service.save_text_fallback_chain(
            [item.model_dump() for item in request.text_fallback_chain]
        )
    if request.image_fallback_chain is not None:
        await routing_service.save_image_fallback_chain(
            [item.model_dump() for item in request.image_fallback_chain]
        )

    from platform_api.dependencies import get_credit_pricing_service

    pricing_service = get_credit_pricing_service()
    text_fallback = (
        [item.model_dump() for item in request.text_fallback_chain]
        if request.text_fallback_chain is not None
        else await routing_service.get_text_fallback_chain()
    )
    image_fallback = (
        [item.model_dump() for item in request.image_fallback_chain]
        if request.image_fallback_chain is not None
        else await routing_service.get_image_fallback_chain()
    )
    pricing_sync = await pricing_service.sync_from_routing_config(
        assignments=assignments_dict,
        text_fallback_chain=text_fallback,
        image_fallback_chain=image_fallback,
    )
    return {"status": "saved", "pricing_sync": pricing_sync}


@router.get("/providers", response_model=ProvidersResponse)
async def get_providers(
    routing_service: AIRoutingServiceDep,
    _: AdminDep,
) -> dict:
    """Return available providers per service type (filtered by active keys)."""
    return await routing_service.get_available_providers()


@router.post("/sync-pricing")
async def sync_routing_pricing(
    routing_service: AIRoutingServiceDep,
    _: AdminDep,
) -> dict:
    """Create draft credit pricing rows for all routing-required provider/operation pairs."""
    from platform_api.dependencies import get_credit_pricing_service

    pricing_service = get_credit_pricing_service()
    assignments_data = await routing_service.get_all_assignments()

    flat_assignments: dict[str, dict[str, Any]] = {}
    for service_type in ("text_generation", "image_generation", "music_generation"):
        flat_assignments.update(assignments_data.get(service_type, {}))

    pricing_sync = await pricing_service.sync_from_routing_config(
        assignments=flat_assignments,
        text_fallback_chain=assignments_data.get("text_fallback_chain", []),
        image_fallback_chain=assignments_data.get("image_fallback_chain", []),
    )
    return pricing_sync


@router.get("/audit")
async def get_routing_audit(
    routing_service: AIRoutingServiceDep,
    _: AdminDep,
) -> dict:
    """Validate routing assignments against capabilities and credit pricing."""
    from platform_api.dependencies import get_credit_pricing_service

    pricing_service = get_credit_pricing_service()
    pricing_entries = await pricing_service.get_all_pricing()
    return await routing_service.audit_configuration(pricing_entries)
