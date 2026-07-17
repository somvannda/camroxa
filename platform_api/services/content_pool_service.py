"""Content-pool claim, finalize, and release helpers shared by API routes and batch orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence
from uuid import uuid4

from platform_api.dependencies import get_db_pool

PoolKind = Literal["titles", "albums", "openings"]
_RESERVATION_STALE_SECONDS = 900


@dataclass(frozen=True, slots=True)
class ClaimedPoolItem:
    kind: PoolKind
    item_id: int
    text: str
    secondary_text: str | None
    reservation_token: str


def _get_table_name(kind: PoolKind) -> str:
    if kind == "titles":
        return "title_pool"
    if kind == "albums":
        return "album_pool"
    return "opening_pairs"


def _get_text_column(kind: PoolKind) -> str:
    if kind == "titles":
        return "title"
    if kind == "albums":
        return "album"
    return "line1"


def build_pool_inspiration_description(
    base_description: str,
    *,
    title_seed: str,
    album_seed: str,
) -> str:
    inspiration = " / ".join(part for part in (title_seed.strip(), album_seed.strip()) if part)
    if not inspiration:
        return base_description
    return f"{base_description}\n\nInspiration (do not copy words): {inspiration}".strip()


def build_forced_opening_text(*, line1: str, line2: str | None) -> str:
    parts = [part.strip() for part in (line1, line2 or "") if part and part.strip()]
    return "\n".join(parts)


def _normalize_avoid_texts(avoid_texts: Sequence[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in avoid_texts or []:
        text = str(value or "").strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


async def claim_pool_item(
    *,
    kind: PoolKind,
    reservation_owner: str,
    reservation_token: str | None = None,
    limit: int = 50,
    ttl_seconds: int = _RESERVATION_STALE_SECONDS,
    avoid_texts: Sequence[str] | None = None,
) -> ClaimedPoolItem:
    token = str(reservation_token or "").strip() or str(uuid4())
    pool = get_db_pool()
    table_name = _get_table_name(kind)
    text_column = _get_text_column(kind)
    avoid_norms = _normalize_avoid_texts(avoid_texts)
    avoid_clause = ""
    avoid_params: list[Any] = []
    if avoid_norms:
        avoid_clause = f"AND LOWER(TRIM({text_column})) <> ALL($5::text[])"
        avoid_params = [avoid_norms]
    if kind == "openings":
        row = await pool.fetchrow(
            f"""
            UPDATE {table_name} AS target
            SET reservation_token = $1,
                reserved_at = NOW(),
                reserved_by = $2
            FROM (
                SELECT id
                FROM {table_name}
                WHERE used_count < $3
                  AND (
                    reservation_token IS NULL
                    OR reserved_at IS NULL
                    OR reserved_at < (NOW() - ($4 * interval '1 second'))
                  )
                ORDER BY used_count ASC, COALESCE(used_at, created_at) ASC, created_at ASC, id ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            ) AS picked
            WHERE target.id = picked.id
            RETURNING
                target.id,
                target.line1,
                target.line2,
                target.reservation_token
            """,
            token,
            reservation_owner,
            limit,
            ttl_seconds,
        )
        if row is None:
            raise RuntimeError("No eligible opening pool item is available.")
        return ClaimedPoolItem(
            kind=kind,
            item_id=int(row["id"]),
            text=str(row["line1"] or ""),
            secondary_text=str(row["line2"] or "") or None,
            reservation_token=str(row["reservation_token"] or token),
        )

    row = await pool.fetchrow(
        f"""
        UPDATE {table_name} AS target
        SET reservation_token = $1,
            reserved_at = NOW(),
            reserved_by = $2
        FROM (
            SELECT id
            FROM {table_name}
            WHERE used_count < $3
              AND (
                reservation_token IS NULL
                OR reserved_at IS NULL
                OR reserved_at < (NOW() - ($4 * interval '1 second'))
              )
              {avoid_clause}
            ORDER BY used_count ASC, COALESCE(used_at, created_at) ASC, created_at ASC, id ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        ) AS picked
        WHERE target.id = picked.id
        RETURNING
            target.id,
            target.{text_column} AS text,
            target.reservation_token
        """,
        token,
        reservation_owner,
        limit,
        ttl_seconds,
        *avoid_params,
    )
    if row is None:
        label = "title" if kind == "titles" else "album"
        raise RuntimeError(f"No eligible {label} pool item is available.")
    return ClaimedPoolItem(
        kind=kind,
        item_id=int(row["id"]),
        text=str(row["text"] or ""),
        secondary_text=None,
        reservation_token=str(row["reservation_token"] or token),
    )


async def finalize_pool_item(*, item: ClaimedPoolItem) -> None:
    pool = get_db_pool()
    table_name = _get_table_name(item.kind)
    result = await pool.execute(
        f"""
        UPDATE {table_name}
        SET used_count = used_count + 1,
            used_at = NOW(),
            reservation_token = NULL,
            reserved_at = NULL,
            reserved_by = NULL
        WHERE id = $1 AND reservation_token = $2
        """,
        item.item_id,
        item.reservation_token,
    )
    if result.endswith("0"):
        raise RuntimeError("Content-pool reservation not found for finalize.")


async def release_pool_item(*, item: ClaimedPoolItem) -> None:
    pool = get_db_pool()
    table_name = _get_table_name(item.kind)
    result = await pool.execute(
        f"""
        UPDATE {table_name}
        SET reservation_token = NULL,
            reserved_at = NULL,
            reserved_by = NULL
        WHERE id = $1 AND reservation_token = $2
        """,
        item.item_id,
        item.reservation_token,
    )
    if result.endswith("0"):
        raise RuntimeError("Content-pool reservation not found for release.")


async def release_claimed_items(items: list[ClaimedPoolItem]) -> None:
    for item in items:
        try:
            await release_pool_item(item=item)
        except Exception:
            continue
