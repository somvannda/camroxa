"""Paid-plan gate for the desktop studio client."""

from __future__ import annotations

from typing import Any

from starlette.requests import Request

from platform_api.exceptions import DesktopPlanRequiredError

DESKTOP_CLIENT_HEADER = "x-camxora-client"
DESKTOP_CLIENT_VALUE = "desktop"
DESKTOP_PLAN_REQUIRED_MESSAGE = (
    "Desktop studio requires a paid plan. Choose Starter, Creator, or Studio on the web."
)


def is_desktop_client(request: Request) -> bool:
    value = (request.headers.get(DESKTOP_CLIENT_HEADER) or "").strip().lower()
    return value == DESKTOP_CLIENT_VALUE


async def assert_paid_desktop_access(user_id: str, license_repo: Any) -> None:
    if not await license_repo.has_paid_desktop_access(str(user_id)):
        raise DesktopPlanRequiredError(DESKTOP_PLAN_REQUIRED_MESSAGE)
