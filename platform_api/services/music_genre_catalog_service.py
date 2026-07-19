"""Curated music genre catalog lookup and validation."""

from __future__ import annotations

from typing import Any

from platform_api.repositories.music_genre_catalog_repo import MusicGenreCatalogRepository
from platform_api.services.music_genre_utils import MAX_DESCRIPTION_GENRES, normalize_description_genres


class MusicGenreCatalogService:
    def __init__(self, pool: Any) -> None:
        self._repo = MusicGenreCatalogRepository(pool)
        self._lookup: dict[str, str] | None = None

    async def _ensure_lookup(self) -> dict[str, str]:
        if self._lookup is not None:
            return self._lookup
        rows = await self._repo.fetch_all_active()
        lookup: dict[str, str] = {}
        for row in rows:
            canonical = str(row["name"]).strip()
            if not canonical:
                continue
            lookup[canonical.casefold()] = canonical
            for alias in row.get("aliases") or []:
                alias_text = str(alias).strip()
                if alias_text:
                    lookup[alias_text.casefold()] = canonical
        self._lookup = lookup
        return lookup

    async def list_categories(self) -> list[str]:
        return await self._repo.list_categories()

    async def search(
        self,
        *,
        query: str | None = None,
        category: str | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        rows = await self._repo.search(query=query, category=category, limit=limit)
        return [
            {
                "name": str(row["name"]),
                "slug": str(row["slug"]),
                "category": str(row["category"]),
                "aliases": list(row.get("aliases") or []),
            }
            for row in rows
        ]

    async def resolve_genre_names(self, raw: list[str] | None) -> list[str]:
        """Map user input to canonical catalog names; reject unknown labels."""
        normalized = normalize_description_genres(raw)
        if not normalized:
            return []
        lookup = await self._ensure_lookup()
        if not lookup:
            return normalized

        resolved: list[str] = []
        unknown: list[str] = []
        seen: set[str] = set()
        for item in normalized:
            canonical = lookup.get(item.casefold())
            if not canonical:
                unknown.append(item)
                continue
            key = canonical.casefold()
            if key in seen:
                continue
            seen.add(key)
            resolved.append(canonical)

        if unknown:
            sample = ", ".join(unknown[:5])
            raise ValueError(
                f"Unknown genre(s): {sample}. Pick from the genre catalog suggestions."
            )
        if len(resolved) > MAX_DESCRIPTION_GENRES:
            raise ValueError(f"At most {MAX_DESCRIPTION_GENRES} genres are allowed.")
        return resolved
