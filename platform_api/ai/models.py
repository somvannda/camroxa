"""Shared AI layer datatypes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelSpec:
    """Provider-specific model configuration.

  Adding a new model is usually just a new ``ModelSpec`` entry in the registry.
  """

    api_id: str
    aliases: tuple[str, ...] = ()
    supports_json_mode: bool = False
    extra_payload: dict[str, Any] = field(default_factory=dict)
    cost_tier: str = ""
    request_timeout_seconds: float | None = None


@dataclass(frozen=True)
class TextRouting:
    """Resolved text provider assignment for one operation."""

    provider: str
    sub_model: str | None

    def same_assignment(self, other: TextRouting) -> bool:
        return self.provider == other.provider and self.sub_model == other.sub_model
