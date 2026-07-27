#!/usr/bin/env python3
"""File-scoped production hotfix: album thumbnail source_job_id race remap only.

Allowlisted paths only — does not sync DistroKid or other WIP from a mixed tree.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FILE_REPO = Path(os.environ.get("CAMXORA_HOTFIX_REPO") or SCRIPT_DIR.parents[1])
_PRIMARY = Path(r"D:\Development\Projects\Electron\MusicGenerator")
_DEPLOY_CANDIDATES = [SCRIPT_DIR, _PRIMARY / "scripts" / "deploy"]
for candidate in _DEPLOY_CANDIDATES:
    venv_site = candidate / ".venv" / "Lib" / "site-packages"
    if venv_site.is_dir():
        sys.path.insert(0, str(venv_site))
    if (candidate / "deploy.py").is_file():
        sys.path.insert(0, str(candidate))
        break

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

FILES = [
    "platform_api/repositories/batch_repo.py",
]


def _run(client, cmd: str, timeout: int = 120) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = (out + ("\n" + err if err.strip() else "")).strip()
    return code, text.encode("ascii", errors="replace").decode("ascii")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    print(f"Target production host: {host}")
    print(f"File source repo: {FILE_REPO}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = FILE_REPO / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel}"
            print(f"Uploading {rel} ...")
            parent = str(Path(remote).parent).replace("\\", "/")
            client.exec_command(f"mkdir -p {parent}")
            sftp.put(str(local), remote)
        sftp.close()

        code, out = _run(
            client,
            "chown camxora:camxora /opt/camxora/repo/platform_api/repositories/batch_repo.py"
            " && grep -n background_id_remap /opt/camxora/repo/platform_api/repositories/batch_repo.py | head -3"
            " && systemctl restart camxora-api && sleep 2 && systemctl is-active camxora-api"
            " && echo API_HOTFIX_OK",
            timeout=60,
        )
        print(out)
        print(f"exit={code}")
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
