#!/usr/bin/env python3
"""Diagnose sandbox auth: env, users, login."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r"""
echo '=== .env cors ==='
grep PLATFORM_CORS /opt/camxora/repo/platform_api/.env || echo missing
echo '=== signup-mode ==='
curl -s https://api.sandbox.camxora.com/api/v1/auth/signup-mode
echo
echo '=== users (sommakara/duke) ==='
sudo -u postgres psql -d camxora_platform -t -A -F'|' -c "SELECT email, role, email_confirmed, is_active FROM users WHERE email ILIKE '%sommakara%' OR email ILIKE '%duke@camxora%' ORDER BY email;"
echo '=== jwt secret set ==='
grep -q '^PLATFORM_JWT_SECRET=.\+' /opt/camxora/repo/platform_api/.env && echo yes || echo no
"""


def probe_login(email: str, password: str) -> None:
    body = json.dumps({"email": email, "password": password}).encode()
    for label, url in (
        ("direct", "https://api.sandbox.camxora.com/api/v1/auth/login"),
        ("app-proxy", "https://app.sandbox.camxora.com/api/v1/auth/login"),
        ("admin-proxy", "https://admin.sandbox.camxora.com/api/v1/auth/login"),
    ):
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Origin": "https://app.sandbox.camxora.com",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                print(f"{label}: OK {resp.status} {resp.read(300).decode()[:200]}")
        except urllib.error.HTTPError as exc:
            cors = exc.headers.get("Access-Control-Allow-Origin", "(none)")
            print(f"{label}: HTTP {exc.code} cors={cors} {exc.read(300).decode()[:200]}")


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    _, stdout, _ = client.exec_command(REMOTE)
    print(stdout.read().decode("utf-8", errors="replace"))
    client.close()

    email = secrets.get("SANDBOX_USER_EMAIL") or secrets.get("ADMIN_EMAIL") or "sommakara84@gmail.com"
    password = secrets.get("SANDBOX_USER_PASSWORD") or secrets.get("ADMIN_PASSWORD")
    print(f"\n=== Login probe for {email} ===")
    if password:
        probe_login(email, password)
    else:
        print("(no password in secrets — skipping real credential probe)")
        probe_login(email, "wrongpassword123")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
