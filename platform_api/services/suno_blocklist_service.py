"""Service for admin CRUD and runtime Suno blocklist configuration."""

from __future__ import annotations

import re
import time
from typing import Any, Protocol
from uuid import UUID

from platform_api.exceptions import ValidationError
from platform_api.services.suno_lyrics_sanitize import (
    DEFAULT_REPLACEMENTS,
    SunoRuntimeBlocklist,
)

_TERM_PATTERN = re.compile(r"^[a-z0-9][a-z0-9 _-]{0,119}$")
_RUNTIME_CACHE_TTL_SECONDS = 60.0


class SunoBlocklistRepositoryProtocol(Protocol):
    async def list_all(self) -> list[dict[str, Any]]: ...

    async def get_by_id(self, term_id: UUID) -> dict[str, Any] | None: ...

    async def get_enabled_terms(self) -> list[dict[str, Any]]: ...

    async def create(
        self,
        *,
        term: str,
        replacement: str | None,
        severity: str,
        source: str = "manual",
        enabled: bool = True,
        notes: str | None = None,
    ) -> dict[str, Any]: ...

    async def update(
        self,
        term_id: UUID,
        *,
        term: str | None = None,
        replacement: str | None = None,
        severity: str | None = None,
        enabled: bool | None = None,
        notes: str | None = None,
        clear_replacement: bool = False,
    ) -> dict[str, Any]: ...

    async def delete(self, term_id: UUID) -> bool: ...

    async def upsert_learned(
        self,
        *,
        term: str,
        replacement: str | None,
        severity: str = "block",
        enabled: bool = True,
        notes: str | None = None,
    ) -> dict[str, Any]: ...


class SunoBlocklistService:
    def __init__(self, repo: SunoBlocklistRepositoryProtocol) -> None:
        self._repo = repo
        self._runtime_cache: SunoRuntimeBlocklist | None = None
        self._runtime_cache_at: float = 0.0

    async def list_terms(self) -> list[dict[str, Any]]:
        return await self._repo.list_all()

    async def create_term(
        self,
        *,
        term: str,
        replacement: str | None = None,
        severity: str = "block",
        enabled: bool = True,
        notes: str | None = None,
        source: str = "manual",
    ) -> dict[str, Any]:
        normalized_term = self._normalize_term(term)
        normalized_severity = self._normalize_severity(severity)
        normalized_replacement = self._normalize_replacement(replacement)
        self._validate_block_replacement(normalized_severity, normalized_replacement)
        row = await self._repo.create(
            term=normalized_term,
            replacement=normalized_replacement,
            severity=normalized_severity,
            source=source,
            enabled=enabled,
            notes=notes,
        )
        self.invalidate_runtime_cache()
        return row

    async def update_term(
        self,
        term_id: UUID,
        *,
        term: str | None = None,
        replacement: str | None = None,
        severity: str | None = None,
        enabled: bool | None = None,
        notes: str | None = None,
        clear_replacement: bool = False,
    ) -> dict[str, Any]:
        normalized_term = self._normalize_term(term) if term is not None else None
        normalized_severity = self._normalize_severity(severity) if severity is not None else None
        normalized_replacement = (
            self._normalize_replacement(replacement) if replacement is not None else None
        )
        if normalized_severity is not None or clear_replacement or normalized_replacement is not None:
            existing = await self._repo.get_by_id(term_id)
            if existing is None:
                from platform_api.exceptions import NotFoundError

                raise NotFoundError("Blocklist term not found.", details={"id": str(term_id)})
            next_severity = normalized_severity or str(existing["severity"])
            next_replacement = None if clear_replacement else (
                normalized_replacement
                if normalized_replacement is not None
                else existing.get("replacement")
            )
            self._validate_block_replacement(next_severity, next_replacement)
        row = await self._repo.update(
            term_id,
            term=normalized_term,
            replacement=normalized_replacement,
            severity=normalized_severity,
            enabled=enabled,
            notes=notes,
            clear_replacement=clear_replacement,
        )
        self.invalidate_runtime_cache()
        return row

    async def delete_term(self, term_id: UUID) -> bool:
        deleted = await self._repo.delete(term_id)
        if deleted:
            self.invalidate_runtime_cache()
        return deleted

    async def promote_learned_term(
        self,
        *,
        term: str,
        replacement: str | None = None,
        severity: str = "block",
        notes: str | None = None,
    ) -> dict[str, Any]:
        normalized_term = self._normalize_term(term)
        normalized_severity = self._normalize_severity(severity)
        normalized_replacement = self._normalize_replacement(replacement)
        self._validate_block_replacement(normalized_severity, normalized_replacement)
        row = await self._repo.upsert_learned(
            term=normalized_term,
            replacement=normalized_replacement,
            severity=normalized_severity,
            enabled=True,
            notes=notes,
        )
        self.invalidate_runtime_cache()
        return row

    async def get_runtime_config(self, *, force_refresh: bool = False) -> SunoRuntimeBlocklist:
        now = time.monotonic()
        if (
            not force_refresh
            and self._runtime_cache is not None
            and (now - self._runtime_cache_at) < _RUNTIME_CACHE_TTL_SECONDS
        ):
            return self._runtime_cache

        rows = await self._repo.get_enabled_terms()
        replacements = dict(DEFAULT_REPLACEMENTS)
        block_terms: set[str] = set()
        warn_terms: set[str] = set()

        for row in rows:
            term = str(row.get("term") or "").strip().lower()
            if not term:
                continue
            severity = str(row.get("severity") or "block").strip().lower()
            replacement = row.get("replacement")
            replacement_text = str(replacement).strip() if replacement is not None else ""
            if severity == "warn":
                warn_terms.add(term)
                if replacement_text:
                    replacements[term] = replacement_text
            else:
                block_terms.add(term)
                if replacement_text:
                    replacements[term] = replacement_text

        config = SunoRuntimeBlocklist(
            replacements=replacements,
            block_terms=frozenset(block_terms),
            warn_terms=frozenset(warn_terms),
        )
        self._runtime_cache = config
        self._runtime_cache_at = now
        return config

    def invalidate_runtime_cache(self) -> None:
        self._runtime_cache = None
        self._runtime_cache_at = 0.0

    @staticmethod
    def _normalize_term(value: str) -> str:
        normalized = str(value or "").strip().lower()
        if not normalized:
            raise ValidationError("term is required.", details={"field": "term"})
        if not _TERM_PATTERN.match(normalized):
            raise ValidationError(
                "term must use lowercase letters, numbers, spaces, underscores, or hyphens.",
                details={"field": "term", "term": normalized},
            )
        return normalized

    @staticmethod
    def _normalize_severity(value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"block", "warn"}:
            raise ValidationError(
                "severity must be 'block' or 'warn'.",
                details={"field": "severity", "severity": value},
            )
        return normalized

    @staticmethod
    def _normalize_replacement(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _validate_block_replacement(severity: str, replacement: str | None) -> None:
        if severity == "block" and not replacement:
            # Block terms without explicit replacement still sanitize via default "echo".
            return
