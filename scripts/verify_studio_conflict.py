"""Verify optimistic concurrency on the Studio project PATCH (W2.2).

1. log in, 2. read the project's updated_at, 3. PATCH with a stale expected_updated_at
and expect 409, 4. PATCH with the current one and expect 200.
"""

import json
import sys
import urllib.request
import urllib.error

API = "http://localhost:8100"
EMAIL = "somvannda@gmail.com"
PASSWORD = "StudioLocal!2026"


def call(path, method="GET", body=None, token=None, cookie=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else None, resp.headers
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        return exc.code, parsed, exc.headers


def main() -> int:
    status, payload, headers = call("/api/v3/auth/login", "POST", {"email": EMAIL, "password": PASSWORD})
    if status != 200:
        print("login failed", status, payload)
        return 1
    token = payload.get("access_token") or payload.get("token")
    cookie = None
    set_cookie = headers.get("set-cookie")
    if set_cookie:
        cookie = set_cookie.split(";")[0]

    status, projects, _ = call(
        "/api/v3/web-music/studio/projects?limit=5", token=token, cookie=cookie
    )
    if status != 200 or not projects:
        print("list failed", status, projects)
        return 1
    items = projects.get("items") if isinstance(projects, dict) else projects
    project = items[0]
    project_id = project["id"]
    updated_at = project.get("updated_at")
    print("project", project_id, "updated_at", updated_at)

    stale = "2000-01-01T00:00:00Z"
    status, body, _ = call(
        f"/api/v3/web-music/studio/projects/{project_id}",
        "PATCH",
        {"data": {"probe": "stale"}, "expected_updated_at": stale},
        token=token,
        cookie=cookie,
    )
    print("stale write ->", status, json.dumps(body)[:120])
    ok_conflict = status == 409

    status2, body2, _ = call(
        f"/api/v3/web-music/studio/projects/{project_id}",
        "PATCH",
        {"expected_updated_at": updated_at},
        token=token,
        cookie=cookie,
    )
    print("matching write ->", status2)
    ok_match = status2 == 200

    return 0 if (ok_conflict and ok_match) else 2


if __name__ == "__main__":
    sys.exit(main())
