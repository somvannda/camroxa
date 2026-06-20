"""Tests for the prompts router endpoints (platform_api.routers.prompts)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.exceptions import DuplicateError, NotFoundError, ValidationError
from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext
from platform_api.models.domain import MusicDescription, MusicStructure
from platform_api.routers.prompts import _get_prompt_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ADMIN_CONTEXT = AuthContext(user_id=str(uuid4()), email="admin@example.com", role="admin")
USER_CONTEXT = AuthContext(user_id=str(uuid4()), email="user@example.com", role="user")

NOW = datetime(2024, 1, 15, 12, 0, 0)


def _make_description(
    name: str = "Epic Rock",
    content: str = "High energy rock with driving guitars",
    match_key: str | None = None,
) -> MusicDescription:
    return MusicDescription(
        id=uuid4(),
        name=name,
        content=content,
        match_key=match_key,
        created_at=NOW,
        updated_at=NOW,
    )


def _make_structure(
    name: str = "Verse-Chorus",
    content: str = "[Verse]\n[Chorus]\n[Verse]\n[Chorus]\n[Bridge]\n[Chorus]",
    match_key: str | None = None,
) -> MusicStructure:
    return MusicStructure(
        id=uuid4(),
        name=name,
        content=content,
        match_key=match_key,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def mock_prompt_service() -> AsyncMock:
    """Create a mock prompt service."""
    service = AsyncMock()
    service.list_descriptions = AsyncMock(return_value=[])
    service.create_description = AsyncMock(side_effect=lambda **kw: _make_description(**kw))
    service.update_description = AsyncMock(side_effect=lambda desc_id, **kw: _make_description(**kw))
    service.delete_description = AsyncMock(return_value=None)
    service.list_structures = AsyncMock(return_value=[])
    service.create_structure = AsyncMock(side_effect=lambda **kw: _make_structure(**kw))
    service.update_structure = AsyncMock(side_effect=lambda struct_id, **kw: _make_structure(**kw))
    service.delete_structure = AsyncMock(return_value=None)
    return service


@pytest.fixture
def app(mock_prompt_service: AsyncMock):
    """Create a test app with admin auth and prompt service overrides."""
    from platform_api.middleware.auth import require_admin

    application = create_app()
    application.dependency_overrides[_get_prompt_service] = lambda: mock_prompt_service
    application.dependency_overrides[require_admin] = lambda: ADMIN_CONTEXT
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def non_admin_app(mock_prompt_service: AsyncMock):
    """Create a test app where the user is NOT an admin."""
    from platform_api.middleware.auth import require_admin
    from platform_api.exceptions import ForbiddenError

    application = create_app()
    application.dependency_overrides[_get_prompt_service] = lambda: mock_prompt_service

    def _reject_non_admin():
        raise ForbiddenError("You do not have permission to perform this action.")

    application.dependency_overrides[require_admin] = _reject_non_admin
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def non_admin_client(non_admin_app) -> AsyncClient:
    """Create a test client with non-admin user."""
    transport = ASGITransport(app=non_admin_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /prompts/descriptions
# ---------------------------------------------------------------------------


class TestListDescriptions:
    """Tests for GET /api/v1/prompts/descriptions."""

    async def test_list_empty(self, client: AsyncClient) -> None:
        """Empty list returns 200 with empty array."""
        response = await client.get("/api/v1/prompts/descriptions")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_returns_descriptions(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Returns all descriptions."""
        desc = _make_description()
        mock_prompt_service.list_descriptions.return_value = [desc]

        response = await client.get("/api/v1/prompts/descriptions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Epic Rock"
        assert data[0]["id"] == str(desc.id)

    async def test_non_admin_rejected(self, non_admin_client: AsyncClient) -> None:
        """Non-admin user receives 403."""
        response = await non_admin_client.get("/api/v1/prompts/descriptions")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /prompts/descriptions
# ---------------------------------------------------------------------------


class TestCreateDescription:
    """Tests for POST /api/v1/prompts/descriptions."""

    async def test_create_success(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Valid request creates a description and returns 201."""
        response = await client.post(
            "/api/v1/prompts/descriptions",
            json={
                "name": "Chill Lofi",
                "content": "Relaxed lofi hip hop with jazzy undertones",
                "match_key": "lofi_set",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Chill Lofi"
        mock_prompt_service.create_description.assert_awaited_once()

    async def test_create_without_match_key(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """match_key is optional."""
        response = await client.post(
            "/api/v1/prompts/descriptions",
            json={
                "name": "Pop Anthem",
                "content": "Upbeat pop with catchy hooks",
            },
        )
        assert response.status_code == 201

    async def test_create_duplicate_name(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Duplicate name returns 409."""
        mock_prompt_service.create_description.side_effect = DuplicateError(
            "A description named 'Epic Rock' already exists."
        )
        response = await client.post(
            "/api/v1/prompts/descriptions",
            json={"name": "Epic Rock", "content": "Some content"},
        )
        assert response.status_code == 409

    async def test_create_name_too_long(self, client: AsyncClient) -> None:
        """Name exceeding 100 chars returns 422."""
        response = await client.post(
            "/api/v1/prompts/descriptions",
            json={"name": "A" * 101, "content": "Valid content"},
        )
        assert response.status_code == 422

    async def test_create_content_empty(self, client: AsyncClient) -> None:
        """Empty content returns 422."""
        response = await client.post(
            "/api/v1/prompts/descriptions",
            json={"name": "Valid Name", "content": ""},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# PUT /prompts/descriptions/{id}
# ---------------------------------------------------------------------------


class TestUpdateDescription:
    """Tests for PUT /api/v1/prompts/descriptions/{id}."""

    async def test_update_success(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Valid update returns 200 with updated record."""
        desc_id = uuid4()
        response = await client.put(
            f"/api/v1/prompts/descriptions/{desc_id}",
            json={"name": "Updated Name", "content": "Updated content"},
        )
        assert response.status_code == 200
        mock_prompt_service.update_description.assert_awaited_once()

    async def test_update_not_found(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Non-existent description returns 404."""
        mock_prompt_service.update_description.side_effect = NotFoundError(
            "Description not found."
        )
        desc_id = uuid4()
        response = await client.put(
            f"/api/v1/prompts/descriptions/{desc_id}",
            json={"name": "New Name"},
        )
        assert response.status_code == 404

    async def test_update_partial_fields(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Updating only some fields is valid."""
        desc_id = uuid4()
        response = await client.put(
            f"/api/v1/prompts/descriptions/{desc_id}",
            json={"content": "Only content updated"},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# DELETE /prompts/descriptions/{id}
# ---------------------------------------------------------------------------


class TestDeleteDescription:
    """Tests for DELETE /api/v1/prompts/descriptions/{id}."""

    async def test_delete_success(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Valid delete returns 200."""
        desc_id = uuid4()
        response = await client.delete(f"/api/v1/prompts/descriptions/{desc_id}")
        assert response.status_code == 200
        assert "deleted" in response.json()["message"]
        mock_prompt_service.delete_description.assert_awaited_once_with(desc_id)

    async def test_delete_not_found(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Non-existent description returns 404."""
        mock_prompt_service.delete_description.side_effect = NotFoundError(
            "Description not found."
        )
        desc_id = uuid4()
        response = await client.delete(f"/api/v1/prompts/descriptions/{desc_id}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /prompts/structures
# ---------------------------------------------------------------------------


class TestListStructures:
    """Tests for GET /api/v1/prompts/structures."""

    async def test_list_empty(self, client: AsyncClient) -> None:
        """Empty list returns 200 with empty array."""
        response = await client.get("/api/v1/prompts/structures")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_returns_structures(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Returns all structures."""
        struct = _make_structure()
        mock_prompt_service.list_structures.return_value = [struct]

        response = await client.get("/api/v1/prompts/structures")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Verse-Chorus"

    async def test_non_admin_rejected(self, non_admin_client: AsyncClient) -> None:
        """Non-admin user receives 403."""
        response = await non_admin_client.get("/api/v1/prompts/structures")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /prompts/structures
# ---------------------------------------------------------------------------


class TestCreateStructure:
    """Tests for POST /api/v1/prompts/structures."""

    async def test_create_success(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Valid request creates a structure and returns 201."""
        response = await client.post(
            "/api/v1/prompts/structures",
            json={
                "name": "Bridge Heavy",
                "content": "[Verse]\n[Bridge]\n[Chorus]\n[Bridge]\n[Outro]",
                "match_key": "bridge_set",
            },
        )
        assert response.status_code == 201
        mock_prompt_service.create_structure.assert_awaited_once()

    async def test_create_duplicate_name(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Duplicate name returns 409."""
        mock_prompt_service.create_structure.side_effect = DuplicateError(
            "A structure named 'Verse-Chorus' already exists."
        )
        response = await client.post(
            "/api/v1/prompts/structures",
            json={"name": "Verse-Chorus", "content": "[Verse]\n[Chorus]"},
        )
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# PUT /prompts/structures/{id}
# ---------------------------------------------------------------------------


class TestUpdateStructure:
    """Tests for PUT /api/v1/prompts/structures/{id}."""

    async def test_update_success(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Valid update returns 200."""
        struct_id = uuid4()
        response = await client.put(
            f"/api/v1/prompts/structures/{struct_id}",
            json={"name": "Updated Structure", "content": "[Intro]\n[Verse]\n[Chorus]"},
        )
        assert response.status_code == 200
        mock_prompt_service.update_structure.assert_awaited_once()

    async def test_update_not_found(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Non-existent structure returns 404."""
        mock_prompt_service.update_structure.side_effect = NotFoundError(
            "Structure not found."
        )
        struct_id = uuid4()
        response = await client.put(
            f"/api/v1/prompts/structures/{struct_id}",
            json={"name": "New Name"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /prompts/structures/{id}
# ---------------------------------------------------------------------------


class TestDeleteStructure:
    """Tests for DELETE /api/v1/prompts/structures/{id}."""

    async def test_delete_success(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Valid delete returns 200."""
        struct_id = uuid4()
        response = await client.delete(f"/api/v1/prompts/structures/{struct_id}")
        assert response.status_code == 200
        assert "deleted" in response.json()["message"]
        mock_prompt_service.delete_structure.assert_awaited_once_with(struct_id)

    async def test_delete_not_found(
        self, client: AsyncClient, mock_prompt_service: AsyncMock
    ) -> None:
        """Non-existent structure returns 404."""
        mock_prompt_service.delete_structure.side_effect = NotFoundError(
            "Structure not found."
        )
        struct_id = uuid4()
        response = await client.delete(f"/api/v1/prompts/structures/{struct_id}")
        assert response.status_code == 404
