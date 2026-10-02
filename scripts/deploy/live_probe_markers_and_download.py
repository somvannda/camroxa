#!/usr/bin/env python3
"""Live-prod marker audit + download current running files (router + service)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
R_REMOTE = "/opt/camxora/repo/platform_api/routers/web_music.py"
S_REMOTE = "/opt/camxora/repo/platform_api/services/web_music_service.py"
R_LOCAL = ROOT / ".dbg" / "live-probe" / "web_music.py"
S_LOCAL = ROOT / ".dbg" / "live-probe" / "web_music_service.py"

REMOTE_CMD = (
    "REPO=/opt/camxora/repo/platform_api\n"
    "echo '=== ROUTER MARKERS ==='\n"
    "echo '--- /generate called ---'\n"
    f"grep -n 'web-music /generate called' {R_REMOTE} || echo MISSING\n"
    "echo '--- /generate failed ---'\n"
    f"grep -n 'web-music /generate failed' {R_REMOTE} || echo MISSING\n"
    "echo '--- /generate-styles failed ---'\n"
    f"grep -n 'generate-styles failed' {R_REMOTE} || echo MISSING\n"
    "echo '--- paid netcap guard ---'\n"
    f"grep -n '_has_web_subscription(UUID(ctx.user_id))' {R_REMOTE} || echo MISSING\n"
    "echo '=== SERVICE MARKERS ==='\n"
    "echo '--- text-assist LLM failed log ---'\n"
    f"grep -n 'text-assist LLM failed' {S_REMOTE} || echo MISSING\n"
    "echo '--- http_paths import shim ---'\n"
    f"grep -n 'except ImportError:' {S_REMOTE} || echo MISSING\n"
    "echo '--- service logger id ---'\n"
    f"sed -n '55,62p' {S_REMOTE}\n"
    "echo 'MARKERS_DONE'\n"
)


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== live probe + download -> {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1000:] + "\n")
        if "MARKERS_DONE" not in out:
            return 1

        R_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        sftp = client.open_sftp()
        with sftp.file(R_REMOTE, "rb") as rf:
            R_LOCAL.write_bytes(rf.read())
        with sftp.file(S_REMOTE, "rb") as rf:
            S_LOCAL.write_bytes(rf.read())
        sftp.close()
        print(f"Downloaded current running router: {R_LOCAL}")
        print(f"Downloaded current running service: {S_LOCAL}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
