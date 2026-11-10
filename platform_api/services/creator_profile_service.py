"""Creator identity: handles, profiles, and public pages.

Phase 1 scope. Verification, badges, follows, releases, and earnings are
separate phases; this service only owns the public identity.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from platform_api.exceptions import (
    DuplicateError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from platform_api.repositories.creator_repo import CreatorRepository

HANDLE_RE = re.compile(r"^[a-z][a-z0-9_]{2,29}$")
HANDLE_CHANGE_COOLDOWN_DAYS = 90

RESERVED_HANDLES = {
    "admin",
    "administrator",
    "api",
    "artist",
    "artists",
    "about",
    "blog",
    "camxora",
    "careers",
    "checkout",
    "community",
    "contact",
    "create",
    "creator",
    "creators",
    "discover",
    "download",
    "help",
    "legal",
    "library",
    "login",
    "logout",
    "me",
    "music",
    "official",
    "privacy",
    "root",
    "search",
    "settings",
    "signup",
    "staff",
    "studio",
    "support",
    "system",
    "terms",
    "verified",
    "you",
}

_AI_DISCLOSURES = {"none", "ai_assisted", "ai_artist"}
_CURRENCIES = {"USD", "KHR"}


def normalize_handle(value: str) -> str:
    return str(value or "").strip().lstrip("@").lower()


def validate_handle(value: str) -> str:
    handle = normalize_handle(value)
    if not HANDLE_RE.match(handle):
        raise ValidationError(
            "Handle must be 3-30 characters, start with a letter, and use only "
            "lowercase letters, numbers, and underscores.",
            details={"fields": {"handle": "invalid format"}},
        )
    if handle in RESERVED_HANDLES:
        raise ValidationError(
            "That handle is reserved.",
            details={"fields": {"handle": "reserved"}},
        )
    return handle


def _clean_text(value: Any, *, field: str, max_length: int, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValidationError(
                f"{field} is required.", details={"fields": {field: "required"}}
            )
        return None
    text = str(value).strip()
    if not text:
        if required:
            raise ValidationError(
                f"{field} is required.", details={"fields": {field: "required"}}
            )
        return None
    if len(text) > max_length:
        raise ValidationError(
            f"{field} must be at most {max_length} characters.",
            details={"fields": {field: f"max length {max_length}"}},
        )
    return text


def _clean_list(
    values: Any, *, field: str, max_items: int, max_length: int
) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValidationError(
            f"{field} must be a list.", details={"fields": {field: "expected list"}}
        )
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = _clean_text(raw, field=field, max_length=max_length)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    if len(cleaned) > max_items:
        raise ValidationError(
            f"{field} can contain at most {max_items} items.",
            details={"fields": {field: f"max {max_items} items"}},
        )
    return cleaned


def _clean_links(values: Any) -> list[dict[str, str]]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValidationError(
            "links must be a list.", details={"fields": {"links": "expected list"}}
        )
    if len(values) > 5:
        raise ValidationError(
            "links can contain at most 5 items.",
            details={"fields": {"links": "max 5 items"}},
        )
    cleaned: list[dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            raise ValidationError(
                "Each link must have a label and url.",
                details={"fields": {"links": "invalid item"}},
            )
        label = _clean_text(item.get("label"), field="links.label", max_length=30)
        url = _clean_text(item.get("url"), field="links.url", max_length=500)
        if not label or not url:
            raise ValidationError(
                "Each link must have a label and url.",
                details={"fields": {"links": "label and url required"}},
            )
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationError(
                "Link URLs must start with http:// or https://.",
                details={"fields": {"links": "invalid url"}},
            )
        cleaned.append({"label": label, "url": url})
    return cleaned


def _decode_links(value: Any) -> list[dict[str, str]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    return value if isinstance(value, list) else []


def _validate_display_name(value: Any) -> str:
    name = _clean_text(value, field="display_name", max_length=50, required=True)
    assert name is not None
    lowered = name.casefold()
    if "camxora" in lowered or lowered in {"admin", "support", "official"}:
        raise ValidationError(
            "That display name is reserved.",
            details={"fields": {"display_name": "reserved"}},
        )
    return name


class CreatorProfileService:
    def __init__(self, pool: Any) -> None:
        self._pool = pool
        self._repo = CreatorRepository(pool)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------
    async def get_public(self, handle: str) -> dict[str, Any] | None:
        profile = await self._repo.get_by_handle(normalize_handle(handle))
        if profile:
            return _public_payload(profile)
        redirect = await self._repo.get_redirect(normalize_handle(handle))
        if redirect:
            return {"redirect": redirect}
        return None

    async def get_public_releases(self, handle: str) -> dict[str, Any] | None:
        normalized = normalize_handle(handle)
        profile = await self._repo.get_by_handle(normalized)
        if profile is None:
            return None
        rows = await self._repo.list_public_releases(normalized)
        items = []
        for row in rows:
            genres = row.get("genres")
            if isinstance(genres, str):
                try:
                    genres = json.loads(genres)
                except json.JSONDecodeError:
                    genres = []
            count = int(row.get("track_count") or 0)
            items.append(
                {
                    "id": str(row["id"]),
                    "title": row["title"],
                    "album_slug": row.get("album_slug"),
                    "genre": row.get("genre"),
                    "genres": genres if isinstance(genres, list) else [],
                    "cover_url": None,
                    "track_count": count,
                    "release_type": "album" if count > 1 else "single",
                    "published_at": row.get("published_at"),
                }
            )
        return {"items": items}

    async def list_public(
        self,
        *,
        q: str | None = None,
        genre: str | None = None,
        country: str | None = None,
        verified_only: bool = False,
        sort: str = "followers",
        limit: int = 24,
        offset: int = 0,
    ) -> dict[str, Any]:
        items = await self._repo.list_public(
            q=q,
            genre=genre,
            country=country,
            verified_only=verified_only,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        total = await self._repo.count_public(
            q=q, genre=genre, country=country, verified_only=verified_only
        )
        return {
            "items": [_public_payload(item) for item in items],
            "total": total,
            "limit": max(1, min(limit, 100)),
            "offset": max(0, offset),
        }

    # ------------------------------------------------------------------
    # Studio
    # ------------------------------------------------------------------
    async def get_studio(self, user_id: str) -> dict[str, Any]:
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            return {"profile": None, "checklist": _empty_checklist()}
        return {
            "profile": _studio_payload(profile),
            "checklist": _checklist(profile),
        }

    async def claim(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        if await self._repo.get_by_user_id(user_id):
            raise DuplicateError("You already have a creator profile.")

        handle = validate_handle(data.get("handle", ""))
        if await self._repo.handle_exists(handle):
            raise DuplicateError(
                "That handle is already taken.",
                details={"fields": {"handle": "taken"}},
            )

        profile = await self._repo.insert_profile(
            user_id=user_id,
            handle=handle,
            display_name=_validate_display_name(data.get("display_name")),
            tagline=_clean_text(data.get("tagline"), field="tagline", max_length=120),
            bio=_clean_text(data.get("bio"), field="bio", max_length=2000),
            country_code=_country_code(data.get("country_code")),
            city=_clean_text(data.get("city"), field="city", max_length=80),
            avatar_url=_url(data.get("avatar_url"), field="avatar_url"),
            banner_url=_url(data.get("banner_url"), field="banner_url"),
            links=_clean_links(data.get("links")),
            genres=_clean_list(
                data.get("genres"), field="genres", max_items=3, max_length=60
            ),
            influences=_clean_list(
                data.get("influences"), field="influences", max_items=5, max_length=60
            ),
            pronouns=_clean_text(data.get("pronouns"), field="pronouns", max_length=20),
            ai_disclosure=_ai_disclosure(data.get("ai_disclosure")),
            support_enabled=bool(data.get("support_enabled", False)),
            payout_currency=_currency(data.get("payout_currency")),
        )
        return {
            "profile": _studio_payload(profile),
            "checklist": _checklist(profile),
        }

    async def update(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise NotFoundError("Creator profile not found.")

        fields: dict[str, Any] = {}

        if "display_name" in data:
            fields["display_name"] = _validate_display_name(data["display_name"])
        if "tagline" in data:
            fields["tagline"] = _clean_text(data["tagline"], field="tagline", max_length=120)
        if "bio" in data:
            fields["bio"] = _clean_text(data["bio"], field="bio", max_length=2000)
        if "country_code" in data:
            fields["country_code"] = _country_code(data["country_code"])
        if "city" in data:
            fields["city"] = _clean_text(data["city"], field="city", max_length=80)
        if "avatar_url" in data:
            fields["avatar_url"] = _url(data["avatar_url"], field="avatar_url")
        if "banner_url" in data:
            fields["banner_url"] = _url(data["banner_url"], field="banner_url")
        if "links" in data:
            fields["links"] = _clean_links(data["links"])
        if "genres" in data:
            fields["genres"] = _clean_list(
                data["genres"], field="genres", max_items=3, max_length=60
            )
        if "influences" in data:
            fields["influences"] = _clean_list(
                data["influences"], field="influences", max_items=5, max_length=60
            )
        if "pronouns" in data:
            fields["pronouns"] = _clean_text(data["pronouns"], field="pronouns", max_length=20)
        if "ai_disclosure" in data:
            fields["ai_disclosure"] = _ai_disclosure(data["ai_disclosure"])
        if "support_enabled" in data:
            fields["support_enabled"] = bool(data["support_enabled"])
        if "payout_currency" in data:
            fields["payout_currency"] = _currency(data["payout_currency"])

        if "handle" in data:
            new_handle = validate_handle(data["handle"])
            if new_handle != normalize_handle(profile["handle"]):
                await self._assert_handle_change_allowed(user_id, new_handle)
                await self._repo.insert_handle_history(
                    user_id, str(profile["handle"]), new_handle
                )
                profile = await self._repo.set_handle(user_id, new_handle)

        if fields:
            profile = await self._repo.update_profile(user_id, fields)

        return {
            "profile": _studio_payload(profile),
            "checklist": _checklist(profile),
        }

    async def upload_media(
        self,
        user_id: str,
        *,
        kind: str,
        content_type: str,
        data: bytes,
    ) -> dict[str, Any]:
        if kind not in {"avatar", "banner"}:
            raise ValidationError(
                "kind must be avatar or banner.",
                details={"fields": {"kind": "invalid"}},
            )
        if await self._repo.get_by_user_id(user_id) is None:
            raise NotFoundError("Creator profile not found.")
        normalized_type = str(content_type or "").split(";")[0].strip().lower()
        if not normalized_type.startswith("image/"):
            raise ValidationError(
                "Only image files can be uploaded.",
                details={"fields": {"file": "image required"}},
            )
        if not data:
            raise ValidationError(
                "The uploaded image is empty.",
                details={"fields": {"file": "empty"}},
            )
        if len(data) > 5 * 1024 * 1024:
            raise ValidationError(
                "Images are limited to 5 MB.",
                details={"fields": {"file": "max 5 MB"}},
            )

        from platform_api.services.storage_service import StorageService
        from platform_api.services.streaming_config_service import (
            resolve_streaming_storage_config,
        )

        config = await resolve_streaming_storage_config(self._pool)
        if not config.configured:
            raise ExternalServiceError(
                "Image uploads are not configured.",
                is_retryable=False,
                details={"reason": "storage_not_configured"},
            )
        extension = {
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "image/gif": "gif",
        }.get(normalized_type, "jpg")
        key = f"creator/{kind}/{user_id}/{uuid4()}.{extension}"
        try:
            storage = StorageService.from_config(config)
            await storage.upload_bytes(
                key=key,
                data=data,
                content_type=normalized_type,
            )
            url = await storage.get_signed_get_url(
                key, expires_seconds=365 * 24 * 60 * 60
            )
        except Exception as exc:
            raise ExternalServiceError(
                "Could not store the uploaded image.",
                is_retryable=True,
                details={"provider": "storage"},
            ) from exc

        column = "avatar_url" if kind == "avatar" else "banner_url"
        await self._repo.update_profile(user_id, {column: url})
        return {"url": url, "kind": kind}

    async def availability(self, raw_handle: str) -> dict[str, Any]:
        normalized = normalize_handle(raw_handle)
        try:
            handle = validate_handle(normalized)
        except ValidationError as exc:
            return {
                "handle": normalized,
                "available": False,
                "reason": (exc.details or {}).get("fields", {}).get("handle", "invalid"),
                "suggestions": await self._suggest_handles(normalized),
            }
        if await self._repo.handle_exists(handle):
            return {
                "handle": handle,
                "available": False,
                "reason": "taken",
                "suggestions": await self._suggest_handles(handle),
            }
        return {"handle": handle, "available": True, "reason": None, "suggestions": []}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _assert_handle_change_allowed(self, user_id: str, new_handle: str) -> None:
        if await self._repo.handle_exists(new_handle):
            raise DuplicateError(
                "That handle is already taken.",
                details={"fields": {"handle": "taken"}},
            )
        last = await self._repo.last_handle_change(user_id)
        if last is None:
            return
        next_allowed = last + timedelta(days=HANDLE_CHANGE_COOLDOWN_DAYS)
        if next_allowed > datetime.now(timezone.utc):
            raise ValidationError(
                "You can change your handle once every 90 days.",
                details={
                    "fields": {"handle": "cooldown"},
                    "next_allowed_at": next_allowed.isoformat(),
                },
            )

    async def _suggest_handles(self, base: str) -> list[str]:
        stem = re.sub(r"[^a-z0-9_]", "", normalize_handle(base))[:24] or "creator"
        if not stem or not stem[0].isalpha():
            stem = f"creator{stem}"
        suggestions: list[str] = []
        for suffix in ("2", "3", "4", "kh", "music"):
            candidate = f"{stem}{suffix}"[:30]
            if candidate in RESERVED_HANDLES:
                continue
            if not await self._repo.handle_exists(candidate):
                suggestions.append(candidate)
            if len(suggestions) >= 3:
                break
        return suggestions


def _public_payload(profile: dict[str, Any]) -> dict[str, Any]:
    tier = str(profile.get("tier") or "creator")
    badges = ["verified"] if tier in {"verified", "partner"} else []
    return {
        "handle": profile["handle"],
        "display_name": profile["display_name"],
        "tagline": profile.get("tagline"),
        "bio": profile.get("bio"),
        "avatar_url": profile.get("avatar_url"),
        "banner_url": profile.get("banner_url"),
        "country_code": profile.get("country_code"),
        "city": profile.get("city"),
        "genres": list(profile.get("genres") or []),
        "influences": list(profile.get("influences") or []),
        "links": _decode_links(profile.get("links")),
        "ai_disclosure": profile.get("ai_disclosure") or "none",
        "tier": tier,
        "badges": badges,
        "support_enabled": bool(profile.get("support_enabled")),
        "joined_at": profile.get("program_joined_at"),
        "stats": {
            "followers": int(profile.get("follower_count") or 0),
            "monthly_listeners": 0,
            "releases": 0,
            "valid_streams": 0,
        },
        "is_following": False,
    }


def _studio_payload(profile: dict[str, Any]) -> dict[str, Any]:
    payload = _public_payload(profile)
    payload.update(
        {
            "user_id": str(profile["user_id"]),
            "payout_currency": profile.get("payout_currency") or "USD",
            "status": profile.get("status") or "active",
            "pronouns": profile.get("pronouns"),
            "program_joined_at": profile.get("program_joined_at"),
        }
    )
    return payload


def _checklist(profile: dict[str, Any]) -> dict[str, bool]:
    return {
        "handle": bool(profile.get("handle")),
        "display_name": bool(profile.get("display_name")),
        "bio": bool(profile.get("bio")),
        "avatar": bool(profile.get("avatar_url")),
        "genre": bool(profile.get("genres")),
        "first_release": False,
        "verified": str(profile.get("tier") or "creator") in {"verified", "partner"},
        "payout_ready": False,
    }


def _empty_checklist() -> dict[str, bool]:
    return {
        "handle": False,
        "display_name": False,
        "bio": False,
        "avatar": False,
        "genre": False,
        "first_release": False,
        "verified": False,
        "payout_ready": False,
    }


def _country_code(value: Any) -> str | None:
    text = _clean_text(value, field="country_code", max_length=2)
    if text is None:
        return None
    text = text.upper()
    if len(text) != 2 or not text.isalpha():
        raise ValidationError(
            "country_code must be a 2-letter code.",
            details={"fields": {"country_code": "invalid"}},
        )
    return text


def _ai_disclosure(value: Any) -> str:
    text = str(value or "none").strip().lower()
    if text == "ai_assisted":
        return text
    if text in {"ai_artist", "ai_generated"}:
        return "ai_artist"
    if text not in _AI_DISCLOSURES:
        raise ValidationError(
            "ai_disclosure must be none, ai_assisted, or ai_artist.",
            details={"fields": {"ai_disclosure": "invalid"}},
        )
    return text


def _currency(value: Any) -> str:
    text = str(value or "USD").strip().upper()
    if text not in _CURRENCIES:
        raise ValidationError(
            "payout_currency must be USD or KHR.",
            details={"fields": {"payout_currency": "invalid"}},
        )
    return text


def _url(value: Any, *, field: str) -> str | None:
    text = _clean_text(value, field=field, max_length=500)
    if text is None:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError(
            f"{field} must be an http(s) URL.",
            details={"fields": {field: "invalid url"}},
        )
    return text
