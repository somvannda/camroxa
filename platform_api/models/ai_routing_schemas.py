"""Pydantic request/response schemas for AI Model Routing.

These schemas handle HTTP-layer validation and serialization for
the AI routing admin endpoints (GET/PUT assignments, GET providers).

Requirements: 6.1, 6.2, 6.3
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Provider name validation
# ---------------------------------------------------------------------------

_PROVIDER_PATTERN = r"^(deepseek|openai|fal|slai|cala|suno)$"


# ---------------------------------------------------------------------------
# Core Models
# ---------------------------------------------------------------------------


class OperationAssignment(BaseModel):
    """A single operation's provider assignment."""

    provider: str = Field(pattern=_PROVIDER_PATTERN)
    sub_model: str | None = None
    is_active: bool = True


class SubModelDetail(BaseModel):
    """A sub-model with its cost tier annotation."""

    name: str
    cost_tier: str = ""  # "$" = cheapest, "$$" = moderate, "$$$" = premium


class ProviderOption(BaseModel):
    """A provider available for a service type, with its sub-model options."""

    provider: str
    sub_models: list[str]
    sub_models_detail: list[SubModelDetail] = Field(default_factory=list)


class SaveAssignmentsRequest(BaseModel):
    """Request to save all assignments (PUT /admin/ai-routing)."""

    assignments: dict[str, OperationAssignment]
    text_fallback_chain: list[OperationAssignment] | None = None
    image_fallback_chain: list[OperationAssignment] | None = None


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------


class AssignmentResponse(BaseModel):
    """Full assignments grouped by service type (GET /admin/ai-routing)."""

    text_generation: dict[str, OperationAssignment]
    image_generation: dict[str, OperationAssignment]
    music_generation: dict[str, OperationAssignment]
    text_fallback_chain: list[OperationAssignment] = Field(default_factory=list)
    image_fallback_chain: list[OperationAssignment] = Field(default_factory=list)


class ProvidersResponse(BaseModel):
    """Available providers per service type (GET /admin/ai-routing/providers)."""

    text_generation: list[ProviderOption]
    image_generation: list[ProviderOption]
    music_generation: list[ProviderOption]
