"""HTTP client for Platform API dashboard stats endpoint.

Provides a simple client to fetch aggregated dashboard statistics.
Designed to be called from worker threads (not the Qt main thread).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass(frozen=True)
class DailyUsage:
    date: str = ""
    songs: int = 0
    images: int = 0
    videos: int = 0


@dataclass(frozen=True)
class RecentActivity:
    timestamp: str = ""
    kind: str = ""
    detail: str = ""
    status: str = ""


@dataclass(frozen=True)
class DashboardStats:
    credits_spent: int = 0
    credits_remaining: int = 0
    credits_total: int = 0
    songs_generated: int = 0
    songs_remaining: int | None = None
    songs_quota: int | None = None
    images_generated: int = 0
    videos_generated: int = 0
    usage_by_day: list[DailyUsage] = field(default_factory=list)
    recent_activity: list[RecentActivity] = field(default_factory=list)


class StatsClient:
    """Client for fetching dashboard stats from the Platform API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/api/v1",
        timeout: float = 15.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout)

    def get_dashboard_stats(self, access_token: str) -> DashboardStats:
        """Fetch dashboard statistics for the authenticated user."""
        response = self._client.get(
            "/stats/dashboard",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        data = response.json()

        usage_by_day = [
            DailyUsage(
                date=d.get("date", ""),
                songs=d.get("songs", 0),
                images=d.get("images", 0),
                videos=d.get("videos", 0),
            )
            for d in data.get("usage_by_day", [])
        ]

        recent_activity = [
            RecentActivity(
                timestamp=a.get("timestamp", ""),
                kind=a.get("kind", ""),
                detail=a.get("detail", ""),
                status=a.get("status", ""),
            )
            for a in data.get("recent_activity", [])
        ]

        return DashboardStats(
            credits_spent=data.get("credits_spent", 0),
            credits_remaining=data.get("credits_remaining", 0),
            credits_total=data.get("credits_total", 0),
            songs_generated=data.get("songs_generated", 0),
            songs_remaining=data.get("songs_remaining"),
            songs_quota=data.get("songs_quota"),
            images_generated=data.get("images_generated", 0),
            videos_generated=data.get("videos_generated", 0),
            usage_by_day=usage_by_day,
            recent_activity=recent_activity,
        )

    def close(self) -> None:
        self._client.close()
