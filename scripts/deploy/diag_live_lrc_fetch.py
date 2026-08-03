#!/usr/bin/env python3
"""Upload and run remote_live_lrc_fetch.py on production."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
LOCAL = DEPLOY / "remote_live_lrc_fetch.py"


def load_env(name: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    pr = load_env("secrets.production.env")
    host = pr.get("PRODUCTION_VPS_HOST") or pr["VPS_HOST"]
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(
        host,
        pr.get("PRODUCTION_VPS_USER") or pr["VPS_USER"],
        ensure_deploy_key(),
        pr.get("PRODUCTION_VPS_PASSWORD") or pr.get("VPS_PASSWORD"),
    )
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/remote_live_lrc_fetch.py", "wb") as rf:
            rf.write(LOCAL.read_bytes())
        sftp.close()
        cmd = (
            "set -a; . /opt/camxora/repo/platform_api/.env; set +a; "
            "cd /opt/camxora/repo && "
            "PYTHONPATH=/opt/camxora/repo "
            "/opt/camxora/repo/platform_api/.venv/bin/python "
            "/tmp/remote_live_lrc_fetch.py"
        )
        _, stdout, stderr = client.exec_command(cmd, timeout=120)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
