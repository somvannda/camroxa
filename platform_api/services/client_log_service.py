"""Service for desktop client log uploads."""

from __future__ import annotations

from uuid import UUID

from platform_api.repositories.client_log_repo import ClientLogBatch, ClientLogRepository

MAX_CONTENT_CHARS = 900_000
MAX_LINE_COUNT = 10_000
KEEP_BATCHES_PER_USER = 40


class ClientLogService:
    def __init__(self, repo: ClientLogRepository) -> None:
        self._repo = repo

    async def upload(
        self,
        *,
        user_id: UUID,
        content: str,
        line_count: int | None = None,
        client_id: str | None = None,
        client_label: str | None = None,
        app_version: str | None = None,
    ) -> ClientLogBatch:
        text = str(content or "")
        if len(text) > MAX_CONTENT_CHARS:
            text = text[-MAX_CONTENT_CHARS:]
            nl = text.find("\n")
            if nl >= 0:
                text = text[nl + 1 :]
        if not text.strip():
            raise ValueError("Log content is empty.")
        counted = int(line_count) if line_count is not None else text.count("\n") + 1
        counted = max(1, min(MAX_LINE_COUNT, counted))
        batch = await self._repo.insert(
            user_id=user_id,
            content=text,
            line_count=counted,
            client_id=(client_id or None),
            client_label=(client_label or None),
            app_version=(app_version or None),
        )
        await self._repo.prune_user_batches(user_id=user_id, keep=KEEP_BATCHES_PER_USER)
        return batch

    async def list_for_user(
        self,
        *,
        user_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ClientLogBatch], int]:
        return await self._repo.list_for_user(user_id=user_id, page=page, page_size=page_size)

    async def get_batch(self, batch_id: UUID) -> ClientLogBatch | None:
        return await self._repo.get_by_id(batch_id)
