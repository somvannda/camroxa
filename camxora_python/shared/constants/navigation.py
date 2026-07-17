"""Shell navigation — mirrors camxora/src/renderer/src/features/shell/shellNavigation.ts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ShellRouteKey = Literal[
    "home",
    "profile",
    "workflow",
    "progress",
    "music",
    "image",
    "video",
    "marketplace",
    "merger",
    "settings",
    "log",
]


@dataclass(frozen=True, slots=True)
class ShellRouteMeta:
    key: ShellRouteKey
    path: str
    label: str
    title: str
    eyebrow: str
    description: str
    is_placeholder: bool = False


SHELL_ROUTES: tuple[ShellRouteMeta, ...] = (
    ShellRouteMeta(
        key="home",
        path="/app/home",
        label="Dashboard",
        title="Dashboard",
        eyebrow="Workspace",
        description=(
            "Overview of the current CAMXORA account, profile readiness, and studio status."
        ),
    ),
    ShellRouteMeta(
        key="profile",
        path="/app/profile",
        label="Profile",
        title="Profile",
        eyebrow="Workspace",
        description=(
            "Signed-in account, plan, credits, allowance, and created channel profiles."
        ),
    ),
    ShellRouteMeta(
        key="workflow",
        path="/app/workflow",
        label="Workflow",
        title="Workflow",
        eyebrow="Workspace",
        description=(
            "Timeline view for the selected run and channel, driven by the shared "
            "progress aggregate feed."
        ),
    ),
    ShellRouteMeta(
        key="progress",
        path="/app/progress",
        label="Progress",
        title="Progress",
        eyebrow="Workspace",
        description=(
            "Progress monitoring surface with date filters, active-only mode, polling, "
            "and row-level pipeline status."
        ),
    ),
    ShellRouteMeta(
        key="music",
        path="/app/music",
        label="Music",
        title="Music",
        eyebrow="Workspace",
        description=(
            "Music workspace with batch composer, automation strip, song editor, "
            "and history table."
        ),
    ),
    ShellRouteMeta(
        key="image",
        path="/app/image",
        label="Image",
        title="Image",
        eyebrow="Workspace",
        description=(
            "Image workspace with live prompt generation, reference uploads, "
            "session results, and backend progress context."
        ),
    ),
    ShellRouteMeta(
        key="video",
        path="/app/video",
        label="Video",
        title="Video",
        eyebrow="Workspace",
        description=(
            "Video workspace with template loading, live GPU preview, domain editors, and export."
        ),
    ),
    ShellRouteMeta(
        key="marketplace",
        path="/app/marketplace",
        label="Marketplace",
        title="Marketplace",
        eyebrow="Workspace",
        description=(
            "Browse and install curated video templates from the marketplace catalog."
        ),
    ),
    ShellRouteMeta(
        key="merger",
        path="/app/merger",
        label="Merger",
        title="Merger",
        eyebrow="Reserved route",
        description="This route is reserved for later parity with the Python merger flow.",
        is_placeholder=True,
    ),
    ShellRouteMeta(
        key="settings",
        path="/app/settings",
        label="Settings",
        title="Settings",
        eyebrow="Workspace",
        description=(
            "Desktop-editable settings, local paths, and user preferences."
        ),
    ),
    ShellRouteMeta(
        key="log",
        path="/app/log",
        label="Log",
        title="Log",
        eyebrow="System",
        description=(
            "Runtime action log for this desktop session. Sync manually when you want "
            "support to review diagnostics in the admin portal."
        ),
        is_placeholder=False,
    ),
)

_DEFAULT_ROUTE = SHELL_ROUTES[0]


def get_route_by_key(key: ShellRouteKey) -> ShellRouteMeta:
    for route in SHELL_ROUTES:
        if route.key == key:
            return route
    return _DEFAULT_ROUTE


def get_workspace_routes() -> tuple[ShellRouteMeta, ...]:
    # Merger is reserved/placeholder — keep the route registered, hide from sidebar.
    return tuple(r for r in SHELL_ROUTES if r.key not in ("settings", "log", "merger"))


def get_utility_routes() -> tuple[ShellRouteMeta, ...]:
    return tuple(r for r in SHELL_ROUTES if r.key in ("settings", "log"))
