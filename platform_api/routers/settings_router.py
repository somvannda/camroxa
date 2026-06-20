"""Settings management router endpoints.

Provides merged user settings retrieval and partial patch updates for
authenticated users. Sensitive keys are excluded from responses.

Requirements: 14.1, 14.2, 14.4
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.services.settings_service import SettingsService

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# Dependency Stubs
# ---------------------------------------------------------------------------


async def _get_settings_service() -> SettingsService:
    """Placeholder dependency for SettingsService — override in tests or dependencies.py."""
    raise NotImplementedError(
        "SettingsService dependency not configured. Wire via app.dependency_overrides."
    )


# Type aliases for dependency injection
SettingsServiceDep = Annotated[SettingsService, Depends(_get_settings_service)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=dict[str, Any],
    status_code=200,
    summary="Get merged application settings",
)
async def get_settings(
    ctx: CurrentUserDep,
    settings_service: SettingsServiceDep,
) -> dict[str, Any]:
    """Return merged application settings for the authenticated user.

    Settings are merged with user-stored values taking precedence over system
    defaults. Sensitive keys (containing 'secret', 'password', 'token', 'key',
    'api_key') are excluded from the response.

    Requirement 14.1: Return merged settings within 2 seconds.
    Requirement 14.4: Exclude sensitive settings from responses.
    """
    return await settings_service.get_merged_settings(
        user_id=ctx.user_id,
        include_sensitive=False,
    )


@router.patch(
    "",
    response_model=dict[str, Any],
    status_code=200,
    summary="Patch application settings",
)
async def patch_settings(
    ctx: CurrentUserDep,
    settings_service: SettingsServiceDep,
    patch: dict[str, Any] = Body(
        ...,
        description="A dict of 1-50 key-value pairs to update.",
        examples=[{"theme": "dark", "language": "en", "notifications_enabled": True}],
    ),
) -> dict[str, Any]:
    """Apply a partial settings update for the authenticated user.

    Accepts a JSON object with 1 to 50 key-value pairs. The patch is applied
    atomically — if any value is invalid, the entire patch is rejected.
    Returns the full merged settings after the patch is applied (sensitive
    keys excluded).

    Requirement 14.2: Persist changed keys and return full merged settings.
    Requirement 14.4: Exclude sensitive settings from responses.
    """
    return await settings_service.patch_settings(
        user_id=ctx.user_id,
        patch=patch,
    )
