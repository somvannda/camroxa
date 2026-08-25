"""Smoke-check all Camxora sandbox surfaces for HTTP / API errors."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402


@dataclass
class Check:
    name: str
    url: str
    method: str = "GET"
    body: bytes | None = None
    headers: dict[str, str] | None = None
    ok_codes: tuple[int, ...] = (200,)
    expect_substr: str | None = None


CHECKS: list[Check] = [
    # Platform API
    Check("api.health", "https://api.sandbox.camxora.com/health"),
    Check("api.v3.health", "https://api.sandbox.camxora.com/api/v3/health", ok_codes=(200, 404)),
    Check("api.v3.plans.public", "https://api.sandbox.camxora.com/api/v3/plans/public"),
    Check("api.v3.subscriptions.plans", "https://api.sandbox.camxora.com/api/v3/subscriptions/plans"),
    Check("api.v3.webhooks.cutluy.health", "https://api.sandbox.camxora.com/api/v3/webhooks/cutluy/health"),
    Check(
        "api.v3.billing.webhooks.cutluy.health",
        "https://api.sandbox.camxora.com/api/v3/billing/webhooks/cutluy/health",
        ok_codes=(200, 404),
    ),
    Check(
        "api.v3.streaming.home",
        "https://api.sandbox.camxora.com/api/v3/public/streaming/home",
    ),
    Check(
        "api.v3.me.credits.unauth",
        "https://api.sandbox.camxora.com/api/v3/me/credits",
        ok_codes=(401,),
    ),
    # Music web (HTML + proxied API)
    Check("music.html", "https://music.sandbox.camxora.com/", expect_substr="html"),
    Check(
        "music.proxy.plans",
        "https://music.sandbox.camxora.com/api/v3/subscriptions/plans",
    ),
    Check(
        "music.proxy.streaming.home",
        "https://music.sandbox.camxora.com/api/v3/public/streaming/home",
    ),
    Check(
        "music.proxy.me.credits.unauth",
        "https://music.sandbox.camxora.com/api/v3/me/credits",
        ok_codes=(401,),
    ),
    # Website
    Check("website.html", "https://sandbox.camxora.com/", expect_substr="html"),
    Check("website.pricing", "https://sandbox.camxora.com/pricing", expect_substr="html"),
    # User portal
    Check("portal.html", "https://app.sandbox.camxora.com/", expect_substr="html"),
    Check(
        "portal.proxy.plans",
        "https://app.sandbox.camxora.com/api/v3/plans/public",
    ),
    # Admin
    Check("admin.html", "https://admin.sandbox.camxora.com/", expect_substr="html"),
    Check(
        "admin.assets.index",
        "https://admin.sandbox.camxora.com/assets/",
        ok_codes=(200, 403, 404),
    ),
]


def hit(check: Check) -> tuple[bool, str]:
    req = urllib.request.Request(check.url, method=check.method, data=check.body)
    for k, v in (check.headers or {}).items():
        req.add_header(k, v)
    if check.body is not None and "Content-Type" not in (check.headers or {}):
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            code = resp.status
            ok = code in check.ok_codes
            if ok and check.expect_substr and check.expect_substr.lower() not in body[:800].lower():
                return False, f"{code} missing substr {check.expect_substr!r}: {body[:180]!r}"
            return ok, f"{code} {body[:180].replace(chr(10), ' ')}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        ok = exc.code in check.ok_codes
        return ok, f"{exc.code} {body[:220].replace(chr(10), ' ')}"
    except Exception as exc:  # noqa: BLE001
        return False, f"ERR {type(exc).__name__}: {exc}"


REMOTE_AUTH = r'''
import asyncio, asyncpg, jwt, urllib.request, urllib.error, json
from datetime import datetime, timedelta, timezone
from platform_api.config import get_settings
from platform_api.dependencies import set_db_pool

async def main():
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    set_db_pool(pool)
    row = await pool.fetchrow(
        "SELECT id, email, role, token_version FROM users WHERE email=$1",
        "duke@test.com",
    )
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "user_id": str(row["id"]),
            "email": row["email"],
            "role": row["role"] or "user",
            "token_version": int(row["token_version"] or 0),
            "type": "access",
            "iat": now,
            "exp": now + timedelta(hours=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    if isinstance(token, bytes):
        token = token.decode()

    paths = [
        ("api", "https://api.sandbox.camxora.com", "/api/v3/users/me"),
        ("api", "https://api.sandbox.camxora.com", "/api/v3/me/credits"),
        ("api", "https://api.sandbox.camxora.com", "/api/v3/web-music/quota"),
        ("api", "https://api.sandbox.camxora.com", "/api/v3/streaming/library/likes/ids"),
        ("api", "https://api.sandbox.camxora.com", "/api/v3/credits/balance"),
        ("music", "https://music.sandbox.camxora.com", "/api/v3/me/credits"),
        ("music", "https://music.sandbox.camxora.com", "/api/v3/web-music/quota"),
        ("portal", "https://app.sandbox.camxora.com", "/api/v3/users/me"),
        ("portal", "https://app.sandbox.camxora.com", "/api/v3/me/credits"),
    ]
    for label, base, path in paths:
        req = urllib.request.Request(
            base + path,
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                print(f"OK {resp.status} {label} {path} {body[:140].replace(chr(10),' ')}")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            print(f"FAIL {exc.code} {label} {path} {body[:280].replace(chr(10),' ')}")

    # admin user if exists
    admin = await pool.fetchrow(
        "SELECT id, email, role, token_version FROM users WHERE role IN ('admin','superadmin') ORDER BY created_at NULL LIMIT 1"
    )
    if admin:
        at = jwt.encode(
            {
                "user_id": str(admin["id"]),
                "email": admin["email"],
                "role": admin["role"] or "admin",
                "token_version": int(admin["token_version"] or 0),
                "type": "access",
                "iat": now,
                "exp": now + timedelta(hours=1),
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        if isinstance(at, bytes):
            at = at.decode()
        for path in (
            "/api/v3/admin/dashboard/summary",
            "/api/v3/admin/plans",
            "/api/v3/admin/users?limit=5&offset=0",
            "/api/v3/admin/settings",
            "/api/v3/admin/subscriptions/plans",
        ):
            req = urllib.request.Request(
                "https://api.sandbox.camxora.com" + path,
                headers={"Authorization": f"Bearer {at}"},
                method="GET",
            )
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                    print(f"OK {resp.status} admin {path} {body[:140].replace(chr(10),' ')}")
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                print(f"FAIL {exc.code} admin {path} {body[:280].replace(chr(10),' ')}")
    else:
        print("NO_ADMIN_USER")

    import subprocess
    print("ALEMBIC", subprocess.check_output(
        ["sudo","-u","postgres","psql","-d","camxora_platform","-t","-A","-c","SELECT version_num FROM alembic_version;"],
        text=True,
    ).strip())
    print("JOURNAL")
    print(subprocess.check_output(
        ["bash","-lc","journalctl -u camxora-api.service --since '30 min ago' --no-pager | grep -E 'ERROR|Traceback|INTERNAL| 500 ' | tail -n 40"],
        text=True, errors="replace",
    ))
    await pool.close()

asyncio.run(main())
'''


def main() -> int:
    print("=== PUBLIC CHECKS ===")
    fails = 0
    for check in CHECKS:
        ok, detail = hit(check)
        mark = "OK" if ok else "FAIL"
        if not ok:
            fails += 1
        print(f"{mark} {check.name}: {detail}")

    print("\n=== AUTHENTICATED + JOURNAL (SSH) ===")
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/sandbox_all_platforms_probe.py", "w") as remote:
            remote.write(REMOTE_AUTH)
        sftp.close()
        cmd = (
            "cd /opt/camxora/repo && source platform_api/.venv/bin/activate && "
            "PYTHONPATH=/opt/camxora/repo python /tmp/sandbox_all_platforms_probe.py"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        print(out)
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print("STDERR", err[-2000:])
        if "FAIL " in out:
            fails += out.count("FAIL ")
    finally:
        client.close()

    print(f"\nTOTAL_FAIL_MARKERS={fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
