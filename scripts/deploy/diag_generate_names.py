#!/usr/bin/env python3
"""Diagnose channel-setup 401/502 on sandbox."""

from __future__ import annotations

import json
import os
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
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Portal-Context": "user"}
    req = urllib.request.Request(f"{APP_API}{path}", data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    try:
        with opener.open(req, timeout=60) as resp:
            return resp.status, resp.read(4000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(4000).decode("utf-8", errors="replace")


def main() -> int:
    print("=== Recent API logs (channel-setup / generate-names) ===")
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    cmd = """
journalctl -u camxora-api --since '45 min ago' --no-pager | grep -iE 'generate-names|generate_names|channel-setup|channel_setup|401|502|ExternalService|Unauthorized|deepseek|openai|api_key' | tail -40
echo '--- api keys configured ---'
sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && /opt/camxora/repo/platform_api/.venv/bin/python - <<"PY"
import asyncio, asyncpg, os
async def main():
    dsn=os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://","postgresql://",1)
    conn=await asyncpg.connect(dsn)
    rows=await conn.fetch("SELECT provider, label, status FROM api_key_entries ORDER BY provider, label")
    for r in rows:
        print(dict(r))
    row=await conn.fetchrow("SELECT value FROM system_settings WHERE key=$1","ai.routing.assignments")
    print("ai.routing.assignments", (row["value"][:300] + "...") if row and len(row["value"]) > 300 else (row["value"] if row else None))
    cp=await conn.fetchrow("SELECT COUNT(*) AS c FROM channel_prompts WHERE category=$1 AND is_active=true","title")
    print("active title prompts", cp["c"] if cp else 0)
    await conn.close()
asyncio.run(main())
PY'
"""
    _, stdout, _ = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    client.close()

    print("\n=== HTTP probe (somvannda) ===")
    jar = CookieJar()
    for path in ["/users/me", "/channel-setup/draft", "/channel-setup/onboarding-ai-status"]:
        code, body = request(path, jar=jar)
        print(f"unauthenticated {path}: {code} {body[:120]}")

    code, body = request(
        "/auth/login",
        method="POST",
        body={"email": os.environ.get("CAMXORA_ADMIN_EMAIL", "somvannda@gmail.com"), "password": os.environ["CAMXORA_ADMIN_PASSWORD"]},
        jar=jar,
    )
    print(f"\nlogin: {code}")
    if code != 200:
        print(body[:500])
        return 1

    for path in ["/users/me", "/channel-setup/draft", "/channel-setup/onboarding-ai-status"]:
        code, body = request(path, jar=jar)
        print(f"{path}: {code} {body[:200]}")

    code, body = request(
        "/channel-setup/generate-names",
        method="POST",
        body={
            "genre": "Pop",
            "match_key": "pop",
            "role": "primary",
            "count": 3,
            "description": "",
        },
        jar=jar,
    )
    print(f"\ngenerate-names: {code}")
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
