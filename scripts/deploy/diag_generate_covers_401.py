#!/usr/bin/env python3
"""Diagnose generate-covers 401 on sandbox."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

APP_API = "https://app.sandbox.camxora.com/api/v1"


def request(
    path: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    jar: CookieJar,
) -> tuple[int, str]:
    url = f"{APP_API}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Portal-Context": "user"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    try:
        with opener.open(req, timeout=120) as resp:
            return resp.status, resp.read(500).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(500).decode("utf-8", errors="replace")


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    cmd = r"""
echo '--- user_portal .env.production ---'
cat /opt/camxora/repo/user_portal/.env.production 2>/dev/null || echo missing
echo '--- recent auth errors ---'
journalctl -u camxora-api -n 150 --no-pager | grep -iE '401|Authentication|Missing authorization|generate-cover' | tail -25
"""
    _, stdout, _ = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    client.close()

    email = "somvannda@gmail.com"
    password = secrets.get("SANDBOX_TEST_PASSWORD") or secrets.get("ADMIN_PASSWORD") or ""
    if not password:
        print("\nNo SANDBOX_TEST_PASSWORD in secrets — skipping live auth probe.")
        return 0

    jar = CookieJar()
    code, body = request(
        "/auth/login",
        method="POST",
        body={"email": email, "password": password},
        jar=jar,
    )
    print(f"\nlogin: {code} {body[:200]}")
    if code != 200:
        return 1

    for path in ["/users/me", "/channel-setup/draft"]:
        c, b = request(path, jar=jar)
        print(f"{path}: {c} {b[:180]}")

    c, b = request(
        "/channel-setup/generate-covers",
        method="POST",
        body={
            "channel_name": "Bass Drive",
            "genre": "EDM / Workout Gym",
            "role": "primary",
            "match_key": "EDM / Workout Gym",
            "count": 1,
        },
        jar=jar,
    )
    print(f"generate-covers (fresh session): {c} {b[:300]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
