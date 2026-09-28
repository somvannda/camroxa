"""Upload v1 daily_credits mapping files to sandbox API only."""
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

SANDBOX_HOST = "46.250.235.83"
FILES = [
    "platform_api/models/domain.py",
    "platform_api/repositories/license_repo.py",
]


def load_sandbox() -> dict[str, str]:
    path = ROOT / ".deploy" / "secrets.sandbox.env"
    if not path.is_file():
        path = Path(r"G:\Developments\Projects\Camxora\MusicGenerator") / ".deploy" / "secrets.sandbox.env"
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
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

    archive = Path(tempfile.mkdtemp(prefix="v1-daily-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/v1-daily-credits.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        sftp.close()
        cmd = r"""
set -e
REPO=/opt/camxora/repo
tar -tzf /tmp/v1-daily-credits.tar.gz
tar -xzf /tmp/v1-daily-credits.tar.gz -C $REPO
chown camxora:camxora $REPO/platform_api/models/domain.py $REPO/platform_api/repositories/license_repo.py
systemctl restart camxora-api
sleep 4
systemctl is-active camxora-api
echo API_DAILY_CREDITS_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=120)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
