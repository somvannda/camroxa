"""Admin image prompt library selection and thumbnail text resolution."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from platform_api.exceptions import ValidationError
from platform_api.models.enums import ImageKind
from platform_api.repositories.image_prompt_repo import ImagePromptStyleRecord
from platform_api.services.image_source_mode import empty_prompt_library_message


class ImagePromptStyleRepositoryProtocol(Protocol):
    async def list_active(self, *, kind: str) -> list[ImagePromptStyleRecord]: ...

    async def count_active(self) -> dict[str, int]: ...


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
    """Pick admin-curated prompt styles with least-used rotation."""

    def __init__(
        self,
        *,
        repo: ImagePromptStyleRepositoryProtocol,
        history: ImageRandomHistoryProtocol,
    ) -> None:
        self._repo = repo
        self._history = history

    async def pick_style(
        self,
        *,
        kind: ImageKind | str,
        batch_id: UUID,
        exclude_ids: list[str] | None = None,
        previous_batch_id: UUID | None = None,
    ) -> ImagePromptStyleRecord:
        """Return one active style, avoiding ids already used in this batch.

        If the library has fewer styles than the batch needs, the exclusion is
        relaxed and a style is reused. A genuinely empty library raises a clear
        validation error before any job or wallet work happens.
        """
        kind_value = _kind_value(kind)
        active = await self._repo.list_active(kind=kind_value)
        if not active:
            raise ValidationError(
                empty_prompt_library_message(kind_value),
                details={"kind": kind_value, "source": "admin_library"},
            )

        excluded = {str(value).strip() for value in (exclude_ids or []) if str(value).strip()}
        candidates = [style for style in active if style.id not in excluded]
        if not candidates:
            candidates = list(active)

        by_id = {style.id: style for style in candidates}
        chosen_id = await self._history.pick_least_used_value(
            kind=f"{'thumb' if kind_value == 'thumbnail' else 'bg'}_prompt_style",
            values=list(by_id.keys()),
            batch_id=batch_id,
            previous_batch_id=previous_batch_id,
            lock_key=f"image_prompt_style:{kind_value}",
        )
        chosen = by_id.get(str(chosen_id)) or candidates[0]
        return chosen

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
