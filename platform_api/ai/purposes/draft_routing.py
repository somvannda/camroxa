"""Draft generation routing across title, album, and lyric slots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from platform_api.ai.models import TextRouting


@dataclass(frozen=True)
class DraftRouting:
    """Resolved routing for song draft fields."""

    lyric: TextRouting
    title: TextRouting
    album: TextRouting

    @property
    def use_split(self) -> bool:
        """True when title/album use a different assignment than lyric."""
        return not (
            self.title.same_assignment(self.lyric) and self.album.same_assignment(self.lyric)
        )


def _to_text_routing(result: Any) -> TextRouting:
    return TextRouting(
        provider=str(getattr(result, "provider", "") or "").strip(),
        sub_model=getattr(result, "sub_model", None),
    )


def build_draft_routing(lyric: Any, title: Any | None = None, album: Any | None = None) -> DraftRouting:
    """Build draft routing from AI routing resolve() results."""
    lyric_routing = _to_text_routing(lyric)
    title_routing = _to_text_routing(title) if title is not None else lyric_routing
    album_routing = _to_text_routing(album) if album is not None else lyric_routing
    return DraftRouting(lyric=lyric_routing, title=title_routing, album=album_routing)
