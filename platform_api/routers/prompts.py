"""Music prompts router endpoints (Admin-only).

Provides CRUD for song descriptions and song structures used internally
by the Platform API to drive LLM-based lyric generation. All endpoints
require Admin role.

Requirements: 9.1, 9.2, 9.3
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.services.prompt_service import PromptService

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/prompts", tags=["prompts"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class DescriptionResponse(BaseModel):
    """Public representation of a song description."""

    id: str
    name: str
    content: str
    match_key: str | None = None
    created_at: datetime
    updated_at: datetime


class CreateDescriptionRequest(BaseModel):
    """Request body for creating a new song description."""

    name: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=5000)
    match_key: str | None = None


class UpdateDescriptionRequest(BaseModel):
    """Request body for updating an existing song description."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    match_key: str | None = None


class StructureResponse(BaseModel):
    """Public representation of a song structure."""

    id: str
    name: str
    content: str
    match_key: str | None = None
    created_at: datetime
    updated_at: datetime


class CreateStructureRequest(BaseModel):
    """Request body for creating a new song structure."""

    name: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=5000)
    match_key: str | None = None


class UpdateStructureRequest(BaseModel):
    """Request body for updating an existing song structure."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    match_key: str | None = None


# ---------------------------------------------------------------------------
# Dependency injection placeholders
# ---------------------------------------------------------------------------


async def _get_prompt_service() -> PromptService:
    """Placeholder dependency for PromptService — override in tests or dependencies.py."""
    raise NotImplementedError(
        "PromptService dependency not configured. Wire via app.dependency_overrides."
    )


# Type aliases for dependency injection
PromptServiceDep = Annotated[PromptService, Depends(_get_prompt_service)]
AdminUserDep = Annotated[AuthContext, Depends(require_admin)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _description_to_response(desc) -> DescriptionResponse:
    """Convert a MusicDescription domain object to the response model."""
    return DescriptionResponse(
        id=str(desc.id),
        name=desc.name,
        content=desc.content,
        match_key=desc.match_key,
        created_at=desc.created_at,
        updated_at=desc.updated_at,
    )


def _structure_to_response(struct) -> StructureResponse:
    """Convert a MusicStructure domain object to the response model."""
    return StructureResponse(
        id=str(struct.id),
        name=struct.name,
        content=struct.content,
        match_key=struct.match_key,
        created_at=struct.created_at,
        updated_at=struct.updated_at,
    )


# ---------------------------------------------------------------------------
# Description Endpoints (Admin-only)
# ---------------------------------------------------------------------------


@router.get(
    "/descriptions",
    response_model=list[DescriptionResponse],
    status_code=200,
    summary="List all song descriptions (Admin)",
)
async def list_descriptions(
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> list[DescriptionResponse]:
    """Return all song descriptions ordered by name ascending.

    Requirement 9.1: Admin manages song descriptions.
    """
    descriptions = await prompt_service.list_descriptions()
    return [_description_to_response(d) for d in descriptions]


@router.post(
    "/descriptions",
    response_model=DescriptionResponse,
    status_code=201,
    summary="Create a song description (Admin)",
)
async def create_description(
    request: CreateDescriptionRequest,
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> DescriptionResponse:
    """Create a new song description.

    Requirement 9.1: Admin creates song description with name (1-100 chars,
    unique), content (1-5000 chars), optional match_key.
    """
    desc = await prompt_service.create_description(
        name=request.name,
        content=request.content,
        match_key=request.match_key,
    )
    return _description_to_response(desc)


@router.put(
    "/descriptions/{description_id}",
    response_model=DescriptionResponse,
    status_code=200,
    summary="Update a song description (Admin)",
)
async def update_description(
    description_id: UUID,
    request: UpdateDescriptionRequest,
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> DescriptionResponse:
    """Update an existing song description.

    Requirement 9.3: Admin updates descriptions; persist changed fields
    and return the updated record.
    """
    # Build update dict from provided fields
    fields: dict = {}
    if request.name is not None:
        fields["name"] = request.name
    if request.content is not None:
        fields["content"] = request.content
    # match_key can be explicitly set to None to clear it
    if "match_key" in request.model_fields_set:
        fields["match_key"] = request.match_key

    desc = await prompt_service.update_description(description_id, **fields)
    return _description_to_response(desc)


@router.delete(
    "/descriptions/{description_id}",
    status_code=200,
    summary="Delete a song description (Admin)",
)
async def delete_description(
    description_id: UUID,
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> dict[str, str]:
    """Delete a song description.

    Requirement 9.3: Admin deletes descriptions; removes it and
    dissociates from any match key pairings.
    """
    await prompt_service.delete_description(description_id)
    return {"message": f"Description {description_id} has been deleted."}


# ---------------------------------------------------------------------------
# Structure Endpoints (Admin-only)
# ---------------------------------------------------------------------------


@router.get(
    "/structures",
    response_model=list[StructureResponse],
    status_code=200,
    summary="List all song structures (Admin)",
)
async def list_structures(
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> list[StructureResponse]:
    """Return all song structures ordered by name ascending.

    Requirement 9.2: Admin manages song structures.
    """
    structures = await prompt_service.list_structures()
    return [_structure_to_response(s) for s in structures]


@router.post(
    "/structures",
    response_model=StructureResponse,
    status_code=201,
    summary="Create a song structure (Admin)",
)
async def create_structure(
    request: CreateStructureRequest,
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> StructureResponse:
    """Create a new song structure.

    Requirement 9.2: Admin creates song structure with name (1-100 chars,
    unique), content (1-5000 chars), optional match_key.
    """
    struct = await prompt_service.create_structure(
        name=request.name,
        content=request.content,
        match_key=request.match_key,
    )
    return _structure_to_response(struct)


@router.put(
    "/structures/{structure_id}",
    response_model=StructureResponse,
    status_code=200,
    summary="Update a song structure (Admin)",
)
async def update_structure(
    structure_id: UUID,
    request: UpdateStructureRequest,
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> StructureResponse:
    """Update an existing song structure.

    Requirement 9.3: Admin updates structures; persist changed fields
    and return the updated record.
    """
    # Build update dict from provided fields
    fields: dict = {}
    if request.name is not None:
        fields["name"] = request.name
    if request.content is not None:
        fields["content"] = request.content
    # match_key can be explicitly set to None to clear it
    if "match_key" in request.model_fields_set:
        fields["match_key"] = request.match_key

    struct = await prompt_service.update_structure(structure_id, **fields)
    return _structure_to_response(struct)


@router.delete(
    "/structures/{structure_id}",
    status_code=200,
    summary="Delete a song structure (Admin)",
)
async def delete_structure(
    structure_id: UUID,
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> dict[str, str]:
    """Delete a song structure.

    Requirement 9.3: Admin deletes structures; removes it and
    dissociates from any match key pairings.
    """
    await prompt_service.delete_structure(structure_id)
    return {"message": f"Structure {structure_id} has been deleted."}


# ---------------------------------------------------------------------------
# Public endpoint (no admin required) — used by onboarding wizard
# ---------------------------------------------------------------------------


class PublicDescriptionResponse(BaseModel):
    """Public description response (for onboarding dropdown)."""

    id: str
    name: str
    match_key: str | None = None


@router.get(
    "/descriptions/public",
    response_model=list[PublicDescriptionResponse],
    status_code=200,
    summary="List music descriptions (public, for onboarding)",
)
async def list_descriptions_public() -> list[PublicDescriptionResponse]:
    """List all music descriptions without requiring admin role.

    Used by the onboarding channel wizard genre dropdown.
    """
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    rows = await pool.fetch(
        "SELECT id, name, match_key FROM music_descriptions ORDER BY name"
    )
    return [
        PublicDescriptionResponse(
            id=str(r["id"]),
            name=r["name"],
            match_key=r.get("match_key"),
        )
        for r in rows
    ]
