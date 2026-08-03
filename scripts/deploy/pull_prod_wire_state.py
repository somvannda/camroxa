#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".dbg"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    sftp = client.open_sftp()
    pulls = (
        ("/opt/camxora/repo/platform_api/wire_dependencies.py", OUT / "prod_live_wire_dependencies.py"),
        ("/opt/camxora/repo/platform_api/dependencies.py", OUT / "prod_live_dependencies.py"),
        ("/opt/camxora/repo/platform_api/routers/youtube.py", OUT / "prod_live_youtube.py"),
        ("/opt/camxora/repo/platform_api/routers/admin.py", OUT / "prod_live_admin.py"),
    )
    for remote, local in pulls:
        print(f"Pull {remote}")
        sftp.get(remote, str(local))
    sftp.close()
    # Also list what youtube exports for job queue
    cmd = r"""
rg -n '_get_job_queue|provider_key|wire_all' /opt/camxora/repo/platform_api/wire_dependencies.py /opt/camxora/repo/platform_api/routers/youtube.py 2>/dev/null | head -40
# find last good backup if any
ls -la /opt/camxora/repo/platform_api/wire_dependencies.py* 2>/dev/null | head -20
ls /opt/camxora/backups 2>/dev/null | head -10
find /opt/camxora -name 'wire_dependencies.py*' 2>/dev/null | head -20
"""
    _, stdout, _ = client.exec_command(cmd, get_pty=True)
    print(stdout.read().decode("utf-8", errors="replace"))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
