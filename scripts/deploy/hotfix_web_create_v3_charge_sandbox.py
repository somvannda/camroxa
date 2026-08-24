"""Sandbox-only file-scoped hotfix: Web Create uses the v3 charge model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST_CANDIDATES = (
    ROOT,
    Path(r"D:\Development\Projects\Electron\MusicGenerator"),
)
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
FILES = [
    "platform_api/services/v3/generate_charge.py",
    "platform_api/services/v3/store.py",
    "platform_api/services/v3/period_grant_service.py",
    "platform_api/services/v3/credits_only_billing_service.py",
    "platform_api/services/v3/web_music_charge.py",
    "platform_api/services/web_music_service.py",
]


def load_sandbox() -> dict[str, str]:
    for root in HOST_CANDIDATES:
        path = root / ".deploy" / "secrets.sandbox.env"
        if path.is_file():
            break
    else:
        raise SystemExit("No secrets.sandbox.env")
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
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"Target sandbox host: {host}")
    client = ssh_connect(
        host,
        secrets.get("SANDBOX_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("SANDBOX_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
    )
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = ROOT / rel
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as handle:
                handle.write(local.read_bytes().replace(b"\r\n", b"\n"))
            print(f"uploaded {rel}")
        sftp.close()
        cmd = r"""
set -e
if ip -4 addr | grep -q '82.197.71.248'; then
  echo Refusing production host
  exit 1
fi
chown -R camxora:camxora \
  /opt/camxora/repo/platform_api/services/v3/generate_charge.py \
  /opt/camxora/repo/platform_api/services/v3/store.py \
  /opt/camxora/repo/platform_api/services/v3/period_grant_service.py \
  /opt/camxora/repo/platform_api/services/v3/credits_only_billing_service.py \
  /opt/camxora/repo/platform_api/services/v3/web_music_charge.py \
  /opt/camxora/repo/platform_api/services/web_music_service.py
python3 -m py_compile \
  /opt/camxora/repo/platform_api/services/v3/web_music_charge.py \
  /opt/camxora/repo/platform_api/services/web_music_service.py \
  /opt/camxora/repo/platform_api/services/v3/period_grant_service.py
systemctl restart camxora-api
sleep 8
systemctl is-active camxora-api || { journalctl -u camxora-api -n 40 --no-pager; exit 1; }
echo WEB_CREATE_V3_CHARGE_SANDBOX_OK
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.write(out)
        if err.strip():
            sys.stderr.write(err[-2000:] + "\n")
        if "WEB_CREATE_V3_CHARGE_SANDBOX_OK" not in out:
            raise SystemExit("Sandbox Web Create v3 charge hotfix did not finish cleanly.")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
