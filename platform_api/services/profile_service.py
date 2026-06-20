"""Channel profile management service.

Provides profile creation with plan-based limit enforcement, update, deletion
with batch dissociation, and ordered listing.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID, uuid4

from platform_api.exceptions import DuplicateError, NotFoundError, ValidationError
from platform_api.models.domain import ChannelProfile, License, Plan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Profile limits by plan type
# ---------------------------------------------------------------------------

# Base profile allowance per plan type (name -> limit).
# These map to the plan's profile_allowance field in the database, but we
# define defaults here for the case where the plan record isn't found.
_DEFAULT_PROFILE_LIMITS: dict[str, int] = {
    "lifetime": 5,
    "monthly": 3,
    "yearly": 4,
}

# If the user has no license at all, allow 1 profile.
_NO_LICENSE_LIMIT: int = 1

# Maximum profiles any user can have (even with purchased expansion slots).
_MAX_PROFILE_LIMIT: int = 20

# Maximum profile name length (requirement 8.2).
_MAX_NAME_LENGTH: int = 100


# ---------------------------------------------------------------------------
# Dependency Protocols
# ---------------------------------------------------------------------------


class ProfileRepositoryPort(Protocol):
    """Protocol for the profile repository dependency."""

    async def create(self, profile: ChannelProfile) -> ChannelProfile: ...
    async def get_by_id(self, profile_id: UUID) -> ChannelProfile | None: ...
    async def get_by_user_and_name(
        self, user_id: UUID, name: str
    ) -> ChannelProfile | None: ...
    async def update(
        self, profile_id: UUID, user_id: UUID, **fields: Any
    ) -> ChannelProfile | None: ...
    async def delete(self, profile_id: UUID, user_id: UUID) -> bool: ...
    async def list_for_user(self, user_id: UUID) -> list[ChannelProfile]: ...
    async def count_for_user(self, user_id: UUID) -> int: ...


class LicenseRepositoryPort(Protocol):
    """Protocol for the license repository dependency (plan limit lookup)."""

    async def get_active_for_user(self, user_id: UUID) -> License | None: ...


class PlanRepositoryPort(Protocol):
    """Protocol for the plan repository dependency (profile allowance)."""

    async def get_by_id(self, plan_id: UUID) -> Plan | None: ...


# ---------------------------------------------------------------------------
# Profile Service
# ---------------------------------------------------------------------------


class ProfileService:
    """Application service for channel profile management.

    Handles creation with plan limit enforcement, uniqueness validation,
    update, deletion, and listing.

    Args:
        profile_repo: Repository for profile persistence operations.
        license_repo: Repository for looking up the user's active license.
        plan_repo: Repository for looking up plan details (profile_allowance).
    """

    def __init__(
        self,
        profile_repo: ProfileRepositoryPort,
        license_repo: LicenseRepositoryPort,
        plan_repo: PlanRepositoryPort,
    ) -> None:
        self._profile_repo = profile_repo
        self._license_repo = license_repo
        self._plan_repo = plan_repo

    # -----------------------------------------------------------------------
    # Profile limit resolution
    # -----------------------------------------------------------------------

    async def _get_profile_limit(self, user_id: UUID) -> int:
        """Determine the maximum number of profiles allowed for a user.

        Resolution order:
        1. Look up the user's active license.
        2. If an active license exists, fetch the associated plan's
           profile_allowance field.
        3. If no plan record or no license, fall back to defaults.
        4. Cap at _MAX_PROFILE_LIMIT.

        Returns:
            The maximum profile count allowed for the user.
        """
        license_obj = await self._license_repo.get_active_for_user(user_id)
        if license_obj is None:
            return _NO_LICENSE_LIMIT

        plan = await self._plan_repo.get_by_id(license_obj.plan_id)
        if plan is None:
            # Shouldn't happen, but fallback
            return _NO_LICENSE_LIMIT

        # Use the plan's configured profile_allowance
        limit = plan.profile_allowance
        if limit <= 0:
            # Fallback to defaults by plan name
            limit = _DEFAULT_PROFILE_LIMITS.get(plan.name, _NO_LICENSE_LIMIT)

        return min(limit, _MAX_PROFILE_LIMIT)

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def create_profile(
        self, user_id: UUID, name: str, **config: Any
    ) -> ChannelProfile:
        """Create a new channel profile for a user.

        Validates:
        - Profile name is not empty and does not exceed 100 characters.
        - Profile name is unique per user.
        - User has not exceeded their plan's profile limit.

        Args:
            user_id: The UUID of the owning user.
            name: The profile name (unique per user, max 100 chars).
            **config: Optional profile configuration fields (folder_name,
                run_prefix, logo_path, video_template_id, reel_template_id,
                output_resolution, image_config, youtube_config).

        Returns:
            The newly created ChannelProfile.

        Raises:
            ValidationError: If name is invalid or profile limit is exceeded.
            DuplicateError: If a profile with the same name already exists
                for this user.
        """
        # Validate name
        if not name or not name.strip():
            raise ValidationError(
                "Profile name is required.",
                details={"name": name},
            )

        name = name.strip()
        if len(name) > _MAX_NAME_LENGTH:
            raise ValidationError(
                f"Profile name must not exceed {_MAX_NAME_LENGTH} characters.",
                details={"name_length": len(name), "max": _MAX_NAME_LENGTH},
            )

        # Check uniqueness
        existing = await self._profile_repo.get_by_user_and_name(user_id, name)
        if existing is not None:
            raise DuplicateError(
                f"A profile named '{name}' already exists.",
                details={"name": name, "user_id": str(user_id)},
            )

        # Check plan limit
        current_count = await self._profile_repo.count_for_user(user_id)
        max_allowed = await self._get_profile_limit(user_id)

        if current_count >= max_allowed:
            raise ValidationError(
                "Profile limit exceeded.",
                details={
                    "current_count": current_count,
                    "max_allowed": max_allowed,
                    "upgrade_path": "Purchase additional profile slots",
                    "error_code": "profile-limit-exceeded",
                },
            )

        # Build the profile domain object
        profile = ChannelProfile(
            id=uuid4(),
            user_id=user_id,
            name=name,
            folder_name=config.get("folder_name"),
            run_prefix=config.get("run_prefix"),
            logo_path=config.get("logo_path"),
            video_template_id=config.get("video_template_id"),
            reel_template_id=config.get("reel_template_id"),
            output_resolution=config.get("output_resolution", "1920x1080"),
            image_config=config.get("image_config", {}),
            youtube_config=config.get("youtube_config", {}),
        )

        created = await self._profile_repo.create(profile)
        logger.info(
            "Created profile '%s' (id=%s) for user %s.", name, created.id, user_id
        )
        return created

    async def update_profile(
        self, user_id: UUID, profile_id: UUID, **fields: Any
    ) -> ChannelProfile:
        """Update a channel profile belonging to the user.

        Validates that the profile exists and belongs to the given user.
        If the name is being changed, validates uniqueness of the new name.

        Args:
            user_id: The UUID of the owning user.
            profile_id: The UUID of the profile to update.
            **fields: Column names and new values.

        Returns:
            The updated ChannelProfile.

        Raises:
            NotFoundError: If the profile does not exist or belongs to
                another user.
            ValidationError: If the new name exceeds 100 characters.
            DuplicateError: If the new name conflicts with another profile.
        """
        # Validate name if it's being updated
        new_name = fields.get("name")
        if new_name is not None:
            new_name = new_name.strip() if isinstance(new_name, str) else new_name
            if not new_name:
                raise ValidationError(
                    "Profile name is required.",
                    details={"name": new_name},
                )
            if len(new_name) > _MAX_NAME_LENGTH:
                raise ValidationError(
                    f"Profile name must not exceed {_MAX_NAME_LENGTH} characters.",
                    details={"name_length": len(new_name), "max": _MAX_NAME_LENGTH},
                )

            # Check uniqueness of new name (excluding current profile)
            existing = await self._profile_repo.get_by_user_and_name(
                user_id, new_name
            )
            if existing is not None and existing.id != profile_id:
                raise DuplicateError(
                    f"A profile named '{new_name}' already exists.",
                    details={"name": new_name, "user_id": str(user_id)},
                )
            fields["name"] = new_name

        updated = await self._profile_repo.update(profile_id, user_id, **fields)
        if updated is None:
            raise NotFoundError(
                f"Profile {profile_id} not found.",
                details={"profile_id": str(profile_id), "user_id": str(user_id)},
            )

        logger.info("Updated profile %s for user %s.", profile_id, user_id)
        return updated

    async def delete_profile(self, user_id: UUID, profile_id: UUID) -> None:
        """Delete a channel profile belonging to the user.

        Removes the profile record. In-progress batches referencing this
        profile continue using the configuration captured at batch creation.
        The batch table references profiles via UUID foreign keys — setting
        those to NULL (or leaving them as-is with ON DELETE SET NULL) handles
        dissociation at the DB level.

        Args:
            user_id: The UUID of the owning user.
            profile_id: The UUID of the profile to delete.

        Raises:
            NotFoundError: If the profile does not exist or belongs to
                another user.
        """
        deleted = await self._profile_repo.delete(profile_id, user_id)
        if not deleted:
            raise NotFoundError(
                f"Profile {profile_id} not found.",
                details={"profile_id": str(profile_id), "user_id": str(user_id)},
            )

        logger.info("Deleted profile %s for user %s.", profile_id, user_id)

    async def list_profiles(self, user_id: UUID) -> list[ChannelProfile]:
        """List all profiles for a user, ordered by name ascending.

        Args:
            user_id: The UUID of the user.

        Returns:
            List of ChannelProfile domain objects, ordered by name ASC.
        """
        return await self._profile_repo.list_for_user(user_id)
