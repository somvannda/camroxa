"""Admin image prompt library selection and thumbnail text resolution."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from platform_api.exceptions import ValidationError
from platform_api.models.enums import ImageKind
from platform_api.repositories.image_prompt_repo import ImagePromptStyleRecord
from platform_api.services.image_source_mode import empty_prompt_library_message


class ImagePromptStyleRepositoryProtocol(Protocol):
    async def list_active(
        self, *, kind: str, text_mode: str | None = None
    ) -> list[ImagePromptStyleRecord]: ...

    async def count_active(self) -> dict[str, int]: ...

    async def pick_rotating_style(
        self,
        *,
        user_id: UUID,
        kind: str,
        active_ids: list[str],
        exclude_ids: list[str] | None = None,
        batch_id: UUID | None = None,
    ) -> str | None: ...


class ImageRandomHistoryProtocol(Protocol):
    async def pick_least_used_value(
        self,
        *,
        kind: str,
        values: list[str],
        exclude: list[str] | None = None,
        batch_id: UUID | None = None,
        previous_batch_id: UUID | None = None,
        lock_key: str | None = None,
    ) -> str: ...


def _kind_value(kind: ImageKind | str) -> str:
    value = str(getattr(kind, "value", kind) or "").strip().lower()
    return "thumbnail" if value == "thumbnail" else "background"


class ImagePromptLibraryService:
    """Pick admin-curated prompt styles from a per-user rotation cycle."""

    def __init__(
        self,
        *,
        repo: ImagePromptStyleRepositoryProtocol,
        history: ImageRandomHistoryProtocol | None = None,
    ) -> None:
        self._repo = repo
        # Kept for backward-compatible construction; prompt rotation no longer
        # uses the global least-used table.
        self._history = history

    async def pick_style(
        self,
        *,
        user_id: UUID,
        kind: ImageKind | str,
        batch_id: UUID,
        exclude_ids: list[str] | None = None,
        previous_batch_id: UUID | None = None,
        text_mode: str | None = None,
    ) -> ImagePromptStyleRecord:
        """Return one active style for the user's current prompt cycle.

        Every active style is used once per cycle in random order. When the
        cycle ends it wraps to a new cycle. Within a batch, already-used styles
        are excluded while alternatives remain.
        """
        del previous_batch_id  # per-user cycle replaces previous-batch avoidance
        kind_value = _kind_value(kind)
        active = await self._repo.list_active(kind=kind_value, text_mode=text_mode)
        if not active:
            raise ValidationError(
                empty_prompt_library_message(kind_value),
                details={"kind": kind_value, "source": "admin_library"},
            )

        chosen_id = await self._repo.pick_rotating_style(
            user_id=user_id,
            kind=kind_value,
            active_ids=[style.id for style in active],
            exclude_ids=exclude_ids,
            batch_id=batch_id,
        )
        if chosen_id:
            for style in active:
                if style.id == str(chosen_id):
                    return style
        return active[0]

    async def active_counts(self) -> dict[str, int]:
        return await self._repo.count_active()

    @staticmethod
    def resolve_text_template(
        style: ImagePromptStyleRecord,
        *,
        title: str = "",
        album: str = "",
        channel: str = "",
    ) -> str:
        """Resolve ``{title}`` / ``{album}`` / ``{channel}`` into display text."""
        template = str(style.text_template or "").strip() or "{title}"
        resolved = (
            template.replace("{title}", str(title or "").strip())
            .replace("{album}", str(album or "").strip())
            .replace("{channel}", str(channel or "").strip())
        )
        resolved = resolved.strip()
        return resolved or str(title or "").strip() or str(album or "").strip() or "NEW MUSIC"

    @staticmethod
    def style_summary(style: ImagePromptStyleRecord) -> dict[str, Any]:
        return {
            "id": style.id,
            "kind": style.kind,
            "name": style.name,
            "text_template": style.text_template,
        }
