"""Earning eligibility per track and creator notifications."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from platform_api.exceptions import NotFoundError
from platform_api.services.royalty_policy_service import RoyaltyPolicyService

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD_STREAMS = 500
DEFAULT_THRESHOLD_LISTENERS = 50
HALFWAY_EVENT = "creator_earning_halfway"
ELIGIBLE_EVENT = "creator_earning_eligible"
_ELIGIBILITY_ENABLED = True
_ELIGIBILITY_INTERVAL_SECONDS = 3600


class CreatorEligibilityService:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def _thresholds(self) -> tuple[int, int]:
        try:
            policy = await RoyaltyPolicyService(self._pool).get_active()
        except Exception:
            return DEFAULT_THRESHOLD_STREAMS, DEFAULT_THRESHOLD_LISTENERS
        document = policy.get("document") or {}
        eligibility = document.get("eligibility") or {}
        streams = int(
            document.get("eligibility_streams")
            or eligibility.get("min_valid_streams")
            or DEFAULT_THRESHOLD_STREAMS
        )
        listeners = int(
            document.get("eligibility_unique_listeners")
            or eligibility.get("min_unique_listeners")
            or DEFAULT_THRESHOLD_LISTENERS
        )
        return streams, listeners

    async def _notify(
        self,
        user_id: UUID | str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO notification_queue (user_id, event_type, payload, expires_at)
            VALUES ($1, $2, $3::jsonb, NOW() + INTERVAL '30 days')
            """,
            user_id,
            event_type,
            json.dumps(payload),
        )

    async def refresh_track(
        self,
        track_id: UUID | str,
        *,
        thresholds: tuple[int, int] | None = None,
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            SELECT t.id, t.user_id, t.title,
                   COUNT(v.id) FILTER (
                       WHERE v.status IN ('valid','royalty')
                   )::int AS valid_streams,
                   COUNT(DISTINCT v.listener_user_id) FILTER (
                       WHERE v.status IN ('valid','royalty')
                   )::int AS unique_listeners
            FROM stream_tracks t
            LEFT JOIN valid_streams v
              ON v.subject_type = 'stream_track' AND v.subject_id = t.id
            WHERE t.id = $1
            GROUP BY t.id
            """,
            track_id,
        )
        if row is None:
            raise NotFoundError("Track not found.")

        threshold_streams, threshold_listeners = thresholds or await self._thresholds()
        valid_streams = int(row["valid_streams"] or 0)
        unique_listeners = int(row["unique_listeners"] or 0)
        eligible = (
            valid_streams >= threshold_streams
            and unique_listeners >= threshold_listeners
        )

        current = await self._pool.fetchrow(
            "SELECT * FROM creator_earning_eligibility WHERE track_id = $1",
            row["id"],
        )
        status = str(current["status"]) if current else "not_eligible"
        eligible_at = current["eligible_at"] if current else None
        notified_half_at = current["notified_half_at"] if current else None
        notified_eligible_at = current["notified_eligible_at"] if current else None

        if eligible and status in {"not_eligible", "eligible", "pending_verification"}:
            status = "eligible"
            if eligible_at is None:
                eligible_at = "now"
        if not eligible and status == "not_eligible":
            eligible_at = None

        half_streams = max(1, threshold_streams // 2)
        half_listeners = max(1, threshold_listeners // 2)
        at_halfway = valid_streams >= half_streams and unique_listeners >= half_listeners

        if at_halfway and notified_half_at is None and not eligible:
            await self._notify(
                row["user_id"],
                HALFWAY_EVENT,
                {
                    "track_id": str(row["id"]),
                    "title": row["title"],
                    "valid_streams": valid_streams,
                    "unique_listeners": unique_listeners,
                    "threshold_streams": threshold_streams,
                    "threshold_listeners": threshold_listeners,
                },
            )
            notified_half_at = "now"

        if eligible and notified_eligible_at is None:
            await self._notify(
                row["user_id"],
                ELIGIBLE_EVENT,
                {
                    "track_id": str(row["id"]),
                    "title": row["title"],
                    "valid_streams": valid_streams,
                    "unique_listeners": unique_listeners,
                    "payout_required": True,
                },
            )
            notified_eligible_at = "now"

        updated = await self._pool.fetchrow(
            """
            INSERT INTO creator_earning_eligibility (
                track_id, creator_id, status, valid_streams, unique_listeners,
                threshold_streams, threshold_listeners, notified_half_at,
                notified_eligible_at, eligible_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7,
                CASE WHEN $8::boolean THEN NOW() ELSE NULL END,
                CASE WHEN $9::boolean THEN NOW() ELSE NULL END,
                CASE WHEN $10::boolean THEN NOW() ELSE NULL END,
                NOW()
            )
            ON CONFLICT (track_id) DO UPDATE SET
                status = EXCLUDED.status,
                valid_streams = EXCLUDED.valid_streams,
                unique_listeners = EXCLUDED.unique_listeners,
                threshold_streams = EXCLUDED.threshold_streams,
                threshold_listeners = EXCLUDED.threshold_listeners,
                notified_half_at = COALESCE(creator_earning_eligibility.notified_half_at, EXCLUDED.notified_half_at),
                notified_eligible_at = COALESCE(creator_earning_eligibility.notified_eligible_at, EXCLUDED.notified_eligible_at),
                eligible_at = COALESCE(creator_earning_eligibility.eligible_at, EXCLUDED.eligible_at),
                updated_at = NOW()
            RETURNING *
            """,
            row["id"],
            row["user_id"],
            status,
            valid_streams,
            unique_listeners,
            threshold_streams,
            threshold_listeners,
            notified_half_at == "now",
            notified_eligible_at == "now",
            eligible_at == "now",
        )
        return _row(updated, row.get("title") if hasattr(row, "get") else None)

    async def refresh_creator(self, user_id: UUID | str, *, limit: int = 200) -> int:
        rows = await self._pool.fetch(
            """
            SELECT id FROM stream_tracks
            WHERE user_id = $1 AND publish_status = 'published'
            ORDER BY published_at DESC NULLS LAST, created_at DESC
            LIMIT $2
            """,
            user_id,
            max(1, min(limit, 500)),
        )
        count = 0
        thresholds = await self._thresholds()
        for track in rows:
            await self.refresh_track(track["id"], thresholds=thresholds)
            count += 1
        return count

    async def refresh_all(self, *, limit: int = 500) -> int:
        rows = await self._pool.fetch(
            """
            SELECT id FROM stream_tracks
            WHERE publish_status = 'published'
            ORDER BY published_at DESC NULLS LAST, created_at DESC
            LIMIT $1
            """,
            max(1, min(limit, 2000)),
        )
        count = 0
        thresholds = await self._thresholds()
        for track in rows:
            await self.refresh_track(track["id"], thresholds=thresholds)
            count += 1
        return count

    async def list_creator(self, user_id: UUID | str) -> dict[str, Any]:
        rows = await self._pool.fetch(
            """
            SELECT e.*, t.title, t.origin, t.publish_status
            FROM creator_earning_eligibility e
            JOIN stream_tracks t ON t.id = e.track_id
            WHERE e.creator_id = $1
            ORDER BY e.updated_at DESC
            """,
            user_id,
        )
        items = [_row(row, row["title"]) for row in rows]
        eligible = sum(1 for item in items if item["status"] in {"eligible", "pending_verification"})
        earning = sum(1 for item in items if item["status"] == "earning")
        return {
            "items": items,
            "summary": {
                "tracks": len(items),
                "eligible": eligible,
                "earning": earning,
                "valid_streams": sum(int(item["valid_streams"] or 0) for item in items),
            },
        }


def _row(row: Any, title: str | None = None) -> dict[str, Any]:
    data = dict(row)
    if title is not None:
        data["title"] = title
    return data


async def run_creator_eligibility_loop(
    pool: Any,
    *,
    interval_seconds: int = _ELIGIBILITY_INTERVAL_SECONDS,
    startup_delay: float = 60.0,
) -> None:
    """Refresh track eligibility hourly and queue creator notifications."""
    if startup_delay:
        await asyncio.sleep(startup_delay)
    service = CreatorEligibilityService(pool)
    while True:
        try:
            refreshed = await service.refresh_all(limit=500)
            logger.info("Creator eligibility refresh completed for %s tracks.", refreshed)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Creator eligibility refresh failed; retrying next interval.")
        await asyncio.sleep(max(300, interval_seconds))
