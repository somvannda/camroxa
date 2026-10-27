"""Studio release smoke checks that do not spend Suno credits.

Usage:
    set CAMXORA_WEB_URL=http://localhost:3103
    set CAMXORA_TEST_EMAIL=...
    set CAMXORA_TEST_PASSWORD=...
    python scripts/studio_release_checks.py --allow-not-ready

The script logs in with Playwright, then exercises project, share, comment,
presence, long-poll and cleanup routes through the browser session. It creates
a temporary project and deletes it in a finally block. It never calls a Suno
generation/edit route.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-not-ready", action="store_true")
    args = parser.parse_args()

    web_url = os.getenv("CAMXORA_WEB_URL", "http://localhost:3103").rstrip("/")
    email = os.getenv("CAMXORA_TEST_EMAIL", "").strip()
    password = os.getenv("CAMXORA_TEST_PASSWORD", "").strip()
    if not email or not password:
        print("CAMXORA_TEST_EMAIL and CAMXORA_TEST_PASSWORD are required.", file=sys.stderr)
        return 2

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    project_id: str | None = None
    copy_id: str | None = None

    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def api(
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        payload = None if body is None else json.dumps(body)
        result = page.evaluate(
            """async ({ method, path, payload }) => {
                const response = await fetch(path, {
                    method,
                    credentials: 'include',
                    headers: payload ? { 'Content-Type': 'application/json' } : {},
                    body: payload || undefined,
                });
                const text = await response.text();
                let body = null;
                try { body = text ? JSON.parse(text) : null; } catch { body = text; }
                return { status: response.status, body };
            }""",
            {"method": method, "path": path, "payload": payload},
        )
        return int(result["status"]), result["body"]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        try:
            page.goto(f"{web_url}/login", wait_until="networkidle")
            page.fill("#email", email)
            page.fill("#password", password)
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_timeout(1800)

            status, readiness = api("GET", "/api/v3/web-music/studio/readiness")
            add("readiness", status == 200, readiness)
            if isinstance(readiness, dict) and not readiness.get("ready"):
                blockers.append(
                    "readiness false: "
                    + json.dumps(readiness.get("checks", {}), sort_keys=True)
                )

            status, projects = api("GET", "/api/v3/web-music/studio/projects?limit=5")
            add("project list", status == 200, status)

            status, project = api(
                "POST",
                "/api/v3/web-music/studio/projects",
                {
                    "title": "Release Check",
                    "major_version": 2,
                    "bpm": 120,
                    "time_signature": "4/4",
                    "data": {
                        "lanes": [],
                        "groups": [],
                        "markers": [],
                    },
                },
            )
            project_id = str((project or {}).get("id") or "")
            add("project create", status == 201 and bool(project_id), status)

            if project_id:
                status, updated = api(
                    "PATCH",
                    f"/api/v3/web-music/studio/projects/{project_id}",
                    {
                        "pinned": True,
                        "tags": ["release", "smoke"],
                    },
                )
                add(
                    "project pin/tags",
                    status == 200
                    and isinstance(updated, dict)
                    and updated.get("pinned") is True
                    and updated.get("tags") == ["release", "smoke"],
                    status,
                )

                status, archived = api(
                    "PATCH",
                    f"/api/v3/web-music/studio/projects/{project_id}",
                    {"archived": True},
                )
                add(
                    "project archive",
                    status == 200
                    and isinstance(archived, dict)
                    and archived.get("archived") is True,
                    status,
                )
                api(
                    "PATCH",
                    f"/api/v3/web-music/studio/projects/{project_id}",
                    {"archived": False},
                )

                status, copy = api(
                    "POST",
                    f"/api/v3/web-music/studio/projects/{project_id}/fork",
                    {"title": "Release Check Copy"},
                )
                copy_id = str((copy or {}).get("id") or "")
                add("project duplicate", status == 201 and bool(copy_id), status)

                status, view_share = api(
                    "POST",
                    f"/api/v3/web-music/studio/projects/{project_id}/shares",
                    {"expires_days": 1, "permission": "view"},
                )
                view_token = str((view_share or {}).get("token") or "")
                add("share create", status == 201 and bool(view_token), status)

                status, share_list = api(
                    "GET",
                    f"/api/v3/web-music/studio/projects/{project_id}/shares",
                )
                add(
                    "share list",
                    status == 200
                    and bool((share_list or {}).get("items")),
                    status,
                )

                parent_id = None
                if view_token:
                    status, comment = api(
                        "POST",
                        f"/api/v3/web-music/studio/shares/{view_token}/comments",
                        {
                            "author_name": "Release Check",
                            "body": "Top-level release check",
                        },
                    )
                    parent_id = str((comment or {}).get("id") or "")
                    add("comment create", status == 201 and bool(parent_id), status)

                    if parent_id:
                        status, reply = api(
                            "POST",
                            f"/api/v3/web-music/studio/shares/{view_token}/comments",
                            {
                                "author_name": "Release Check",
                                "body": "Nested release check",
                                "parent_id": parent_id,
                            },
                        )
                        add(
                            "comment reply",
                            status == 201
                            and isinstance(reply, dict)
                            and reply.get("parent_id") == parent_id,
                            status,
                        )

                    status, comments = api(
                        "GET",
                        f"/api/v3/web-music/studio/shares/{view_token}/comments",
                    )
                    add(
                        "comment list",
                        status == 200
                        and len((comments or {}).get("items") or []) >= 2,
                        status,
                    )

                status, edit_share = api(
                    "POST",
                    f"/api/v3/web-music/studio/projects/{project_id}/shares",
                    {"expires_days": 1, "permission": "edit"},
                )
                edit_token = str((edit_share or {}).get("token") or "")
                add("edit share create", status == 201 and bool(edit_token), status)

                if edit_token:
                    status, presence = api(
                        "POST",
                        f"/api/v3/web-music/studio/shares/{edit_token}/presence",
                        {
                            "display_name": "Release Check",
                            "playhead_seconds": 12.5,
                            "selected_lane_id": "release-lane",
                        },
                    )
                    items = (presence or {}).get("items") or []
                    add(
                        "presence",
                        status == 200
                        and bool(items)
                        and items[0].get("playhead_seconds") == 12.5,
                        status,
                    )

                    old_since = "2020-01-01T00:00:00Z"
                    status, update = api(
                        "GET",
                        f"/api/v3/web-music/studio/shares/{edit_token}/updates?since={old_since}&timeout=1",
                    )
                    add(
                        "long poll",
                        status == 200 and bool((update or {}).get("changed")),
                        status,
                    )

                status, public = api(
                    "GET",
                    f"/api/v3/web-music/studio/shares/{view_token}",
                ) if view_token else (0, None)
                add("public share page", status == 200, status)

                status, latest_shares = api(
                    "GET",
                    f"/api/v3/web-music/studio/projects/{project_id}/shares",
                )
                if status == 200 and isinstance(latest_shares, dict):
                    for item in latest_shares.get("items") or []:
                        if item.get("active"):
                            api(
                                "DELETE",
                                f"/api/v3/web-music/studio/projects/{project_id}/shares/{item['id']}",
                            )

                status, _ = api(
                    "GET",
                    f"/api/v3/web-music/studio/shares/{view_token}",
                ) if view_token else (0, None)
                add("revoked share rejected", status == 404, status)

                status, _ = api(
                    "DELETE",
                    f"/api/v3/web-music/studio/projects/{project_id}",
                )
                add("project cleanup", status == 204, status)
                project_id = None

            if copy_id:
                api("DELETE", f"/api/v3/web-music/studio/projects/{copy_id}")
                copy_id = None
        except Exception as exc:  # noqa: BLE001
            add("unexpected error", False, str(exc))
        finally:
            if project_id:
                api("DELETE", f"/api/v3/web-music/studio/projects/{project_id}")
            if copy_id:
                api("DELETE", f"/api/v3/web-music/studio/projects/{copy_id}")
            context.close()
            browser.close()

    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({"checks": checks, "blockers": blockers}, indent=2))
    if failed:
        print(f"\n{len(failed)} check(s) failed.", file=sys.stderr)
        return 1
    if blockers and not args.allow_not_ready:
        print("\nReadiness blockers prevent release.", file=sys.stderr)
        return 3
    print("\nAll non-Suno release checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
