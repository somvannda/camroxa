#!/usr/bin/env python3
"""Probe billing payment endpoint on sandbox."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

PAYMENT_ID = "482de7df-b6e5-4812-abfa-88beb8f9422a"
APP_API = "https://app.sandbox.camxora.com/api/v1"

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def request(path: str, *, method: str = "GET", body: dict | None = None, jar: CookieJar) -> tuple[int, str]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Portal-Context": "user"}
    req = urllib.request.Request(f"{APP_API}{path}", data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    try:
        with opener.open(req, timeout=30) as resp:
            return resp.status, resp.read(4000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(4000).decode("utf-8", errors="replace")


def main() -> int:
    print("=== Recent API errors ===")
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    cmd = """
journalctl -u camxora-api --since '30 min ago' --no-pager | tail -120
"""
    _, stdout, _ = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    client.close()

    print("\n=== HTTP probe ===")
    jar = CookieJar()
    code, body = request(
        "/auth/login",
        method="POST",
        body={"email": os.environ.get("CAMXORA_ADMIN_EMAIL", "somvannda@gmail.com"), "password": os.environ["CAMXORA_ADMIN_PASSWORD"]},
        jar=jar,
    )
    print(f"login: {code}")
    if code != 200:
        print(body[:500])
        return 1

    code, body = request(f"/billing/payments/{PAYMENT_ID}", jar=jar)
    print(f"GET payment: {code}")
    print(body)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
