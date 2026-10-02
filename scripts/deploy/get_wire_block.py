#!/usr/bin/env python3
"""Download prod wire_dependencies.py WebMusicService build block (lines ~600-635)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / ".dbg" / "live-probe" / "wire_dependencies.section.py"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

REMOTE_CMD = r"""
set -e
sed -n '595,635p' /opt/camxora/repo/platform_api/wire_dependencies.py
echo SECTION_END
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=60)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1000:] + "\n")
        LOCAL.parent.mkdir(parents=True, exist_ok=True)
        LOCAL.write_text(out, encoding="utf-8")
        print(f"Saved to {LOCAL}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
