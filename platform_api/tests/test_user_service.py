"""Unit tests for UserService.

Tests user listing, retrieval, update, suspension, reactivation,
and soft-deletion using in-memory fakes for the repository and auth service.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.models.domain import User
from platform_api.models.enums import UserRole, UserStatus
from platform_api.services.user_service import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    UserService,
)


# ---------------------------------------------------------------------------
# Fakes / In-memory implementations
# ---------------------------------------------------------------------------


class FakeUserRepository:
    """In-memory user repository for testing."""

    def __init__(self, users: list[User] | None = None) -> None:
        self._users: dict[UUID, User] = {}
        if users:
            for u in users:
                self._users[u.id] = u

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._users.get(user_id)

    async def update(self, user_id: UUID, **fields) -> User | None:
        user = self._users.get(user_id)
        if user is None:
            return None
        for key, val in fields.items():
            if hasattr(user, key):
                setattr(user, key, val)
        user.updated_at = datetime.now(timezone.utc)
        return user

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        status: str | None = None,
        plan_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[User], int]:
        users = list(self._users.values())
        if status is not None:
            users = [u for u in users if u.status.value == status]
        if date_from is not None:
            users = [u for u in users if u.created_at >= date_from]
        if date_to is not None:
            users = [u for u in users if u.created_at <= date_to]
        total = len(users)
        start = (page - 1) * page_size
        end = start + page_size
        return users[start:end], total

    async def soft_delete(self, user_id: UUID) -> bool:
        user = self._users.get(user_id)
        if user is None or user.status == UserStatus.DELETED:
            return False
        user.status = UserStatus.DELETED
        user.deleted_at = datetime.now(timezone.utc)
        return True

    async def suspend(self, user_id: UUID, reason: str) -> bool:
        user = self._users.get(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            return False
        user.status = UserStatus.SUSPENDED
        user.suspension_reason = reason
        return True

    async def reactivate(self, user_id: UUID) -> bool:
        user = self._users.get(user_id)
        if user is None or user.status != UserStatus.SUSPENDED:
            return False
        user.status = UserStatus.ACTIVE
        user.suspension_reason = None
        return True


class FakeAuthService:
    """In-memory auth service that records token revocations."""

    def __init__(self) -> None:
        self.revoked_user_ids: list[str] = []

    async def revoke_tokens(self, user_id: str) -> None:
        self.revoked_user_ids.append(user_id)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user(
    user_id: UUID | None = None,
    email: str = "test@example.com",
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    return User(
        id=user_id or uuid4(),
        email=email,
        password_hash="hashed",
        display_name="Test User",
        role=UserRole.USER,
        status=status,
        created_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
    )


@pytest.fixture
def user_repo() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def auth_service() -> FakeAuthService:
    return FakeAuthService()


@pytest.fixture
def service(user_repo: FakeUserRepository, auth_service: FakeAuthService) -> UserService:
    return UserService(user_repo=user_repo, auth_service=auth_service)


# ---------------------------------------------------------------------------
# Tests: get_users
# ---------------------------------------------------------------------------


class TestGetUsers:
    """Tests for UserService.get_users."""

    async def test_returns_paginated_users(self, service: UserService, user_repo: FakeUserRepository) -> None:
        users = [_make_user(email=f"user{i}@test.com") for i in range(30)]
        user_repo._users = {u.id: u for u in users}

        result, total = await service.get_users(page=1, page_size=10)

        assert len(result) == 10
        assert total == 30

    async def test_default_page_size(self, service: UserService, user_repo: FakeUserRepository) -> None:
        users = [_make_user(email=f"user{i}@test.com") for i in range(30)]
        user_repo._users = {u.id: u for u in users}

        result, total = await service.get_users(page=1)

        assert len(result) == DEFAULT_PAGE_SIZE
        assert total == 30

    async def test_page_size_exceeds_max_raises_validation_error(self, service: UserService) -> None:
        with pytest.raises(ValidationError, match="must not exceed"):
            await service.get_users(page=1, page_size=MAX_PAGE_SIZE + 1)

    async def test_page_size_zero_raises_validation_error(self, service: UserService) -> None:
        with pytest.raises(ValidationError, match="at least 1"):
            await service.get_users(page=1, page_size=0)

    async def test_page_zero_raises_validation_error(self, service: UserService) -> None:
        with pytest.raises(ValidationError, match="at least 1"):
            await service.get_users(page=0, page_size=10)

    async def test_filters_by_status(self, service: UserService, user_repo: FakeUserRepository) -> None:
        active_user = _make_user(email="active@test.com", status=UserStatus.ACTIVE)
        suspended_user = _make_user(email="suspended@test.com", status=UserStatus.SUSPENDED)
        user_repo._users = {active_user.id: active_user, suspended_user.id: suspended_user}

        result, total = await service.get_users(status="active")

        assert total == 1
        assert result[0].email == "active@test.com"

    async def test_empty_result(self, service: UserService) -> None:
        result, total = await service.get_users()

        assert result == []
        assert total == 0


# ---------------------------------------------------------------------------
# Tests: get_user
# ---------------------------------------------------------------------------


class TestGetUser:
    """Tests for UserService.get_user."""

    async def test_returns_user_when_found(self, service: UserService, user_repo: FakeUserRepository) -> None:
        user = _make_user()
        user_repo._users[user.id] = user

        result = await service.get_user(user.id)

        assert result.id == user.id
        assert result.email == user.email

    async def test_raises_not_found_for_missing_user(self, service: UserService) -> None:
        with pytest.raises(NotFoundError, match="not found"):
            await service.get_user(uuid4())


# ---------------------------------------------------------------------------
# Tests: update_user
# ---------------------------------------------------------------------------


class TestUpdateUser:
    """Tests for UserService.update_user."""

    async def test_updates_display_name(self, service: UserService, user_repo: FakeUserRepository) -> None:
        user = _make_user()
        user_repo._users[user.id] = user

        result = await service.update_user(user.id, display_name="New Name")

        assert result.display_name == "New Name"

    async def test_ignores_disallowed_fields(self, service: UserService, user_repo: FakeUserRepository) -> None:
        user = _make_user()
        user_repo._users[user.id] = user

        # status is not in _ALLOWED_UPDATE_FIELDS, so only display_name is applied
        result = await service.update_user(user.id, display_name="Updated", status="deleted")

        assert result.display_name == "Updated"
        assert result.status == UserStatus.ACTIVE  # unchanged

    async def test_raises_validation_error_for_no_valid_fields(self, service: UserService, user_repo: FakeUserRepository) -> None:
        user = _make_user()
        user_repo._users[user.id] = user

        with pytest.raises(ValidationError, match="No valid fields"):
            await service.update_user(user.id, status="deleted")

    async def test_raises_not_found_for_missing_user(self, service: UserService) -> None:
        with pytest.raises(NotFoundError, match="not found"):
            await service.update_user(uuid4(), display_name="X")


# ---------------------------------------------------------------------------
# Tests: suspend_user
# ---------------------------------------------------------------------------


class TestSuspendUser:
    """Tests for UserService.suspend_user."""

    async def test_suspends_active_user(
        self, service: UserService, user_repo: FakeUserRepository, auth_service: FakeAuthService
    ) -> None:
        user = _make_user()
        user_repo._users[user.id] = user

        result = await service.suspend_user(user.id, reason="Policy violation")

        assert result.status == UserStatus.SUSPENDED
        assert result.suspension_reason == "Policy violation"
        assert str(user.id) in auth_service.revoked_user_ids

    async def test_raises_not_found_for_missing_user(self, service: UserService) -> None:
        with pytest.raises(NotFoundError, match="not found"):
            await service.suspend_user(uuid4(), reason="Test")

    async def test_raises_validation_for_already_suspended(
        self, service: UserService, user_repo: FakeUserRepository
    ) -> None:
        user = _make_user(status=UserStatus.SUSPENDED)
        user_repo._users[user.id] = user

        with pytest.raises(ValidationError, match="Cannot suspend"):
            await service.suspend_user(user.id, reason="Again")

    async def test_raises_validation_for_empty_reason(
        self, service: UserService, user_repo: FakeUserRepository
    ) -> None:
        user = _make_user()
        user_repo._users[user.id] = user

        with pytest.raises(ValidationError, match="reason is required"):
            await service.suspend_user(user.id, reason="")


# ---------------------------------------------------------------------------
# Tests: reactivate_user
# ---------------------------------------------------------------------------


class TestReactivateUser:
    """Tests for UserService.reactivate_user."""

    async def test_reactivates_suspended_user(self, service: UserService, user_repo: FakeUserRepository) -> None:
        user = _make_user(status=UserStatus.SUSPENDED)
        user.suspension_reason = "Old reason"
        user_repo._users[user.id] = user

        result = await service.reactivate_user(user.id)

        assert result.status == UserStatus.ACTIVE
        assert result.suspension_reason is None

    async def test_raises_not_found_for_missing_user(self, service: UserService) -> None:
        with pytest.raises(NotFoundError, match="not found"):
            await service.reactivate_user(uuid4())

    async def test_raises_validation_for_active_user(
        self, service: UserService, user_repo: FakeUserRepository
    ) -> None:
        user = _make_user(status=UserStatus.ACTIVE)
        user_repo._users[user.id] = user

        with pytest.raises(ValidationError, match="Cannot reactivate"):
            await service.reactivate_user(user.id)


# ---------------------------------------------------------------------------
# Tests: delete_user
# ---------------------------------------------------------------------------


class TestDeleteUser:
    """Tests for UserService.delete_user."""

    async def test_soft_deletes_user_and_revokes_tokens(
        self, service: UserService, user_repo: FakeUserRepository, auth_service: FakeAuthService
    ) -> None:
        user = _make_user()
        user_repo._users[user.id] = user

        await service.delete_user(user.id)

        assert user.status == UserStatus.DELETED
        assert user.deleted_at is not None
        assert str(user.id) in auth_service.revoked_user_ids

    async def test_raises_not_found_for_missing_user(self, service: UserService) -> None:
        with pytest.raises(NotFoundError, match="not found"):
            await service.delete_user(uuid4())

    async def test_raises_validation_for_already_deleted_user(
        self, service: UserService, user_repo: FakeUserRepository
    ) -> None:
        user = _make_user(status=UserStatus.DELETED)
        user_repo._users[user.id] = user

        with pytest.raises(ValidationError, match="Cannot delete"):
            await service.delete_user(user.id)
