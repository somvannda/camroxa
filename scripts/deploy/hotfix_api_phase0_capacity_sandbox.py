#!/usr/bin/env python3
"""Phase 0 capacity: deploy API pool/progress fixes + set uvicorn workers=4 (sandbox)."""
from __future__ import annotations

import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

FILES = [
    "platform_api/main.py",
    "platform_api/routers/progress.py",
    "platform_api/CHANGELOG.md",
]

SANDBOX_HOST = "46.250.235.83"
WORKERS = 4


def load_sandbox() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.sandbox.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_sandbox()
    host = secrets.get("SANDBOX_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("SANDBOX_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("SANDBOX_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"Target sandbox host: {host}")

    archive = Path(tempfile.mkdtemp(prefix="phase0-sbx-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/phase0-api.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        sftp.close()

        cmd = (
            "set -e; "
            "REPO=/opt/camxora/repo; "
            "tar -xzf /tmp/phase0-api.tar.gz -C $REPO; "
            "chown -R camxora:camxora $REPO/platform_api; "
            f"sed -i 's/--workers [0-9]\\+/--workers {WORKERS}/' "
            "/etc/systemd/system/camxora-api.service; "
            "systemctl daemon-reload; "
            "systemctl restart camxora-api; "
            "sleep 3; "
            "systemctl is-active camxora-api; "
            "systemctl show camxora-api -p ExecStart --no-pager; "
            "grep -n 'max_size=8\\|min_size=4\\|UNNEST' "
            "$REPO/platform_api/main.py "
            "$REPO/platform_api/routers/progress.py | head -20; "
            "echo PHASE0_SANDBOX_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
