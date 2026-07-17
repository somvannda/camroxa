"""Billing traceability context attached to credit transactions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DraftBillingContext:
    """Links a draft charge to batch/song records for admin usage tracing."""

    source: str = "api"
    batch_id: str | None = None
    song_id: str | None = None
    batch_index: int | None = None

    def to_metadata(self) -> dict[str, Any]:
        data: dict[str, Any] = {"source": self.source}
        if self.batch_id:
            data["batch_id"] = self.batch_id
        if self.song_id:
            data["song_id"] = self.song_id
        if self.batch_index is not None:
            data["batch_index"] = self.batch_index
        return data

    @property
    def ref_id(self) -> str | None:
        """Prefer song_id as the wallet ref so charges trace to one song."""
        return self.song_id
