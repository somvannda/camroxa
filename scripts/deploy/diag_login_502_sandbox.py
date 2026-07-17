#!/usr/bin/env python3
"""Diagnose auth/login 502 on sandbox."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

APP_API = "https://app.sandbox.camxora.com/api/v1"
DIRECT_API = "https://api.sandbox.camxora.com/api/v1"


def probe(url: str, body: dict) -> None:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "X-Portal-Context": "user"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"OK {url} -> {resp.status} {resp.read(500).decode()[:300]}")
    except urllib.error.HTTPError as exc:
        print(f"HTTP {url} -> {exc.code} {exc.read(500).decode()[:300]}")
    except Exception as exc:
        print(f"ERR {url} -> {type(exc).__name__}: {exc}")


def main() -> int:
    print("=== External probes ===")
    probe(f"{APP_API}/auth/login", {"email": "probe@test.com", "password": "wrong"})
    probe(f"{DIRECT_API}/auth/login", {"email": "probe@test.com", "password": "wrong"})

    print("\n=== SSH service health ===")
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    ssh_cmd = r"""
set -e
echo '--- systemd ---'
systemctl is-active camxora-api camxora-portal nginx || true
systemctl status camxora-api --no-pager -l | head -25
echo '--- local upstream ---'
curl -s -o /dev/null -w '127.0.0.1:8100 health %{http_code}\n' http://127.0.0.1:8100/health || echo health_failed
curl -s -o /dev/null -w '127.0.0.1:8100 login %{http_code}\n' -X POST http://127.0.0.1:8100/api/v1/auth/login \
  -H 'Content-Type: application/json' -d '{"email":"probe@test.com","password":"wrong"}' || echo login_failed
echo '--- nginx error (last 30) ---'
tail -30 /var/log/nginx/error.log 2>/dev/null || journalctl -u nginx -n 30 --no-pager
echo '--- api journal (last 60) ---'
journalctl -u camxora-api -n 60 --no-pager
"""
    _, stdout, stderr = client.exec_command(ssh_cmd, get_pty=True)
    data = stdout.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(data.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("SSH stderr:", err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
