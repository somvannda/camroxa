"""Channel prompt management service.

Provides create/update/delete for channel prompts used by the
onboarding wizard to generate channel names, logos, covers, etc.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID

from platform_api.exceptions import DuplicateError, NotFoundError, ValidationError
from platform_api.models.domain import ChannelPrompt

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"title", "logo", "cover", "description", "keyword", "tag"}

_MIN_NAME_LENGTH = 1
_MAX_NAME_LENGTH = 100
_MIN_CONTENT_LENGTH = 1
_MAX_CONTENT_LENGTH = 5000


class ChannelPromptRepositoryPort(Protocol):
    async def create(self, prompt: ChannelPrompt) -> ChannelPrompt: ...
    async def get_by_id(self, prompt_id: UUID) -> ChannelPrompt | None: ...
    async def list_all(self) -> list[ChannelPrompt]: ...
    async def list_by_category(self, category: str) -> list[ChannelPrompt]: ...
    async def get_best_match(self, category: str, genre: str, match_key: str | None = None) -> ChannelPrompt | None: ...
    async def update(self, prompt_id: UUID, **fields: Any) -> ChannelPrompt | None: ...
    async def delete(self, prompt_id: UUID) -> bool: ...


class ChannelPromptService:
    """Service for channel prompt CRUD operations."""

    def __init__(self, repo: ChannelPromptRepositoryPort) -> None:
        self._repo = repo

    def _validate(self, name: str, content: str, category: str) -> None:
        errors = []
        if len(name) < _MIN_NAME_LENGTH or len(name) > _MAX_NAME_LENGTH:
            errors.append({"field": "name", "message": f"Name must be 1-{_MAX_NAME_LENGTH} characters."})
        if len(content) < _MIN_CONTENT_LENGTH or len(content) > _MAX_CONTENT_LENGTH:
            errors.append({"field": "content", "message": f"Content must be 1-{_MAX_CONTENT_LENGTH} characters."})
        if category not in VALID_CATEGORIES:
            errors.append({"field": "category", "message": f"Category must be one of: {', '.join(sorted(VALID_CATEGORIES))}"})
        if errors:
            raise ValidationError(message="Validation failed.", details={"fields": errors})

    async def create(self, name: str, content: str, category: str, genre: str = "", match_key: str | None = None, is_active: bool = True) -> ChannelPrompt:
        self._validate(name, content, category)
        prompt = ChannelPrompt(name=name, content=content, category=category, genre=genre, match_key=match_key, is_active=is_active)
        return await self._repo.create(prompt)

    async def get(self, prompt_id: UUID) -> ChannelPrompt:
        prompt = await self._repo.get_by_id(prompt_id)
        if prompt is None:
            raise NotFoundError(f"Channel prompt {prompt_id} not found.")
        return prompt

    async def list_all(self) -> list[ChannelPrompt]:
        return await self._repo.list_all()

    async def list_by_category(self, category: str) -> list[ChannelPrompt]:
        if category not in VALID_CATEGORIES:
            raise ValidationError(message="Invalid category.", details={"field": "category"})
        return await self._repo.list_by_category(category)

    async def get_best_match(self, category: str, genre: str, match_key: str | None = None) -> ChannelPrompt | None:
        return await self._repo.get_best_match(category, genre, match_key)

    async def update(self, prompt_id: UUID, **fields: Any) -> ChannelPrompt:
        existing = await self.get(prompt_id)
        if "name" in fields and fields["name"] != existing.name:
            pass  # Name uniqueness is per (name, category), handled by DB
        if "content" in fields:
            if len(fields["content"]) < _MIN_CONTENT_LENGTH or len(fields["content"]) > _MAX_CONTENT_LENGTH:
                raise ValidationError(message="Content must be 1-5000 characters.", details={"field": "content"})
        if "category" in fields and fields["category"] not in VALID_CATEGORIES:
            raise ValidationError(message="Invalid category.", details={"field": "category"})
        updated = await self._repo.update(prompt_id, **fields)
        if updated is None:
            raise NotFoundError(f"Channel prompt {prompt_id} not found.")
        return updated

    async def delete(self, prompt_id: UUID) -> None:
        deleted = await self._repo.delete(prompt_id)
        if not deleted:
            raise NotFoundError(f"Channel prompt {prompt_id} not found.")
