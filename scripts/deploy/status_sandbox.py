#!/usr/bin/env python3
"""Quick sandbox status check via SSH + HTTPS."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def https_get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read(500).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read(500).decode("utf-8", errors="replace")
        return exc.code, body


def https_head_location(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.headers.get("Location", "")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Location", "")


def main() -> int:
    print("=== HTTPS checks ===")
    for label, url in [
        ("signup", "https://app.sandbox.camxora.com/signup"),
        ("register", "https://app.sandbox.camxora.com/register"),
        ("login page", "https://app.sandbox.camxora.com/login"),
        ("admin", "https://admin.sandbox.camxora.com/"),
        ("signup-mode", "https://api.sandbox.camxora.com/api/v1/auth/signup-mode"),
    ]:
        code, extra = https_head_location(url) if label == "signup" else (0, "")
        if label == "signup":
            print(f"{label}: HTTP {code} -> {extra or '(no redirect)'}")
        else:
            status, body = https_get(url)
            snippet = body[:120].replace("\n", " ")
            print(f"{label}: HTTP {status} {snippet}")

    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    cmd = r"""
systemctl is-active camxora-api camxora-portal camxora-website camxora-admin camxora-music 2>&1
echo ---
curl -sI http://127.0.0.1:3101/register | head -3
echo ---
curl -sI http://127.0.0.1:3101/login | head -3
echo ---
python3 <<'PY'
import json
from pathlib import Path
p = Path('/opt/camxora/repo/user_portal/.next/app-path-routes-manifest.json')
print(p.read_text() if p.is_file() else 'missing manifest')
PY
echo ---
curl -s -o /dev/null -w 'login:%{http_code}\n' -X POST http://127.0.0.1:8100/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"duke@camxora.com","password":"__CAMXORA_ADMIN_PASSWORD__"}'
"""
    cmd = cmd.replace("__CAMXORA_ADMIN_PASSWORD__", os.environ.get("CAMXORA_ADMIN_PASSWORD", ""))
    _, stdout, _ = client.exec_command(cmd)
    print("\n=== SSH checks ===")
    print(stdout.read().decode("utf-8", errors="replace"))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
