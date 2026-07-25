"""Music prompts router endpoints (Admin-only).

Provides CRUD for song descriptions, song structures, and song moods used
internally by the Platform API to drive LLM-based lyric generation. All
admin endpoints require Admin role.

Requirements: 9.1, 9.2, 9.3
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.services.prompt_service import PromptService
from platform_api.services.music_genre_utils import normalize_description_genres

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
    genres: list[str] = Field(default_factory=list)
    match_key: str | None = None
    vocal_profile: dict[str, Any] | None = None
    is_active: bool = True
    owner_label: str = "camxora"
    usage_count: int = 0
    created_at: datetime
    updated_at: datetime


class CreateDescriptionRequest(BaseModel):
    """Request body for creating a new song description."""

    name: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=5000)
    genres: list[str] = Field(default_factory=list)
    match_key: str | None = None
    vocal_profile: dict[str, Any] | None = None
    is_active: bool = True

    @field_validator("genres")
    @classmethod
    def validate_genres(cls, value: list[str]) -> list[str]:
        try:
            return normalize_description_genres(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class UpdateDescriptionRequest(BaseModel):
    """Request body for updating an existing song description."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    genres: list[str] | None = None
    match_key: str | None = None
    vocal_profile: dict[str, Any] | None = None
    is_active: bool | None = None

    @field_validator("genres")
    @classmethod
    def validate_genres(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        try:
            return normalize_description_genres(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class StructureResponse(BaseModel):
    """Public representation of a song structure."""

    id: str
    name: str
    content: str
    match_key: str | None = None
    is_active: bool = True
    owner_label: str = "camxora"
    usage_count: int = 0
    created_at: datetime
    updated_at: datetime


class CreateStructureRequest(BaseModel):
    """Request body for creating a new song structure."""

    name: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=5000)
    match_key: str | None = None
    is_active: bool = True


class UpdateStructureRequest(BaseModel):
    """Request body for updating an existing song structure."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    match_key: str | None = None
    is_active: bool | None = None


class MoodResponse(BaseModel):
    """Public representation of a song mood."""

    id: str
    name: str
    content: str
    match_key: str | None = None
    is_active: bool = True
    owner_label: str = "camxora"
    usage_count: int = 0
    created_at: datetime
    updated_at: datetime


class CreateMoodRequest(BaseModel):
    """Request body for creating a new song mood."""

    name: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=5000)
    match_key: str | None = None
    is_active: bool = True


class UpdateMoodRequest(BaseModel):
    """Request body for updating an existing song mood."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    match_key: str | None = None
    is_active: bool | None = None


class UserPromptRequest(BaseModel):
    """Request body for user-owned prompt create/update."""

    name: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=5000)


class UserDescriptionResponse(BaseModel):
    """Full user-owned description for settings editing."""

    id: str
    name: str
    content: str
    created_at: datetime
    updated_at: datetime


class UserStructureResponse(BaseModel):
    """Full user-owned structure for settings editing."""

    id: str
    name: str
    content: str
    created_at: datetime
    updated_at: datetime


class UserMoodResponse(BaseModel):
    """Full user-owned mood for settings editing."""

    id: str
    name: str
    content: str
    created_at: datetime
    updated_at: datetime


class AdminUserOwnedPromptResponse(BaseModel):
    """Admin-facing list row for user-owned prompts."""

    id: str
    user_id: str
    user_email: str
    user_display_name: str
    name: str
    content: str
    is_active: bool = True
    usage_count: int = 0
    created_at: datetime
    updated_at: datetime


class WorkspacePromptOption(BaseModel):
    """Selector option for Settings/Music — never exposes camxora content."""

    id: str
    name: str
    match_key: str | None = None
    is_owned: bool = False
    vocal_mode: str | None = None
    default_secondary_language: str | None = None


class PromptUsageByUser(BaseModel):
    user_id: str
    user_email: str
    user_display_name: str
    usage_count: int
    last_used_at: datetime | None = None


class PromptUsageByProfile(BaseModel):
    profile_id: str
    profile_name: str
    user_email: str
    user_display_name: str
    usage_count: int
    last_used_at: datetime | None = None


class PromptUsageByDay(BaseModel):
    usage_date: date
    usage_count: int


class PromptUsageResponse(BaseModel):
    prompt_id: str
    prompt_name: str
    owner_label: str
    usage_count: int
    users: list[PromptUsageByUser]
    profiles: list[PromptUsageByProfile]
    by_day: list[PromptUsageByDay]


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
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _description_to_response(desc, *, usage_count: int = 0) -> DescriptionResponse:
    """Convert a MusicDescription domain object to the response model."""
    return DescriptionResponse(
        id=str(desc.id),
        name=desc.name,
        content=desc.content,
        genres=list(desc.genres or []),
        match_key=desc.match_key,
        vocal_profile=desc.vocal_profile,
        is_active=desc.is_active,
        owner_label="camxora" if desc.user_id is None else "user",
        usage_count=usage_count,
        created_at=desc.created_at,
        updated_at=desc.updated_at,
    )


def _structure_to_response(struct, *, usage_count: int = 0) -> StructureResponse:
    """Convert a MusicStructure domain object to the response model."""
    return StructureResponse(
        id=str(struct.id),
        name=struct.name,
        content=struct.content,
        match_key=struct.match_key,
        is_active=struct.is_active,
        owner_label="camxora" if struct.user_id is None else "user",
        usage_count=usage_count,
        created_at=struct.created_at,
        updated_at=struct.updated_at,
    )


def _mood_to_response(mood, *, usage_count: int = 0) -> MoodResponse:
    """Convert a MusicMood domain object to the response model."""
    return MoodResponse(
        id=str(mood.id),
        name=mood.name,
        content=mood.content,
        match_key=mood.match_key,
        is_active=mood.is_active,
        owner_label="camxora" if mood.user_id is None else "user",
        usage_count=usage_count,
        created_at=mood.created_at,
        updated_at=mood.updated_at,
    )


def _user_description_to_response(desc) -> UserDescriptionResponse:
    return UserDescriptionResponse(
        id=str(desc.id),
        name=desc.name,
        content=desc.content,
        created_at=desc.created_at,
        updated_at=desc.updated_at,
    )


def _user_structure_to_response(struct) -> UserStructureResponse:
    return UserStructureResponse(
        id=str(struct.id),
        name=struct.name,
        content=struct.content,
        created_at=struct.created_at,
        updated_at=struct.updated_at,
    )


def _user_mood_to_response(mood) -> UserMoodResponse:
    return UserMoodResponse(
        id=str(mood.id),
        name=mood.name,
        content=mood.content,
        created_at=mood.created_at,
        updated_at=mood.updated_at,
    )


def _workspace_description_option(desc) -> WorkspacePromptOption:
    from platform_api.ai.purposes.vocal_profile import parse_vocal_profile

    profile = parse_vocal_profile(getattr(desc, "vocal_profile", None))
    return WorkspacePromptOption(
        id=str(desc.id),
        name=desc.name,
        match_key=desc.match_key,
        is_owned=desc.user_id is not None,
        vocal_mode=profile.mode if profile is not None else "monolingual",
        default_secondary_language=profile.secondary_language if profile and profile.is_bilingual else None,
    )


def _workspace_structure_option(struct) -> WorkspacePromptOption:
    return WorkspacePromptOption(
        id=str(struct.id),
        name=struct.name,
        is_owned=struct.user_id is not None,
    )


def _workspace_mood_option(mood) -> WorkspacePromptOption:
    return WorkspacePromptOption(
        id=str(mood.id),
        name=mood.name,
        is_owned=mood.user_id is not None,
    )


def _usage_users_to_response(rows: list[dict]) -> list[PromptUsageByUser]:
    return [
        PromptUsageByUser(
            user_id=str(row["user_id"]),
            user_email=str(row.get("email") or ""),
            user_display_name=str(row.get("display_name") or ""),
            usage_count=int(row.get("usage_count") or 0),
            last_used_at=row.get("last_used_at"),
        )
        for row in rows
    ]


def _usage_profiles_to_response(rows: list[dict]) -> list[PromptUsageByProfile]:
    return [
        PromptUsageByProfile(
            profile_id=str(row["profile_id"]),
            profile_name=str(row.get("profile_name") or ""),
            user_email=str(row.get("user_email") or ""),
            user_display_name=str(row.get("user_display_name") or ""),
            usage_count=int(row.get("usage_count") or 0),
            last_used_at=row.get("last_used_at"),
        )
        for row in rows
    ]


def _usage_days_to_response(rows: list[dict]) -> list[PromptUsageByDay]:
    result: list[PromptUsageByDay] = []
    for row in rows:
        usage_date = row.get("usage_date")
        if isinstance(usage_date, datetime):
            usage_date = usage_date.date()
        elif isinstance(usage_date, str):
            usage_date = date.fromisoformat(usage_date)
        if not isinstance(usage_date, date):
            continue
        result.append(
            PromptUsageByDay(
                usage_date=usage_date,
                usage_count=int(row.get("usage_count") or 0),
            )
        )
    return result


# ---------------------------------------------------------------------------
# Genre catalog (Admin autocomplete)
# ---------------------------------------------------------------------------


class GenreCatalogItemResponse(BaseModel):
    name: str
    slug: str
    category: str
    aliases: list[str] = Field(default_factory=list)


class GenreCatalogListResponse(BaseModel):
    items: list[GenreCatalogItemResponse]
    categories: list[str] = Field(default_factory=list)


@router.get(
    "/genre-catalog",
    response_model=GenreCatalogListResponse,
    status_code=200,
    summary="Search curated music genres (Admin)",
)
async def search_genre_catalog(
    ctx: AdminUserDep,
    q: str | None = None,
    category: str | None = None,
    limit: int = 30,
) -> GenreCatalogListResponse:
    del ctx
    from platform_api.dependencies import get_db_pool
    from platform_api.services.music_genre_catalog_service import MusicGenreCatalogService

    service = MusicGenreCatalogService(get_db_pool())
    items = await service.search(query=q, category=category, limit=limit)
    categories = await service.list_categories()
    return GenreCatalogListResponse(
        items=[GenreCatalogItemResponse.model_validate(item) for item in items],
        categories=categories,
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
    """Return global song descriptions ordered by name ascending."""
    descriptions = await prompt_service.list_descriptions()
    usage_counts = await prompt_service.list_description_usage_summaries()
    return [
        _description_to_response(d, usage_count=usage_counts.get(d.id, 0))
        for d in descriptions
    ]


@router.get(
    "/descriptions/user-prompts",
    response_model=list[AdminUserOwnedPromptResponse],
    status_code=200,
    summary="List all user-owned descriptions (Admin)",
)
async def list_user_owned_descriptions(
    ctx: AdminUserDep,
) -> list[AdminUserOwnedPromptResponse]:
    """Return all user-owned descriptions with owner info and usage counts."""
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    rows = await pool.fetch(
        """
        SELECT
            d.id,
            d.user_id,
            u.email AS user_email,
            u.display_name AS user_display_name,
            d.name,
            d.content,
            d.is_active,
            COALESCE(usage.usage_count, 0)::int AS usage_count,
            d.created_at,
            d.updated_at
        FROM music_descriptions d
        JOIN users u ON u.id = d.user_id
        LEFT JOIN (
            SELECT description_id, COUNT(*)::int AS usage_count
            FROM songs
            WHERE description_id IS NOT NULL
            GROUP BY description_id
        ) usage ON usage.description_id = d.id
        WHERE d.user_id IS NOT NULL
        ORDER BY d.is_active DESC, usage_count DESC, d.updated_at DESC, u.email ASC, d.name ASC
        """
    )
    return [
        AdminUserOwnedPromptResponse(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            user_email=str(row.get("user_email") or ""),
            user_display_name=str(row.get("user_display_name") or ""),
            name=str(row["name"]),
            content=str(row["content"]),
            is_active=bool(row.get("is_active", True)),
            usage_count=int(row.get("usage_count") or 0),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


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
        genres=request.genres,
        match_key=request.match_key,
        vocal_profile=request.vocal_profile,
        is_active=request.is_active,
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
    if "genres" in request.model_fields_set:
        fields["genres"] = request.genres
    # match_key can be explicitly set to None to clear it
    if "match_key" in request.model_fields_set:
        fields["match_key"] = request.match_key
    if "is_active" in request.model_fields_set:
        fields["is_active"] = request.is_active
    if "vocal_profile" in request.model_fields_set:
        fields["vocal_profile"] = request.vocal_profile

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
    """Return global song structures ordered by name ascending."""
    structures = await prompt_service.list_structures()
    usage_counts = await prompt_service.list_structure_usage_summaries()
    return [
        _structure_to_response(s, usage_count=usage_counts.get(s.id, 0))
        for s in structures
    ]


@router.get(
    "/structures/user-prompts",
    response_model=list[AdminUserOwnedPromptResponse],
    status_code=200,
    summary="List all user-owned structures (Admin)",
)
async def list_user_owned_structures(
    ctx: AdminUserDep,
) -> list[AdminUserOwnedPromptResponse]:
    """Return all user-owned structures with owner info and usage counts."""
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    rows = await pool.fetch(
        """
        SELECT
            s.id,
            s.user_id,
            u.email AS user_email,
            u.display_name AS user_display_name,
            s.name,
            s.content,
            s.is_active,
            COALESCE(usage.usage_count, 0)::int AS usage_count,
            s.created_at,
            s.updated_at
        FROM music_structures s
        JOIN users u ON u.id = s.user_id
        LEFT JOIN (
            SELECT structure_id, COUNT(*)::int AS usage_count
            FROM songs
            WHERE structure_id IS NOT NULL
            GROUP BY structure_id
        ) usage ON usage.structure_id = s.id
        WHERE s.user_id IS NOT NULL
        ORDER BY s.is_active DESC, usage_count DESC, s.updated_at DESC, u.email ASC, s.name ASC
        """
    )
    return [
        AdminUserOwnedPromptResponse(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            user_email=str(row.get("user_email") or ""),
            user_display_name=str(row.get("user_display_name") or ""),
            name=str(row["name"]),
            content=str(row["content"]),
            is_active=bool(row.get("is_active", True)),
            usage_count=int(row.get("usage_count") or 0),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


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
        is_active=request.is_active,
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
    if "is_active" in request.model_fields_set:
        fields["is_active"] = request.is_active

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
# Mood Endpoints (Admin-only)
# ---------------------------------------------------------------------------


@router.get(
    "/moods",
    response_model=list[MoodResponse],
    status_code=200,
    summary="List all song moods (Admin)",
)
async def list_moods(
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> list[MoodResponse]:
    """Return global song moods ordered by name ascending."""
    moods = await prompt_service.list_moods()
    usage_counts = await prompt_service.list_mood_usage_summaries()
    return [
        _mood_to_response(m, usage_count=usage_counts.get(m.id, 0))
        for m in moods
    ]


@router.get(
    "/moods/user-prompts",
    response_model=list[AdminUserOwnedPromptResponse],
    status_code=200,
    summary="List all user-owned moods (Admin)",
)
async def list_user_owned_moods(
    ctx: AdminUserDep,
) -> list[AdminUserOwnedPromptResponse]:
    """Return all user-owned moods with owner info and usage counts."""
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    rows = await pool.fetch(
        """
        SELECT
            m.id,
            m.user_id,
            u.email AS user_email,
            u.display_name AS user_display_name,
            m.name,
            m.content,
            m.is_active,
            COALESCE(usage.usage_count, 0)::int AS usage_count,
            m.created_at,
            m.updated_at
        FROM music_moods m
        JOIN users u ON u.id = m.user_id
        LEFT JOIN (
            SELECT mood_id, COUNT(*)::int AS usage_count
            FROM songs
            WHERE mood_id IS NOT NULL
            GROUP BY mood_id
        ) usage ON usage.mood_id = m.id
        WHERE m.user_id IS NOT NULL
        ORDER BY m.is_active DESC, usage_count DESC, m.updated_at DESC, u.email ASC, m.name ASC
        """
    )
    return [
        AdminUserOwnedPromptResponse(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            user_email=str(row.get("user_email") or ""),
            user_display_name=str(row.get("user_display_name") or ""),
            name=str(row["name"]),
            content=str(row["content"]),
            is_active=bool(row.get("is_active", True)),
            usage_count=int(row.get("usage_count") or 0),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@router.post(
    "/moods",
    response_model=MoodResponse,
    status_code=201,
    summary="Create a song mood (Admin)",
)
async def create_mood(
    request: CreateMoodRequest,
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> MoodResponse:
    """Create a new song mood.

    Admin creates song mood with name (1-100 chars, unique), content
    (1-5000 chars), optional match_key.
    """
    mood = await prompt_service.create_mood(
        name=request.name,
        content=request.content,
        match_key=request.match_key,
        is_active=request.is_active,
    )
    return _mood_to_response(mood)


@router.put(
    "/moods/{mood_id}",
    response_model=MoodResponse,
    status_code=200,
    summary="Update a song mood (Admin)",
)
async def update_mood(
    mood_id: UUID,
    request: UpdateMoodRequest,
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> MoodResponse:
    """Update an existing song mood.

    Admin updates moods; persist changed fields and return the updated record.
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
    if "is_active" in request.model_fields_set:
        fields["is_active"] = request.is_active

    mood = await prompt_service.update_mood(mood_id, **fields)
    return _mood_to_response(mood)


@router.delete(
    "/moods/{mood_id}",
    status_code=200,
    summary="Delete a song mood (Admin)",
)
async def delete_mood(
    mood_id: UUID,
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> dict[str, str]:
    """Delete a song mood.

    Admin deletes moods; removes it and dissociates from any songs.
    """
    await prompt_service.delete_mood(mood_id)
    return {"message": f"Mood {mood_id} has been deleted."}


# ---------------------------------------------------------------------------
# Usage analytics (Admin-only)
# ---------------------------------------------------------------------------


@router.get(
    "/descriptions/{description_id}/usage",
    response_model=PromptUsageResponse,
    status_code=200,
    summary="Get description usage breakdown (Admin)",
)
async def get_description_usage(
    description_id: UUID,
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> PromptUsageResponse:
    """Return how many songs used this description and by which users."""
    usage = await prompt_service.get_description_usage(description_id)
    return PromptUsageResponse(
        prompt_id=usage["prompt_id"],
        prompt_name=usage["prompt_name"],
        owner_label=usage["owner_label"],
        usage_count=usage["usage_count"],
        users=_usage_users_to_response(usage["users"]),
        profiles=_usage_profiles_to_response(usage["profiles"]),
        by_day=_usage_days_to_response(usage["by_day"]),
    )


@router.get(
    "/structures/{structure_id}/usage",
    response_model=PromptUsageResponse,
    status_code=200,
    summary="Get structure usage breakdown (Admin)",
)
async def get_structure_usage(
    structure_id: UUID,
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> PromptUsageResponse:
    """Return how many songs used this structure and by which users."""
    usage = await prompt_service.get_structure_usage(structure_id)
    return PromptUsageResponse(
        prompt_id=usage["prompt_id"],
        prompt_name=usage["prompt_name"],
        owner_label=usage["owner_label"],
        usage_count=usage["usage_count"],
        users=_usage_users_to_response(usage["users"]),
        profiles=_usage_profiles_to_response(usage["profiles"]),
        by_day=_usage_days_to_response(usage["by_day"]),
    )


@router.get(
    "/moods/{mood_id}/usage",
    response_model=PromptUsageResponse,
    status_code=200,
    summary="Get mood usage breakdown (Admin)",
)
async def get_mood_usage(
    mood_id: UUID,
    ctx: AdminUserDep,
    prompt_service: PromptServiceDep,
) -> PromptUsageResponse:
    """Return how many songs used this mood and by which users."""
    usage = await prompt_service.get_mood_usage(mood_id)
    return PromptUsageResponse(
        prompt_id=usage["prompt_id"],
        prompt_name=usage["prompt_name"],
        owner_label=usage["owner_label"],
        usage_count=usage["usage_count"],
        users=_usage_users_to_response(usage["users"]),
        profiles=_usage_profiles_to_response(usage["profiles"]),
        by_day=_usage_days_to_response(usage["by_day"]),
    )


# ---------------------------------------------------------------------------
# Workspace selectors (authenticated users)
# ---------------------------------------------------------------------------


@router.get(
    "/descriptions/workspace",
    response_model=list[WorkspacePromptOption],
    status_code=200,
    summary="List selectable descriptions for Settings/Music",
)
async def list_descriptions_workspace(
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> list[WorkspacePromptOption]:
    """Return camxora description names plus the current user's own names."""
    descriptions = await prompt_service.list_descriptions_workspace(UUID(ctx.user_id))
    return [_workspace_description_option(item) for item in descriptions]


@router.get(
    "/structures/workspace",
    response_model=list[WorkspacePromptOption],
    status_code=200,
    summary="List selectable structures for Settings/Music",
)
async def list_structures_workspace(
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> list[WorkspacePromptOption]:
    """Return camxora structure names plus the current user's own names."""
    structures = await prompt_service.list_structures_workspace(UUID(ctx.user_id))
    return [_workspace_structure_option(item) for item in structures]


@router.get(
    "/moods/workspace",
    response_model=list[WorkspacePromptOption],
    status_code=200,
    summary="List selectable moods for Settings/Music",
)
async def list_moods_workspace(
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> list[WorkspacePromptOption]:
    """Return camxora mood names plus the current user's own names."""
    moods = await prompt_service.list_moods_workspace(UUID(ctx.user_id))
    return [_workspace_mood_option(item) for item in moods]


# ---------------------------------------------------------------------------
# User-owned prompts (authenticated users)
# ---------------------------------------------------------------------------


@router.get(
    "/me/descriptions",
    response_model=list[UserDescriptionResponse],
    status_code=200,
    summary="List current user's descriptions",
)
async def list_my_descriptions(
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> list[UserDescriptionResponse]:
    """Return full content for descriptions owned by the current user."""
    descriptions = await prompt_service.list_user_descriptions(UUID(ctx.user_id))
    return [_user_description_to_response(item) for item in descriptions]


@router.post(
    "/me/descriptions",
    response_model=UserDescriptionResponse,
    status_code=201,
    summary="Create a user-owned description",
)
async def create_my_description(
    request: UserPromptRequest,
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> UserDescriptionResponse:
    """Create a description owned by the current user."""
    desc = await prompt_service.create_user_description(
        UUID(ctx.user_id),
        name=request.name,
        content=request.content,
    )
    return _user_description_to_response(desc)


@router.put(
    "/me/descriptions/{description_id}",
    response_model=UserDescriptionResponse,
    status_code=200,
    summary="Update a user-owned description",
)
async def update_my_description(
    description_id: UUID,
    request: UserPromptRequest,
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> UserDescriptionResponse:
    """Update a description owned by the current user."""
    desc = await prompt_service.update_user_description(
        description_id,
        UUID(ctx.user_id),
        name=request.name,
        content=request.content,
    )
    return _user_description_to_response(desc)


@router.delete(
    "/me/descriptions/{description_id}",
    status_code=200,
    summary="Archive a user-owned description",
)
async def delete_my_description(
    description_id: UUID,
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> dict[str, str]:
    """Archive a description owned by the current user (hidden from UI, kept for usage history)."""
    await prompt_service.delete_user_description(description_id, UUID(ctx.user_id))
    return {"message": f"Description {description_id} has been archived."}


@router.get(
    "/me/structures",
    response_model=list[UserStructureResponse],
    status_code=200,
    summary="List current user's structures",
)
async def list_my_structures(
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> list[UserStructureResponse]:
    """Return full content for structures owned by the current user."""
    structures = await prompt_service.list_user_structures(UUID(ctx.user_id))
    return [_user_structure_to_response(item) for item in structures]


@router.post(
    "/me/structures",
    response_model=UserStructureResponse,
    status_code=201,
    summary="Create a user-owned structure",
)
async def create_my_structure(
    request: UserPromptRequest,
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> UserStructureResponse:
    """Create a structure owned by the current user."""
    struct = await prompt_service.create_user_structure(
        UUID(ctx.user_id),
        name=request.name,
        content=request.content,
    )
    return _user_structure_to_response(struct)


@router.put(
    "/me/structures/{structure_id}",
    response_model=UserStructureResponse,
    status_code=200,
    summary="Update a user-owned structure",
)
async def update_my_structure(
    structure_id: UUID,
    request: UserPromptRequest,
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> UserStructureResponse:
    """Update a structure owned by the current user."""
    struct = await prompt_service.update_user_structure(
        structure_id,
        UUID(ctx.user_id),
        name=request.name,
        content=request.content,
    )
    return _user_structure_to_response(struct)


@router.delete(
    "/me/structures/{structure_id}",
    status_code=200,
    summary="Archive a user-owned structure",
)
async def delete_my_structure(
    structure_id: UUID,
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> dict[str, str]:
    """Archive a structure owned by the current user (hidden from UI, kept for usage history)."""
    await prompt_service.delete_user_structure(structure_id, UUID(ctx.user_id))
    return {"message": f"Structure {structure_id} has been archived."}


@router.get(
    "/me/moods",
    response_model=list[UserMoodResponse],
    status_code=200,
    summary="List current user's moods",
)
async def list_my_moods(
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> list[UserMoodResponse]:
    """Return full content for moods owned by the current user."""
    moods = await prompt_service.list_user_moods(UUID(ctx.user_id))
    return [_user_mood_to_response(item) for item in moods]


@router.post(
    "/me/moods",
    response_model=UserMoodResponse,
    status_code=201,
    summary="Create a user-owned mood",
)
async def create_my_mood(
    request: UserPromptRequest,
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> UserMoodResponse:
    """Create a mood owned by the current user."""
    mood = await prompt_service.create_user_mood(
        UUID(ctx.user_id),
        name=request.name,
        content=request.content,
    )
    return _user_mood_to_response(mood)


@router.put(
    "/me/moods/{mood_id}",
    response_model=UserMoodResponse,
    status_code=200,
    summary="Update a user-owned mood",
)
async def update_my_mood(
    mood_id: UUID,
    request: UserPromptRequest,
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> UserMoodResponse:
    """Update a mood owned by the current user."""
    mood = await prompt_service.update_user_mood(
        mood_id,
        UUID(ctx.user_id),
        name=request.name,
        content=request.content,
    )
    return _user_mood_to_response(mood)


@router.delete(
    "/me/moods/{mood_id}",
    status_code=200,
    summary="Archive a user-owned mood",
)
async def delete_my_mood(
    mood_id: UUID,
    ctx: CurrentUserDep,
    prompt_service: PromptServiceDep,
) -> dict[str, str]:
    """Archive a mood owned by the current user (hidden from UI, kept for usage history)."""
    await prompt_service.delete_user_mood(mood_id, UUID(ctx.user_id))
    return {"message": f"Mood {mood_id} has been archived."}


# ---------------------------------------------------------------------------
# Public endpoint (no admin required) — used by onboarding wizard
# ---------------------------------------------------------------------------


class PublicDescriptionResponse(BaseModel):
    """Public description response (for onboarding dropdown)."""

    id: str
    name: str
    match_key: str | None = None


class PublicStructureResponse(BaseModel):
    """Public structure response (for Settings selectors)."""

    id: str
    name: str


class PublicMoodResponse(BaseModel):
    """Public mood response (for Settings selectors)."""

    id: str
    name: str


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
        """
        SELECT id, name, match_key
        FROM music_descriptions
        WHERE user_id IS NULL AND is_active = TRUE
        ORDER BY name
        """
    )
    return [
        PublicDescriptionResponse(
            id=str(r["id"]),
            name=r["name"],
            match_key=r.get("match_key"),
        )
        for r in rows
    ]


@router.get(
    "/structures/public",
    response_model=list[PublicStructureResponse],
    status_code=200,
    summary="List music structures (public, names only)",
)
async def list_structures_public() -> list[PublicStructureResponse]:
    """List all music structures without requiring admin role.

    Used by the Electron Settings route to provide a safe selector-only
    surface sourced from the same Admin Portal-managed prompt tables.
    """
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    rows = await pool.fetch(
        """
        SELECT id, name
        FROM music_structures
        WHERE user_id IS NULL AND is_active = TRUE
        ORDER BY name
        """
    )
    return [
        PublicStructureResponse(
            id=str(r["id"]),
            name=r["name"],
        )
        for r in rows
    ]


@router.get(
    "/moods/public",
    response_model=list[PublicMoodResponse],
    status_code=200,
    summary="List music moods (public, names only)",
)
async def list_moods_public() -> list[PublicMoodResponse]:
    """List all music moods without requiring admin role.

    Used by the Electron Settings route to provide a safe selector-only
    surface sourced from the same Admin Portal-managed prompt tables.
    """
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    rows = await pool.fetch(
        """
        SELECT id, name
        FROM music_moods
        WHERE user_id IS NULL AND is_active = TRUE
        ORDER BY name
        """
    )
    return [
        PublicMoodResponse(
            id=str(r["id"]),
            name=r["name"],
        )
        for r in rows
    ]
